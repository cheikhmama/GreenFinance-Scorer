"""Entités de persistance du scoring ESG (configuration de pondération, score calculé).

ConfigurationPonderation.utilisateur_id est nul pour la configuration de
référence maintenue par l'Administrateur, et renseigné pour toute
configuration personnalisée — quel que soit le rôle de son créateur parmi
Investisseur, Chercheur et Institution (pas réservé à l'Investisseur). Le
moteur de calcul reste implémenté à l'Étape 12 (Scoring ESG).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow

if TYPE_CHECKING:
    from app.auth.models import User
    from app.ingestion.models import ESGReport


class ConfigurationPonderation(SQLModel, table=True):
    __tablename__ = "configuration_ponderation"
    __table_args__ = (
        # Une seule ligne de référence par version (tâche 1.6) : cible de l'INSERT ... ON CONFLICT
        # de app/scoring/engine.py::obtenir_configuration_reference. Sans elle, chaque changement
        # de version du fichier YAML (ou deux validations concurrentes) créait une ligne de plus.
        Index(
            "uq_configuration_ponderation_reference_version",
            "version",
            unique=True,
            postgresql_where=text("utilisateur_id IS NULL"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nom: str
    version: int
    fichier_yaml: str
    date_creation: datetime = Field(default_factory=utcnow)
    # Nul = configuration de référence (Administrateur). Renseigné =
    # personnalisation par un Investisseur, Chercheur ou Institution. Une seule
    # référence par version (uq_configuration_ponderation_reference_version).
    # RESTRICT, jamais SET NULL : un utilisateur_id NULL désigne la configuration de RÉFÉRENCE —
    # le mettre à NULL à la suppression du Chercheur la transformerait silencieusement en
    # méthodologie officielle.
    utilisateur_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="RESTRICT", index=True
    )

    utilisateur: Optional["User"] = Relationship(
        back_populates="scoring_configs"
    )
    scores: list["ScoreESG"] = Relationship(back_populates="configuration")


class ScoreESG(SQLModel, table=True):
    """Les quatre scores sont bornés 0-100 à la fois côté Pydantic (Field) et côté PostgreSQL
    (__table_args__, Phase 5 §6). valeur_globale est toujours renseignée (app/scoring/engine.py
    refuse de créer un ScoreESG si aucun pilier n'est calculable) ; les trois scores de pilier
    sont nullables — un pilier sans aucun indicateur trouvé dans le rapport reste NULL plutôt que
    de recevoir une note fabriquée (0 se lirait comme « pire score possible », pas comme
    « donnée absente ») ; valeur_globale se recalcule alors sur les seuls piliers présents."""

    __tablename__ = "score_esg"
    __table_args__ = (
        # Un rapport peut légitimement avoir plusieurs scores (un par ConfigurationPonderation :
        # la référence, plus une par pondération personnalisée d'un Investisseur/Chercheur/
        # Institution — voir tests/integration/test_models_scoring.py) mais jamais deux fois sous
        # la même configuration : c'est ce doublon-là qui rendrait score_officiel() ambigu.
        UniqueConstraint(
            "rapport_id", "configuration_id", name="uq_score_esg_rapport_configuration"
        ),
        CheckConstraint(
            "valeur_globale BETWEEN 0 AND 100", name="ck_score_esg_valeur_globale_bornee"
        ),
        CheckConstraint(
            "score_environnement BETWEEN 0 AND 100", name="ck_score_esg_environnement_borne"
        ),
        CheckConstraint("score_social BETWEEN 0 AND 100", name="ck_score_esg_social_borne"),
        CheckConstraint(
            "score_gouvernance BETWEEN 0 AND 100", name="ck_score_esg_gouvernance_borne"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE")
    configuration_id: uuid.UUID = Field(foreign_key="configuration_ponderation.id")
    valeur_globale: float = Field(ge=0, le=100)
    score_environnement: float | None = Field(default=None, ge=0, le=100)
    score_social: float | None = Field(default=None, ge=0, le=100)
    score_gouvernance: float | None = Field(default=None, ge=0, le=100)
    date_calcul: datetime = Field(default_factory=utcnow)

    rapport: "ESGReport" = Relationship(back_populates="scores")
    configuration: ConfigurationPonderation = Relationship(back_populates="scores")
