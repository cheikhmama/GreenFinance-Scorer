"""Contrôles KYC d'une inscription d'entreprise (tâche 5.3), calculés à la demande pour la fenêtre
de décision de l'Administrateur.

Quatre contrôles, chacun avec son résultat, un détail lisible et sa source :
- `gleif_registration` : le LEI déclaré existe à la GLEIF et son enregistrement est `ISSUED` ;
- `gleif_legal_name` : le nom déclaré correspond au nom légal GLEIF (ou à un nom antérieur ou
  commercial qu'elle connaît) ;
- `contact_domain` : le domaine de l'e-mail du demandeur est celui du site web déclaré ;
- `mandate_letter` : une lettre de mandat a été déposée.

Ces contrôles éclairent la décision, ils ne la prennent jamais : un résultat FAILED n'empêche pas
de valider, et GLEIF injoignable donne NOT_VERIFIABLE, jamais une erreur. Rien n'est stocké : la
fiche GLEIF peut changer, le contrôle se refait à chaque ouverture.
"""

import re
import unicodedata
import uuid
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
import structlog
from sqlmodel import Session

from app.admin.schemas import KycCheck, KycReport
from app.auth.models import User
from app.company.models import Company
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import KycCheckResult
from app.core.exceptions import NotFoundError

logger = structlog.get_logger(__name__)

SOURCE_GLEIF = "GLEIF — api.gleif.org"
SOURCE_DOMAINE = "E-mail du demandeur et site web déclaré"
SOURCE_MANDAT = "Lettre de mandat déposée avec la demande"

# Formes juridiques ignorées dans la comparaison des noms (« Minière du Nord SA » = « Minière du
# Nord »). Liste courte, assumée : un écart restant s'affiche, l'Administrateur juge.
FORMES_JURIDIQUES = {
    "sa", "sas", "sasu", "sarl", "eurl", "snc", "sca", "scs", "gie", "ag", "gmbh", "kg", "se",
    "nv", "bv", "oy", "ab", "as", "spa", "srl", "plc", "ltd", "limited", "llc", "inc", "corp",
    "corporation", "co", "company", "lp", "llp",
}

# Messageries grand public : un domaine qui ne dit rien de l'entreprise.
MESSAGERIES_GRAND_PUBLIC = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.fr", "hotmail.com", "hotmail.fr",
    "outlook.com", "outlook.fr", "live.com", "live.fr", "msn.com", "icloud.com", "me.com",
    "aol.com", "gmx.com", "gmx.fr", "proton.me", "protonmail.com", "orange.fr", "free.fr",
    "laposte.net", "yandex.com", "mail.com",
}


class GleifIndisponible(Exception):
    """GLEIF n'a pas répondu, ou pas de façon exploitable : contrôle non vérifiable."""


