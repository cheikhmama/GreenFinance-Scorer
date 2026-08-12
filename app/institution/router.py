"""Routes HTTP de l'espace Institution.

Contiendra les endpoints d'accès institutionnel aux données de la
plateforme (reporting réglementaire, vues consolidées) — implémenté à
l'Étape 17 (Espace Chercheur / Institution).
"""

from fastapi import APIRouter

router = APIRouter(tags=["institution"])
