"""Routes HTTP de l'espace Chercheur.

Contiendra les endpoints d'accès aux données agrégées et anonymisées à des
fins de recherche — implémenté à l'Étape 17
(Espace Chercheur / Institution).
"""

from fastapi import APIRouter

router = APIRouter(tags=["researcher"])
