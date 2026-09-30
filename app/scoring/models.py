"""Entités de persistance du scoring ESG : configurations de pondération (`scoring_configs`) et
scores calculés (`scores`) — tâche 3.1, docs/RENAME_PLAN.md §3d.

Une configuration est identifiée par le contenu de sa méthodologie, pas par un chemin de fichier
ni par son numéro de version : content_yaml garde le YAML tel que fourni, content_hash le SHA-256
de sa forme canonique (app/scoring/config_schema.py::empreinte_configuration). Tout calcul relit
content_yaml — le fichier config/weights/ ne sert qu'à enregistrer la configuration de référence
courante. Modifier le YAML sans changer d'empreinte est donc impossible par construction, et un
score ancien se recalcule toujours avec la méthodologie exacte qui l'a produit.

owner_user_id est nul pour une configuration de référence (méthodologie officielle), renseigné
pour une pondération personnalisée — qui ne modifie jamais un score officiel.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Column, Index, Text, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow

if TYPE_CHECKING:
    from app.auth.models import User
    from app.ingestion.models import ESGReport


class ScoringConfig(SQLModel, table=True):
    __tablename__ = "scoring_configs"
    __table_args__ = (
        # Une seule ligne par méthodologie et par propriétaire : cible des INSERT ... ON CONFLICT de
        # app/scoring/engine.py::enregistrer_configuration (deux validations concurrentes ne créent
        # jamais de doublon). La référence (propriétaire nul) a son propre index partiel, NULL
        # n'étant jamais égal à NULL dans une contrainte d'unicité ordinaire.
        Index(
            "uq_scoring_configs_reference_content_hash",
            "content_hash",
            unique=True,
            postgresql_where=text("owner_user_id IS NULL"),
        ),
        Index(
            "uq_scoring_configs_owner_content_hash",
            "owner_user_id",
            "content_hash",
            unique=True,
            postgresql_where=text("owner_user_id IS NOT NULL"),
        ),
        # Contenu et empreinte vont ensemble. Tous deux nuls seulement pour une configuration
        # antérieure à la tâche 3.1 dont le contenu d'origine n'a pas pu être retrouvé : jamais
        # recalculable, jamais inventée.
        CheckConstraint(
            "(content_yaml IS NULL) = (content_hash IS NULL)",
            name="ck_scoring_configs_content_with_hash",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    # Numéro de version déclaré dans le YAML : informatif (affiché avec le score). L'identité est
    # l'empreinte — deux contenus différents sous le même numéro restent deux configurations.
    version: int
    content_yaml: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    content_hash: str | None = Field(default=None, min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=utcnow)
    # RESTRICT, jamais SET NULL : un owner_user_id NULL désigne une configuration de RÉFÉRENCE —
    # le mettre à NULL à la suppression de son auteur la transformerait silencieusement en
    # méthodologie officielle.
    owner_user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="RESTRICT", index=True
    )

    owner: Optional["User"] = Relationship(back_populates="scoring_configs")
    scores: list["Score"] = Relationship(back_populates="config")


class Score(SQLModel, table=True):
    """Les quatre scores sont bornés 0-100 côté Pydantic et côté PostgreSQL. global_score est
    toujours renseigné (app/scoring/engine.py refuse de créer un score si aucun pilier n'est
    calculable) ; un pilier sans aucun indicateur présent reste NULL plutôt que de recevoir une
    note fabriquée (0 se lirait « pire score possible », pas « donnée absente »).

    coverage_rate (0-1) : part pondérée des indicateurs de la configuration effectivement présents
    dans le rapport — affichée à côté du score, qui ne se lit jamais sans elle. Nulle seulement
    pour un score calculé avant la tâche 3.1."""

    __tablename__ = "scores"
    __table_args__ = (
        # Un rapport peut avoir plusieurs scores (un par configuration) mais jamais deux sous la
        # même : c'est ce doublon-là qui rendrait le score officiel ambigu.
        UniqueConstraint("report_id", "config_id", name="uq_scores_report_config"),
        CheckConstraint("global_score BETWEEN 0 AND 100", name="ck_scores_global_score_range"),
        CheckConstraint(
            "environmental_score BETWEEN 0 AND 100", name="ck_scores_environmental_score_range"
        ),
        CheckConstraint("social_score BETWEEN 0 AND 100", name="ck_scores_social_score_range"),
        CheckConstraint(
            "governance_score BETWEEN 0 AND 100", name="ck_scores_governance_score_range"
        ),
        CheckConstraint("coverage_rate BETWEEN 0 AND 1", name="ck_scores_coverage_rate_range"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE")
    # RESTRICT : une configuration qui a produit des scores ne disparaît pas sous eux.
    config_id: uuid.UUID = Field(foreign_key="scoring_configs.id", ondelete="RESTRICT", index=True)
    global_score: float = Field(ge=0, le=100)
    environmental_score: float | None = Field(default=None, ge=0, le=100)
    social_score: float | None = Field(default=None, ge=0, le=100)
    governance_score: float | None = Field(default=None, ge=0, le=100)
    coverage_rate: float | None = Field(default=None, ge=0, le=1)
    computed_at: datetime = Field(default_factory=utcnow)

    report: "ESGReport" = Relationship(back_populates="scores")
    config: ScoringConfig = Relationship(back_populates="scores")
