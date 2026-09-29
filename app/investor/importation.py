"""Import des positions d'un portefeuille par ISIN ou ticker (tâche 2.2, docs/WORKFLOWS.md §2.2).

Tout ou rien : le fichier entier est validé avant la moindre écriture ; une seule ligne invalide
et rien n'est enregistré, la réponse listant CHAQUE ligne en erreur (fields `line_<n>`, n = numéro
de ligne dans le fichier, en-tête CSV = ligne 1). Une ligne valide dont l'identifiant ne désigne
aucune entreprise est conservée (UNMATCHED / AMBIGUOUS), jamais écartée en silence.

Règles :
- Formats : CSV (séparateur `,`, `;` ou tabulation, décimale `,` acceptée avec `;`) ou JSON (liste
  d'objets, ou {"lines": [...]}). Colonnes : identifier (requis), identifier_type (ISIN par défaut,
  ou TICKER), puis SOIT outstanding_amount + currency, SOIT weight — jamais un mélange.
- Poids : leur somme vaut 1 (± 0,001) ; un import par poids exige `total_value` (dans la devise
  de référence du portefeuille) pour en déduire des montants — PCAF a besoin de montants, jamais de
  poids seuls (docs/ARCHITECTURE.md §3.4).
- Rapprochement : seulement avec une entreprise PUBLIÉE (sinon UNMATCHED — un import ne révèle
  jamais l'existence d'une entreprise en attente ou non publiée). ISIN unique ; un ticker peut
  désigner plusieurs entreprises : AMBIGUOUS.
- Une entreprise rapprochée suit les mêmes règles qu'une saisie manuelle (app/investor/
  portfolio.py) : active, et montant au moins égal à son minimum d'investissement.
- Le portefeuille doit être vide : remplacer des positions ayant un historique les détruirait.
"""

import csv
import io
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, col, select

from app.company.identifiers import isin_valide
from app.company.models import Company
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import (
    CompanyStatus,
    DevisePosition,
    IdentifierType,
    MatchStatus,
    TypeDureeInvestissement,
)
from app.core.exceptions import ValidationError
from app.investor import fx
from app.investor.models import Portfolio, PortfolioPosition
from app.investor.portfolio import (
    _construire_position,
    _portefeuille_de_investisseur,
    _verifier_montant_minimum,
)

TAILLE_MAX_OCTETS = 1024 * 1024
LIGNES_MAX = 5000
TOLERANCE_SOMME_POIDS = 0.001
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_COLONNES = {"identifier", "identifier_type", "outstanding_amount", "currency", "weight"}


@dataclass
class _Ligne:
    numero: int
    identifiant: str
    type_identifiant: IdentifierType
    montant: float | None
    devise: DevisePosition | None
    poids: float | None


@dataclass
class ResultatImport:
    positions: list[PortfolioPosition]


def _nombre(brut: Any, decimale_virgule: bool) -> float | None:
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        return None
    if isinstance(brut, int | float) and not isinstance(brut, bool):
        return float(brut)
    texte = str(brut).strip().replace(" ", "").replace(" ", "")
    if decimale_virgule:
        texte = texte.replace(",", ".")
    return float(texte)  # ValueError géré par l'appelant


def _lire(contenu: bytes, nom_fichier: str | None) -> tuple[list[tuple[int, dict[str, Any]]], bool]:
    """Renvoie [(numéro de ligne, valeurs)] et si la virgule est le séparateur décimal."""
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ValidationError("Le fichier dépasse 1 Mo.", code="import_trop_volumineux")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("Le fichier doit être encodé en UTF-8.", code="import_illisible") from exc

    est_json = (nom_fichier or "").lower().endswith(".json") or texte.lstrip()[:1] in ("[", "{")
    if est_json:
        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as exc:
            raise ValidationError("JSON illisible.", code="import_illisible") from exc
        if isinstance(donnees, dict):
            donnees = donnees.get("lines")
        if not isinstance(donnees, list) or not all(isinstance(d, dict) for d in donnees):
            raise ValidationError(
                "JSON attendu : une liste de lignes, ou {\"lines\": [...]}.", code="import_illisible"
            )
        return [(i + 1, {str(k).strip().lower(): v for k, v in d.items()}) for i, d in enumerate(donnees)], False

    premiere = texte.splitlines()[0] if texte.strip() else ""
    separateur = max((",", ";", "\t"), key=premiere.count)
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=separateur)
    if lecteur.fieldnames is None or "identifier" not in {c.strip().lower() for c in lecteur.fieldnames}:
        raise ValidationError(
            "En-tête CSV attendu, avec au moins la colonne identifier.", code="import_illisible"
        )
    lignes = [
        (numero + 2, {(k or "").strip().lower(): v for k, v in ligne.items()})
        for numero, ligne in enumerate(lecteur)
        if any((v or "").strip() for v in ligne.values() if isinstance(v, str))
    ]
    return lignes, separateur == ";"


