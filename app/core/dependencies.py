"""Dépendances FastAPI transversales, non liées à un domaine métier précis.

get_current_user est un point d'ancrage explicite : les futurs modules
peuvent déjà la référencer dans leurs signatures de route sans qu'elle
fonctionne encore. À l'Étape 9 (Authentification et autorisation), seul
le contenu de cette fonction change — aucune route déjà écrite n'aura à
être modifiée.
"""

from app.core.database import get_session

__all__ = ["get_current_user", "get_session"]


def get_current_user() -> None:
    """Placeholder explicite — l'authentification n'existe pas encore.

    Lève volontairement une erreur plutôt que de simuler silencieusement
    un utilisateur connecté, pour qu'aucune route ne puisse accidentellement
    se croire protégée avant l'Étape 9.
    """
    raise NotImplementedError("Authentification implémentée à l'Étape 9")
