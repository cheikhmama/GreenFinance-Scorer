"""Routes HTTP de l'espace Administrateur.

Contiendra les endpoints de gestion et de supervision de la plateforme —
implémenté à l'Étape 10 (Espace Entreprise + Administrateur).
"""

from fastapi import APIRouter

router = APIRouter(tags=["admin"])