def _valider_ligne(numero: int, valeurs: dict[str, Any], decimale_virgule: bool) -> _Ligne:
    inconnues = set(valeurs) - _COLONNES
    if inconnues:
        raise ValueError(f"colonne(s) inconnue(s) : {', '.join(sorted(inconnues))}")
    identifiant = str(valeurs.get("identifier") or "").replace(" ", "").upper()
    if not identifiant:
        raise ValueError("identifier est requis")
    brut_type = str(valeurs.get("identifier_type") or "ISIN").strip().upper()
    try:
        type_identifiant = IdentifierType(brut_type)
    except ValueError as exc:
        raise ValueError("identifier_type doit valoir ISIN ou TICKER") from exc
    if type_identifiant == IdentifierType.ISIN and not isin_valide(identifiant):
        raise ValueError(f"ISIN invalide : {identifiant}")
    if type_identifiant == IdentifierType.TICKER and not _TICKER.match(identifiant):
        raise ValueError(f"ticker invalide : {identifiant}")

    try:
        montant = _nombre(valeurs.get("outstanding_amount"), decimale_virgule)
        poids = _nombre(valeurs.get("weight"), decimale_virgule)
    except ValueError as exc:
        raise ValueError("nombre illisible (outstanding_amount ou weight)") from exc
    brut_devise = str(valeurs.get("currency") or "").strip().upper()

    if montant is not None and poids is not None:
        raise ValueError("renseigner outstanding_amount OU weight, pas les deux")
    if montant is None and poids is None:
        raise ValueError("outstanding_amount ou weight est requis")
    devise: DevisePosition | None = None
    if montant is not None:
        if montant <= 0:
            raise ValueError("outstanding_amount doit être strictement positif")
        try:
            devise = DevisePosition(brut_devise)
        except ValueError as exc:
            devises = ", ".join(d.value for d in DevisePosition)
            raise ValueError(f"currency doit valoir {devises}") from exc
    if poids is not None and not 0 < poids <= 1:
        raise ValueError("weight doit être compris entre 0 (exclu) et 1")
    return _Ligne(numero, identifiant, type_identifiant, montant, devise, poids)


def _rapprocher(session: Session, ligne: _Ligne) -> tuple[MatchStatus, Company | None]:
    colonne = Company.isin if ligne.type_identifiant == IdentifierType.ISIN else Company.ticker
    candidates = session.exec(
        select(Company).where(
            col(colonne) == ligne.identifiant, col(Company.published_at).is_not(None)
        )
    ).all()
    if len(candidates) == 1:
        return MatchStatus.MATCHED, candidates[0]
    return (MatchStatus.AMBIGUOUS if candidates else MatchStatus.UNMATCHED), None


