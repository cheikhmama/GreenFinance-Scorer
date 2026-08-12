"""Routes HTTP d'authentification (connexion, MFA, gestion de session).

Contiendra les endpoints login/logout/MFA — implémenté à l'Étape 9
(Authentification et autorisation).
"""

from fastapi import APIRouter

router = APIRouter(tags=["auth"])
