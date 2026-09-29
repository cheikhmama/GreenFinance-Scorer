"""Énumérations partagées du schéma pivot (Étape 3).

Une seule définition par énumération, réutilisée par tous les modules
qui en ont besoin — jamais dupliquée localement dans un module métier.
"""

from enum import Enum

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum


def sa_enum_column(enum_cls: type[Enum], *, nullable: bool = False) -> Column:
    """Colonne SQLAlchemy pour un champ enum, stockée en VARCHAR + CHECK
    plutôt qu'en type ENUM natif PostgreSQL (native_enum=False).

    Certaines de ces énumérations (ex. MethodeDonnee) sont réutilisées sur
    plusieurs tables : un type ENUM natif porte le même nom PostgreSQL
    partout où il est utilisé, ce qui expose à un conflit de création lors
    d'une même migration. Le stockage VARCHAR+CHECK évite ce risque tout en
    conservant la contrainte de valeur au niveau base de données.
    """
    return Column(SAEnum(enum_cls, native_enum=False, length=64), nullable=nullable)


class ReportStatus(str, Enum):
    """Cycle de vie métier d'un rapport (docs/WORKFLOWS.md §1.2). L'avancement du pipeline
    d'extraction n'y figure plus : il vit dans ExtractionStatus, sur sa propre colonne."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING_AUDIT = "PENDING_AUDIT"
    # Avis de l'auditeur rendu, décision de l'Administrateur attendue (décision D2).
    PENDING_DECISION = "PENDING_DECISION"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class ExtractionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


class CompanyStatus(str, Enum):
    """Cycle de vie du compte entreprise (KYC, décision D5) — distinct de la publication de son
    score (Company.published_at)."""

    PENDING_ONBOARDING = "PENDING_ONBOARDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"


class TypeRapport(str, Enum):
    RAPPORT_ANNUEL = "RAPPORT_ANNUEL"
    RAPPORT_ESG = "RAPPORT_ESG"
    RAPPORT_CLIMAT = "RAPPORT_CLIMAT"


class CanalDepot(str, Enum):
    AUTOMATIQUE = "AUTOMATIQUE"
    ENTREPRISE = "ENTREPRISE"


class Pilier(str, Enum):
    ENVIRONNEMENT = "ENVIRONNEMENT"
    SOCIAL = "SOCIAL"
    GOUVERNANCE = "GOUVERNANCE"


class MethodeDonnee(str, Enum):
    RAPPORTEE = "RAPPORTEE"
    ESTIMEE = "ESTIMEE"
    CALCULEE = "CALCULEE"


class StatutCouvertureIndicateur(str, Enum):
    """Statut à 3 valeurs d'un code cible pour un rapport (Phase 6, remplace l'ancien booléen
    CouvertureIndicateur.trouve). ABSENT_CONFIRME n'est posé automatiquement par le pipeline que
    sous conditions strictes (voir app/ingestion/completeness.py::_absence_confirmee) — jamais une
    simple absence dans les pages examinées, qui reste NON_TROUVE."""

    TROUVE = "TROUVE"
    NON_TROUVE = "NON_TROUVE"
    ABSENT_CONFIRME = "ABSENT_CONFIRME"


class NiveauConfiance(str, Enum):
    ELEVE = "ELEVE"
    MOYEN = "MOYEN"
    FAIBLE = "FAIBLE"


class DecisionAudit(str, Enum):
    RECOMMANDE_VALIDATION = "RECOMMANDE_VALIDATION"
    RECOMMANDE_REJET = "RECOMMANDE_REJET"
    DEMANDE_CLARIFICATION = "DEMANDE_CLARIFICATION"


class Role(str, Enum):
    """Rôles de la plateforme (docs/ARCHITECTURE.md §1) — INSTITUTION conservé (décision D1)."""

    ADMIN = "ADMIN"
    ENTERPRISE = "ENTERPRISE"
    AUDITOR = "AUDITOR"
    INVESTOR = "INVESTOR"
    RESEARCHER = "RESEARCHER"
    INSTITUTION = "INSTITUTION"


class DevisePosition(str, Enum):
    MRU = "MRU"
    USD = "USD"
    EUR = "EUR"


class TypeDureeInvestissement(str, Enum):
    OUVERTE = "OUVERTE"
    FIXE = "FIXE"


class StatutRattachement(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    ACCEPTE = "ACCEPTE"
    REFUSE = "REFUSE"


class StatutProjet(str, Enum):
    OUVERT = "OUVERT"
    CLOTURE = "CLOTURE"


class StatutAnalyse(str, Enum):
    BROUILLON = "BROUILLON"
    SOUMISE = "SOUMISE"
    VALIDEE = "VALIDEE"
    CORRECTION_DEMANDEE = "CORRECTION_DEMANDEE"
