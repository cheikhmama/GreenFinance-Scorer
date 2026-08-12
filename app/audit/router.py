"""Routes HTTP de l'espace Auditeur.

Contiendra les endpoints de consultation des dossiers assignés et de
soumission d'avis d'audit — implémenté à l'Étape 11 (Espace Auditeur).
"""

from fastapi import APIRouter

router = APIRouter(tags=["audit"])
