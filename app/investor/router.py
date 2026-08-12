"""Routes HTTP de l'espace Investisseur.

Contiendra les endpoints de consultation des scores et de gestion des
portefeuilles côté investisseur — implémenté à l'Étape 16
(Espace Investisseur).
"""

from fastapi import APIRouter

router = APIRouter(tags=["investor"])
