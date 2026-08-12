"""Routes HTTP de l'espace Entreprise.

Contiendra les endpoints de dépôt de documents et de consultation du score
par une entreprise — implémenté à l'Étape 10 (Espace Entreprise +
Administrateur).
"""

from fastapi import APIRouter

router = APIRouter(tags=["company"])