def recuperer_fiche_gleif(lei: str) -> dict[str, Any] | None:
    """Fiche LEI publique de la GLEIF (attributs `data.attributes`), None si le LEI est inconnu.
    Hôte fixé par la configuration ; le LEI, déjà validé (20 caractères alphanumériques, chiffres
    de contrôle), est de plus encodé dans le chemin."""
    settings = get_settings()
    url = f"{settings.gleif_api_url.rstrip('/')}/lei-records/{quote(lei, safe='')}"
    try:
        reponse = httpx.get(
            url,
            timeout=settings.gleif_timeout_seconds,
            headers={"Accept": "application/vnd.api+json"},
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        logger.warning("gleif_injoignable", error_type=type(exc).__name__)
        raise GleifIndisponible from exc
    if reponse.status_code == 404:
        return None
    if reponse.status_code != 200:
        logger.warning("gleif_reponse_inattendue", status_code=reponse.status_code)
        raise GleifIndisponible
    try:
        attributs = reponse.json()["data"]["attributes"]
    except (ValueError, KeyError, TypeError) as exc:
        logger.warning("gleif_reponse_illisible")
        raise GleifIndisponible from exc
    if not isinstance(attributs, dict):
        raise GleifIndisponible
    return attributs


def normaliser_nom(nom: str) -> str:
    """Casse, accents, ponctuation et formes juridiques ignorés."""
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    # Points retirés d'abord : « S.A. » devient « sa », une forme juridique reconnue.
    mots = re.sub(r"[^a-z0-9]+", " ", sans_accents.casefold().replace(".", "")).split()
    return " ".join(mot for mot in mots if mot not in FORMES_JURIDIQUES)


def _noms_gleif(fiche: dict[str, Any]) -> tuple[str | None, list[str]]:
    entite = fiche.get("entity") or {}
    nom_legal = (entite.get("legalName") or {}).get("name")
    autres = [
        nom["name"]
        for nom in entite.get("otherNames") or []
        if isinstance(nom, dict) and isinstance(nom.get("name"), str)
    ]
    return nom_legal if isinstance(nom_legal, str) else None, autres


def controles_gleif(entreprise: Company) -> list[KycCheck]:
    """Enregistrement LEI et nom légal, vérifiés en direct auprès de la GLEIF. Partagé par la
    fenêtre KYC et l'en-tête de l'espace Entreprise (tâche 5.9)."""
    def controle(code: str, libelle: str, resultat: KycCheckResult, detail: str) -> KycCheck:
        return KycCheck(code=code, label=libelle, result=resultat, detail=detail, source=SOURCE_GLEIF)

    enregistrement = "Enregistrement LEI"
    nom = "Nom légal"
    if not entreprise.lei:
        return [
            controle("gleif_registration", enregistrement, KycCheckResult.NOT_APPLICABLE, "Aucun LEI déclaré."),
            controle("gleif_legal_name", nom, KycCheckResult.NOT_APPLICABLE, "Aucun LEI déclaré."),
        ]
    try:
        fiche = recuperer_fiche_gleif(entreprise.lei)
    except GleifIndisponible:
        indisponible = "GLEIF n'a pas répondu : contrôle à refaire ou à mener à la main."
        return [
            controle("gleif_registration", enregistrement, KycCheckResult.NOT_VERIFIABLE, indisponible),
            controle("gleif_legal_name", nom, KycCheckResult.NOT_VERIFIABLE, indisponible),
        ]
    if fiche is None:
        return [
            controle(
                "gleif_registration",
                enregistrement,
                KycCheckResult.FAILED,
                f"Le LEI {entreprise.lei} est inconnu de la GLEIF.",
            ),
            controle("gleif_legal_name", nom, KycCheckResult.NOT_APPLICABLE, "LEI inconnu."),
        ]

    statut = (fiche.get("registration") or {}).get("status")
    statut_entite = (fiche.get("entity") or {}).get("status")
    enregistre = statut == "ISSUED" and statut_entite in (None, "ACTIVE")
    controle_enregistrement = controle(
        "gleif_registration",
        enregistrement,
        KycCheckResult.PASSED if enregistre else KycCheckResult.FAILED,
        f"Enregistrement {statut or 'inconnu'}, entité {statut_entite or 'inconnue'}.",
    )

    nom_legal, autres_noms = _noms_gleif(fiche)
    declare = normaliser_nom(entreprise.name)
    if nom_legal is not None and normaliser_nom(nom_legal) == declare:
        controle_nom = controle("gleif_legal_name", nom, KycCheckResult.PASSED, f"Nom légal GLEIF : {nom_legal}.")
    elif any(normaliser_nom(autre) == declare for autre in autres_noms):
        controle_nom = controle(
            "gleif_legal_name",
            nom,
            KycCheckResult.PASSED,
            f"Correspond à un autre nom connu de la GLEIF ; nom légal : {nom_legal or 'inconnu'}.",
        )
    else:
        controle_nom = controle(
            "gleif_legal_name",
            nom,
            KycCheckResult.FAILED,
            f"Nom déclaré « {entreprise.name} », nom légal GLEIF « {nom_legal or 'inconnu'} ».",
        )
    return [controle_enregistrement, controle_nom]


def _domaine_du_site(site: str) -> str | None:
    hote = urlsplit(site).hostname
    if not hote:
        return None
    hote = hote.lower().rstrip(".")
    return hote.removeprefix("www.")


def _controle_domaine(entreprise: Company, email: str | None) -> KycCheck:
    def controle(resultat: KycCheckResult, detail: str) -> KycCheck:
        return KycCheck(
            code="contact_domain",
            label="Domaine du contact",
            result=resultat,
            detail=detail,
            source=SOURCE_DOMAINE,
        )

    if email is None or "@" not in email:
        return controle(KycCheckResult.NOT_APPLICABLE, "Aucun compte titulaire.")
    domaine_email = email.rsplit("@", 1)[1].lower()
    if domaine_email in MESSAGERIES_GRAND_PUBLIC:
        return controle(
            KycCheckResult.FAILED,
            f"Adresse d'une messagerie grand public ({domaine_email}) : elle ne rattache pas le "
            "demandeur à l'entreprise.",
        )
    domaine_site = _domaine_du_site(entreprise.website) if entreprise.website else None
    if domaine_site is None:
        return controle(KycCheckResult.NOT_APPLICABLE, "Aucun site web déclaré.")
    correspond = (
        domaine_email == domaine_site
        or domaine_email.endswith("." + domaine_site)
        or domaine_site.endswith("." + domaine_email)
    )
    return controle(
        KycCheckResult.PASSED if correspond else KycCheckResult.FAILED,
        f"E-mail @{domaine_email}, site {domaine_site}.",
    )


def _controle_mandat(entreprise: Company) -> KycCheck:
    present = entreprise.mandate_letter_path is not None
    if present and entreprise.mandate_letter_uploaded_at is not None:
        detail = f"Déposée le {entreprise.mandate_letter_uploaded_at:%d/%m/%Y}."
    elif present:
        detail = "Déposée."
    else:
        detail = "Aucune lettre de mandat (inscription antérieure à la tâche 5.2, ou créée par un administrateur)."
    return KycCheck(
        code="mandate_letter",
        label="Lettre de mandat",
        result=KycCheckResult.PASSED if present else KycCheckResult.FAILED,
        detail=detail,
        source=SOURCE_MANDAT,
    )


def rapport_kyc(session: Session, entreprise_id: uuid.UUID) -> KycReport:
    entreprise = session.get(Company, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    titulaire = session.get(User, entreprise.owner_user_id) if entreprise.owner_user_id else None
    email = titulaire.email if titulaire is not None else None
    return KycReport(
        company_id=entreprise.id,
        company_name=entreprise.name,
        status=entreprise.status,
        country=entreprise.country,
        tax_id=entreprise.tax_id,
        tax_id_type=entreprise.tax_id_type,
        lei=entreprise.lei,
        isin=entreprise.isin,
        website=entreprise.website,
        contact_name=titulaire.name if titulaire is not None else None,
        contact_email=email,
        registered_at=entreprise.registered_at,
        mandate_letter_available=entreprise.mandate_letter_path is not None,
        mandate_letter_uploaded_at=entreprise.mandate_letter_uploaded_at,
        info_request_message=entreprise.info_request_message,
        info_requested_at=entreprise.info_requested_at,
        info_response_message=entreprise.info_response_message,
        checked_at=utcnow(),
        checks=[*controles_gleif(entreprise), _controle_domaine(entreprise, email), _controle_mandat(entreprise)],
    )