def importer_positions(
    session: Session,
    investisseur_id: uuid.UUID,
    portefeuille_id: uuid.UUID,
    contenu: bytes,
    nom_fichier: str | None,
    total_value: float | None,
) -> list[PortfolioPosition]:
    portefeuille: Portfolio = _portefeuille_de_investisseur(session, investisseur_id, portefeuille_id)
    if portefeuille.archived:
        raise ValidationError("Ce portefeuille est archivé.", code="portefeuille_archive")
    if session.exec(
        select(PortfolioPosition.id).where(col(PortfolioPosition.portfolio_id) == portefeuille.id)
    ).first() is not None:
        raise ValidationError(
            "L'import se fait dans un portefeuille vide (les positions existantes ont un "
            "historique à préserver).",
            code="portefeuille_non_vide",
        )

    brutes, decimale_virgule = _lire(contenu, nom_fichier)
    if not brutes:
        raise ValidationError("Le fichier ne contient aucune ligne.", code="import_vide")
    if len(brutes) > LIGNES_MAX:
        raise ValidationError(f"Au plus {LIGNES_MAX} lignes par import.", code="import_trop_volumineux")

    erreurs: dict[str, str] = {}
    lignes: list[_Ligne] = []
    vus: dict[tuple[IdentifierType, str], int] = {}
    for numero, valeurs in brutes:
        try:
            ligne = _valider_ligne(numero, valeurs, decimale_virgule)
        except ValueError as exc:
            erreurs[f"line_{numero}"] = str(exc)
            continue
        cle = (ligne.type_identifiant, ligne.identifiant)
        if cle in vus:
            erreurs[f"line_{numero}"] = f"identifiant déjà présent ligne {vus[cle]}"
            continue
        vus[cle] = numero
        lignes.append(ligne)

    par_poids = [ligne for ligne in lignes if ligne.poids is not None]
    if par_poids and len(par_poids) != len(lignes):
        erreurs["file"] = "Toutes les lignes doivent utiliser le même mode : montants ou poids."
    elif par_poids and not erreurs:
        somme = sum(ligne.poids or 0 for ligne in par_poids)
        if abs(somme - 1) > TOLERANCE_SOMME_POIDS:
            erreurs["file"] = f"La somme des poids vaut {somme:.4f} au lieu de 1."
        elif total_value is None or total_value <= 0:
            erreurs["file"] = (
                "Un import par poids exige total_value (valeur totale du portefeuille, dans sa "
                "devise de référence) pour en déduire les montants."
            )

    chemin_taux = get_settings().fx_rates_path
    devise_ref = portefeuille.reference_currency
    preparees: list[tuple[_Ligne, MatchStatus, Company | None, float, float, float | None]] = []
    if not erreurs:
        for ligne in lignes:
            if ligne.poids is not None:
                assert total_value is not None
                montant, devise = ligne.poids * total_value, devise_ref
            else:
                assert ligne.montant is not None and ligne.devise is not None
                montant, devise = ligne.montant, ligne.devise
            converti, taux = fx.convertir(montant, devise, devise_ref, chemin_taux)
            statut, entreprise = _rapprocher(session, ligne)
            if entreprise is not None:
                if entreprise.status != CompanyStatus.ACTIVE:
                    erreurs[f"line_{ligne.numero}"] = "entreprise suspendue : aucune nouvelle position"
                    continue
                try:
                    _verifier_montant_minimum(entreprise, converti, devise_ref, chemin_taux)
                except ValidationError as exc:
                    erreurs[f"line_{ligne.numero}"] = exc.message
                    continue
            ligne.montant, ligne.devise = montant, devise
            preparees.append((ligne, statut, entreprise, converti, montant, taux))

    if erreurs:
        nb = sum(1 for cle in erreurs if cle.startswith("line_"))
        raise ValidationError(
            f"Import refusé : {nb} ligne(s) en erreur{' et une erreur de fichier' if 'file' in erreurs else ''}."
            " Rien n'a été enregistré.",
            code="import_invalide",
            fields=erreurs,
        )

    total_converti = sum(converti for _l, _s, _e, converti, _m, _t in preparees)
    aujourdhui = utcnow()
    positions = [
        _construire_position(
            {
                "portfolio_id": portefeuille.id,
                "company_id": entreprise.id if entreprise else None,
                "identifier_type": ligne.type_identifiant,
                "identifier_raw": ligne.identifiant,
                "match_status": statut,
                "outstanding_amount": montant,
                "currency": ligne.devise,
                "fx_rate_used": taux,
                "converted_amount": converti,
                # Poids déclaré, sinon dérivé des montants convertis : toute ligne importée porte
                # son poids.
                "weight": ligne.poids if ligne.poids is not None else converti / total_converti,
                "duration_type": TypeDureeInvestissement.OUVERTE,
                "start_date": aujourdhui,
            }
        )
        for ligne, statut, entreprise, converti, montant, taux in preparees
    ]
    session.add_all(positions)
    session.commit()
    for position in positions:
        session.refresh(position)
    return positions
