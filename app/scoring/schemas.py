"""Schémas Pydantic d'entrée/sortie du module Scoring.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2). Forme partagée entre
tous les espaces qui exposent le score officiel d'un rapport (Investisseur, Entreprise, Chercheur)
-- un seul endroit où "le score officiel" est mis en forme, jamais une copie divergente par module.
"""


from pydantic import BaseModel


class ScoreESGPublic(BaseModel):
    """Le ScoreESG officiel d'un rapport (app/scoring/engine.py::score_officiel), jamais un score
    personnalisé ni un score auto-déclaré par l'entreprise -- ces deux-là restent ailleurs (voir
    app/ingestion/schemas.py::RapportESGDetail pour la distinction explicite)."""

    valeur_globale: float
    score_environnement: float | None
    score_social: float | None
    score_gouvernance: float | None
    configuration_version: int
