"""Téléchargement côté serveur d'un PDF depuis une URL fournie par le client (canal d'import
automatique, SubmissionChannel.AUTOMATIQUE).

Frontière délibérée, plus sensible qu'un dépôt multipart classique (app/company/upload_validation.py) :
ici le client ne fournit pas seulement un contenu non fiable, il fournit une CIBLE réseau que le
serveur va lui-même contacter. Sans garde-fou, un compte Entreprise pourrait transformer le
backend en proxy ouvert vers le réseau interne (ex. 169.254.169.254, les services internes
Docker) ou vers des services tiers arbitraires.

Défenses appliquées, dans cet ordre :
  1. Schéma http(s) uniquement, avant tout appel réseau.
  2. Résolution DNS puis rejet de toute IP qui n'est pas globalement routable (`not is_global`,
     tâche 4.3) — liste d'autorisation plutôt que liste noire : privé, loopback, lien-local,
     CGNAT 100.64.0.0/10, plages de documentation et de test, réservé... ; IPv6 contenant une
     IPv4 (mappée ::ffff:, 6to4) vérifiée sur l'IPv4 embarquée.
  3. Aucun suivi automatique de redirection HTTP — chaque saut est revalidé manuellement,
     plafonné à _SAUTS_REDIRECTION_MAX (empêche le contournement classique "premier hôte
     public, redirection 302 vers une IP interne").
  4. Téléchargement en flux avec plafond de taille identique au dépôt manuel
     (upload_validation.TAILLE_MAX_OCTETS) — jamais de tampon illimité en mémoire — et échéance
     TOTALE (_DELAI_TOTAL_SECONDES, redirections comprises) : un délai par lecture ne suffit pas,
     un serveur qui envoie un octet toutes les quelques secondes le réarmerait indéfiniment.
  5. Validation PDF sur les octets reçus uniquement (upload_validation.valider_pdf) — jamais
     confiance au Content-Type distant.

Limite assumée, non résolue ici (à documenter, pas à ignorer) : entre l'étape 2 (résolution DNS
de validation) et la connexion réelle faite par httpx, un serveur DNS malveillant à TTL nul
pourrait en théorie renvoyer une IP différente ("DNS rebinding") — fermer complètement cette
fenêtre demanderait un transport HTTP personnalisé qui épingle l'IP validée jusque dans la
connexion TLS (SNI/vérification de certificat par IP plutôt que par nom), hors périmètre de cette
passe. Le délai entre les deux résolutions est de l'ordre de la milliseconde (même appel de
fonction), ce qui réduit fortement mais n'élimine pas ce risque résiduel.
"""

import ipaddress
import socket
import time
from urllib.parse import urlparse

import httpx

from app.company.upload_validation import TAILLE_MAX_OCTETS
from app.core.exceptions import ValidationError

_SCHEMES_AUTORISES = {"http", "https"}
_SAUTS_REDIRECTION_MAX = 2
_DELAI_CONNEXION_SECONDES = 10.0
_DELAI_LECTURE_SECONDES = 30.0
_DELAI_TOTAL_SECONDES = 60.0


def _adresse_autorisee(adresse: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(adresse, ipaddress.IPv6Address):
        embarquee = adresse.ipv4_mapped or adresse.sixtofour
        if embarquee is not None:
            return _adresse_autorisee(embarquee)
    return adresse.is_global and not adresse.is_multicast


def _delai_depasse() -> ValidationError:
    return ValidationError(
        "Le téléchargement a dépassé le délai autorisé.", code="telechargement_delai_depasse"
    )


def _delais(echeance: float) -> httpx.Timeout:
    restant = echeance - time.monotonic()
    if restant <= 0:
        raise _delai_depasse()
    return httpx.Timeout(
        connect=min(_DELAI_CONNEXION_SECONDES, restant),
        read=min(_DELAI_LECTURE_SECONDES, restant),
        write=min(_DELAI_LECTURE_SECONDES, restant),
        pool=min(_DELAI_LECTURE_SECONDES, restant),
    )


def _valider_url_cible(url: str) -> None:
    morceaux = urlparse(url)
    if morceaux.scheme not in _SCHEMES_AUTORISES or not morceaux.hostname:
        raise ValidationError(
            "Seules les URL http:// ou https:// avec un hôte valide sont acceptées.",
            code="url_schema_invalide",
        )

    port = morceaux.port or (443 if morceaux.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(morceaux.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValidationError(
            "Impossible de résoudre l'adresse indiquée.", code="url_cible_non_autorisee"
        ) from exc

    for info in infos:
        adresse = ipaddress.ip_address(info[4][0])
        if not _adresse_autorisee(adresse):
            raise ValidationError(
                "Cette adresse n'est pas autorisée comme source d'import.",
                code="url_cible_non_autorisee",
            )


def _telecharger(url: str, *, sauts_restants: int, echeance: float) -> bytes:
    _valider_url_cible(url)
    try:
        with httpx.stream("GET", url, follow_redirects=False, timeout=_delais(echeance)) as reponse:
            if reponse.is_redirect:
                if sauts_restants <= 0:
                    raise ValidationError(
                        "Trop de redirections pour cette URL.", code="telechargement_echoue"
                    )
                cible = reponse.headers.get("location")
                if not cible:
                    raise ValidationError(
                        "Redirection sans destination valide.", code="telechargement_echoue"
                    )
                url_suivante = str(httpx.URL(url).join(cible))
                return _telecharger(
                    url_suivante, sauts_restants=sauts_restants - 1, echeance=echeance
                )

            if reponse.status_code != 200:
                raise ValidationError(
                    f"Le téléchargement a échoué (code {reponse.status_code}).",
                    code="telechargement_echoue",
                )

            morceaux = bytearray()
            for chunk in reponse.iter_bytes():
                if time.monotonic() > echeance:
                    raise _delai_depasse()
                morceaux.extend(chunk)
                if len(morceaux) > TAILLE_MAX_OCTETS:
                    raise ValidationError(
                        f"Le fichier dépasse la taille maximale autorisée "
                        f"({TAILLE_MAX_OCTETS // (1024 * 1024)} Mo).",
                        code="telechargement_trop_volumineux",
                    )
            return bytes(morceaux)
    except httpx.TimeoutException as exc:
        raise _delai_depasse() from exc
    except httpx.HTTPError as exc:
        raise ValidationError("Le téléchargement a échoué.", code="telechargement_echoue") from exc


def telecharger_pdf_depuis_url(url: str) -> bytes:
    """Point d'entrée unique du module. Ne valide jamais le PDF lui-même (upload_validation.py
    s'en charge sur les octets renvoyés) — seulement la légitimité de la cible réseau."""
    return _telecharger(
        url,
        sauts_restants=_SAUTS_REDIRECTION_MAX,
        echeance=time.monotonic() + _DELAI_TOTAL_SECONDES,
    )
