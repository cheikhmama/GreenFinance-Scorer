"""Schémas Pydantic d'entrée/sortie du module Scoring.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2). Forme partagée entre
tous les espaces qui exposent le score officiel d'un rapport (Investisseur, Entreprise, Chercheur)
-- un seul endroit où "le score officiel" est mis en forme, jamais une copie divergente par module.
"""


from pydantic import BaseModel


class ScoreESGPublic(BaseModel):
    """Le Score officiel d'un rapport (app/scoring/engine.py::score_officiel), jamais un score
    personnalisé ni un score auto-déclaré par l'entreprise -- ces deux-là restent ailleurs (voir
    app/ingestion/schemas.py::RapportESGDetail pour la distinction explicite)."""

    global_score: float
    environmental_score: float | None
    social_score: float | None
    governance_score: float | None
    # Part pondérée des indicateurs de la méthodologie présents dans le rapport (0-1, tâche 3.1) :
    # un score ne se lit jamais sans elle. Nulle pour un score calculé avant qu'elle soit stockée.
    coverage_rate: float | None
    config_version: int
