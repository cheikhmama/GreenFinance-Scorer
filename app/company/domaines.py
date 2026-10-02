"""Domaine de l'adresse d'un demandeur (tâches 5.3, 5.11) : une seule règle, appliquée à
l'inscription (refus immédiat) et rappelée dans la fenêtre KYC de l'Administrateur."""

from urllib.parse import urlsplit

# Messageries grand public : une telle adresse ne rattache pas le demandeur à son entreprise.
MESSAGERIES_GRAND_PUBLIC = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.fr", "hotmail.com", "hotmail.fr",
        "outlook.com", "outlook.fr", "live.com", "live.fr", "msn.com", "icloud.com", "me.com",
        "aol.com", "gmx.com", "gmx.fr", "proton.me", "protonmail.com", "orange.fr", "free.fr",
        "laposte.net", "yandex.com", "mail.com",
    }
)


def domaine_de_l_email(email: str) -> str:
    return email.rsplit("@", 1)[1].lower().rstrip(".")


def est_messagerie_grand_public(email: str) -> bool:
    return domaine_de_l_email(email) in MESSAGERIES_GRAND_PUBLIC


def domaine_du_site(site: str) -> str | None:
    hote = urlsplit(site).hostname
    if not hote:
        return None
    return hote.lower().rstrip(".").removeprefix("www.")


def domaines_correspondent(domaine_email: str, domaine_site: str) -> bool:
    """Même domaine, ou l'un sous-domaine de l'autre (rse.atlas.mr ↔ atlas.mr)."""
    return (
        domaine_email == domaine_site
        or domaine_email.endswith("." + domaine_site)
        or domaine_site.endswith("." + domaine_email)
    )
