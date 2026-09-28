"""Téléchargement côté serveur d'un PDF depuis une URL fournie par le client (canal d'import
automatique, CanalDepot.AUTOMATIQUE).

Frontière délibérée, plus sensible qu'un dépôt multipart classique (app/company/upload_validation.py) :
ici le client ne fournit pas seulement un contenu non fiable, il fournit une CIBLE réseau que le
serveur va lui-même contacter. Sans garde-fou, un compte Entreprise pourrait transformer le
backend en proxy ouvert vers le réseau interne (ex. 169.254.169.254, les services internes
Docker) ou vers des services tiers arbitraires.

Défenses appliquées, dans cet ordre :
  1. Schéma http(s) uniquement, avant tout appel réseau.
  2. Résolution DNS puis rejet si l'IP résolue est privée/loopback/lien-local/multicast/réservée
     (bloque notamment 169.254.169.254, 127.0.0.1, 10.0.0.0/8, 192.168.0.0/16).
  3. Aucun suivi automatique de redirection HTTP — chaque saut est revalidé manuellement,
     plafonné à _SAUTS_REDIRECTION_MAX (empêche le contournement classique "premier hôte
     public, redirection 302 vers une IP interne").
  4. Téléchargement en flux avec plafond de taille identique au dépôt manuel
     (upload_validation.TAILLE_MAX_OCTETS) — jamais de tampon illimité en mémoire.
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
from urllib.parse import urlparse

import httpx

from app.company.upload_validation import TAILLE_MAX_OCTETS
from app.core.exceptions import ValidationError

_SCHEMES_AUTORISES = {"http", "https"}
_SAUTS_REDIRECTION_MAX = 2
_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)


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
        if (
            adresse.is_private
            or adresse.is_loopback
            or adresse.is_link_local
            or adresse.is_multicast
            or adresse.is_reserved
            or adresse.is_unspecified
        ):
            raise ValidationError(
                "Cette adresse n'est pas autorisée comme source d'import.",
                code="url_cible_non_autorisee",
            )


def _telecharger(url: str, *, sauts_restants: int) -> bytes:
    _valider_url_cible(url)
    try:
        with httpx.stream("GET", url, follow_redirects=False, timeout=_TIMEOUT) as reponse:
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
                return _telecharger(url_suivante, sauts_restants=sauts_restants - 1)

            if reponse.status_code != 200:
                raise ValidationError(
                    f"Le téléchargement a échoué (code {reponse.status_code}).",
                    code="telechargement_echoue",
                )

            morceaux = bytearray()
            for chunk in reponse.iter_bytes():
                morceaux.extend(chunk)
                if len(morceaux) > TAILLE_MAX_OCTETS:
                    raise ValidationError(
                        f"Le fichier dépasse la taille maximale autorisée "
                        f"({TAILLE_MAX_OCTETS // (1024 * 1024)} Mo).",
                        code="telechargement_trop_volumineux",
                    )
            return bytes(morceaux)
    except httpx.TimeoutException as exc:
        raise ValidationError(
            "Le téléchargement a dépassé le délai autorisé.", code="telechargement_delai_depasse"
        ) from exc
    except httpx.HTTPError as exc:
        raise ValidationError("Le téléchargement a échoué.", code="telechargement_echoue") from exc


def telecharger_pdf_depuis_url(url: str) -> bytes:
    """Point d'entrée unique du module. Ne valide jamais le PDF lui-même (upload_validation.py
    s'en charge sur les octets renvoyés) — seulement la légitimité de la cible réseau."""
    return _telecharger(url, sauts_restants=_SAUTS_REDIRECTION_MAX)
