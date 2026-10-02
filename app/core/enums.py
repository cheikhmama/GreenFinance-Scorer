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

    Certaines de ces énumérations (ex. DataMethod) sont réutilisées sur
    plusieurs tables : un type ENUM natif porte le même nom PostgreSQL
    partout où il est utilisé, ce qui expose à un conflit de création lors
    d'une même migration. Le stockage VARCHAR+CHECK évite ce risque tout en
    conservant la contrainte de valeur au niveau base de données.
    """
    return Column(SAEnum(enum_cls, native_enum=False, length=64), nullable=nullable)


class ReportStatus(str, Enum):
    """Cycle de vie d'un rapport (docs/WORKFLOWS.md §1.2), extraction comprise (tâche 5.1 : un
    seul statut, l'ancien ExtractionStatus est fondu ici).

    Pendant EXTRACTING, `extraction_started_at` distingue un job en file (NULL) d'un job en cours
    (renseigné) — c'est la seule différence dont la supervision a besoin.
    """

    DRAFT = "DRAFT"
    EXTRACTING = "EXTRACTING"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    AWAITING_ASSIGNMENT = "AWAITING_ASSIGNMENT"
    IN_AUDIT = "IN_AUDIT"
    # Avis de l'auditeur rendu, décision de l'Administrateur attendue (décision D2).
    PENDING_DECISION = "PENDING_DECISION"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class ExtractionRunStatus(str, Enum):
    """Issue d'une exécution du pipeline d'extraction sur un rapport (tâche 5.5, table
    extraction_runs) — une ligne par tentative, jamais réécrite après sa clôture."""

    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    # Échec passager (quota, réseau) : le job est remis en file, une nouvelle exécution suivra.
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


class RegistrationStatus(str, Enum):
    """Cycle de vie de l'inscription puis du compte entreprise (KYC, décision D5, tâche 5.2) —
    distinct de la publication de son score (Company.published_at).

    PENDING_ONBOARDING et INFO_REQUESTED : demande en cours d'examen, entreprise invisible et
    inactive. REJECTED : demande refusée, conservée avec son motif (plus supprimée). ACTIVE puis,
    éventuellement, SUSPENDED : entreprise validée.
    """

    PENDING_ONBOARDING = "PENDING_ONBOARDING"
    INFO_REQUESTED = "INFO_REQUESTED"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class KycCheckResult(str, Enum):
    """Résultat d'un contrôle KYC (tâche 5.3) — un éclairage pour l'Administrateur, jamais une
    décision automatique."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    # La source n'a pas répondu (GLEIF injoignable) : à refaire ou à vérifier à la main.
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    # Rien à contrôler (pas de LEI, pas de site web déclaré).
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TaxIdType(str, Enum):
    """Nature de l'identifiant fiscal d'une entreprise (tâche 5.10), déduite de son pays : NIF
    mauritanien, SIREN français, EIN américain, identifiant fiscal générique ailleurs."""

    NIF = "NIF"
    SIREN = "SIREN"
    EIN = "EIN"
    TAX_ID = "TAX_ID"


class AccessRequestStatus(str, Enum):
    """Demande d'accès d'un Investisseur ou d'un Chercheur (tâche 5.10) : en attente de
    l'Administrateur, approuvée (lien d'activation envoyé) ou refusée avec son motif."""

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class InvestorType(str, Enum):
    INVESTMENT_FUND = "INVESTMENT_FUND"
    BANK_INSTITUTIONAL = "BANK_INSTITUTIONAL"
    BUSINESS_ANGEL = "BUSINESS_ANGEL"
    OTHER = "OTHER"


class ResearchDomain(str, Enum):
    SUSTAINABLE_FINANCE = "SUSTAINABLE_FINANCE"
    CARBON_FOOTPRINT = "CARBON_FOOTPRINT"
    GOVERNANCE = "GOVERNANCE"
    OTHER = "OTHER"


class ReportType(str, Enum):
    RAPPORT_ANNUEL = "RAPPORT_ANNUEL"
    RAPPORT_ESG = "RAPPORT_ESG"
    RAPPORT_CLIMAT = "RAPPORT_CLIMAT"


class SubmissionChannel(str, Enum):
    AUTOMATIQUE = "AUTOMATIQUE"
    ENTREPRISE = "ENTREPRISE"


class Pillar(str, Enum):
    ENVIRONNEMENT = "ENVIRONNEMENT"
    SOCIAL = "SOCIAL"
    GOUVERNANCE = "GOUVERNANCE"


class DataMethod(str, Enum):
    RAPPORTEE = "RAPPORTEE"
    ESTIMEE = "ESTIMEE"
    CALCULEE = "CALCULEE"


class MetricCoverageStatus(str, Enum):
    """Statut à 3 valeurs d'un code cible pour un rapport (Phase 6, remplace l'ancien booléen
    MetricCoverage.trouve). ABSENT_CONFIRME n'est posé automatiquement par le pipeline que
    sous conditions strictes (voir app/ingestion/completeness.py::_absence_confirmee) — jamais une
    simple absence dans les pages examinées, qui reste NON_TROUVE."""

    TROUVE = "TROUVE"
    NON_TROUVE = "NON_TROUVE"
    ABSENT_CONFIRME = "ABSENT_CONFIRME"


class ConfidenceLevel(str, Enum):
    ELEVE = "ELEVE"
    MOYEN = "MOYEN"
    FAIBLE = "FAIBLE"


class AuditDecision(str, Enum):
    """Avis de l'Auditeur (tâche 5.6) — une recommandation ; la décision finale reste à
    l'Administrateur. Tout avis autre que FAVORABLE exige un commentaire."""

    FAVORABLE = "FAVORABLE"
    FAVORABLE_WITH_RESERVATIONS = "FAVORABLE_WITH_RESERVATIONS"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    UNFAVORABLE = "UNFAVORABLE"


class MetricReviewStatus(str, Enum):
    """Revue d'une valeur extraite par l'Auditeur affecté (tâche 5.6)."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    # Valeur corrigée : la valeur auditée remplace la valeur extraite au calcul.
    OVERRIDDEN = "OVERRIDDEN"
    # Valeur absente de la source : retirée du calcul, comme un indicateur non communiqué.
    NOT_FOUND = "NOT_FOUND"


class ReviewReason(str, Enum):
    """Catégorie de motif d'une correction ou d'un « non trouvé » (tâche 5.6)."""

    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    UNIT_ERROR = "UNIT_ERROR"
    WRONG_PERIOD = "WRONG_PERIOD"
    WRONG_SCOPE = "WRONG_SCOPE"
    NOT_IN_SOURCE = "NOT_IN_SOURCE"
    OTHER = "OTHER"


class Role(str, Enum):
    """Rôles de la plateforme (docs/ARCHITECTURE.md §1) — INSTITUTION conservé (décision D1)."""

    ADMIN = "ADMIN"
    ENTERPRISE = "ENTERPRISE"
    AUDITOR = "AUDITOR"
    INVESTOR = "INVESTOR"
    RESEARCHER = "RESEARCHER"
    INSTITUTION = "INSTITUTION"


class Currency(str, Enum):
    MRU = "MRU"
    USD = "USD"
    EUR = "EUR"


class BaselineScope(str, Enum):
    """Ensemble de référence d'une explication de score (tâche 3.2) : les pairs du même secteur,
    ou toutes les entreprises publiées."""

    SECTOR = "SECTOR"
    UNIVERSE = "UNIVERSE"


class ComparedScore(str, Enum):
    """Score comparé par une validation croisée (tâche 3.3) : un pilier ou le score global."""

    ENVIRONMENTAL = "ENVIRONMENTAL"
    SOCIAL = "SOCIAL"
    GOVERNANCE = "GOVERNANCE"
    GLOBAL = "GLOBAL"


class UnmatchedReason(str, Enum):
    """Pourquoi une ligne d'un jeu de référence n'entre pas dans la comparaison (tâche 3.3).
    UNKNOWN ne distingue jamais une entreprise inconnue d'une entreprise hors du périmètre."""

    UNKNOWN = "UNKNOWN"
    DUPLICATE = "DUPLICATE"  # entreprise déjà rapprochée par une ligne précédente
    NO_PLATFORM_SCORE = "NO_PLATFORM_SCORE"


class IdentifierType(str, Enum):
    """Identifiant de marché d'une ligne de portefeuille importée (tâche 2.2)."""

    ISIN = "ISIN"
    TICKER = "TICKER"


class MatchStatus(str, Enum):
    """Rapprochement d'une ligne de portefeuille avec une entreprise de la plateforme."""

    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    # Plusieurs entreprises possibles (ex. un ticker coté sur plusieurs places).
    AMBIGUOUS = "AMBIGUOUS"


class DurationType(str, Enum):
    OUVERTE = "OUVERTE"
    FIXE = "FIXE"


class AffiliationStatus(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    ACCEPTE = "ACCEPTE"
    REFUSE = "REFUSE"


class ProjectStatus(str, Enum):
    OUVERT = "OUVERT"
    CLOTURE = "CLOTURE"


class AnalysisStatus(str, Enum):
    BROUILLON = "BROUILLON"
    SOUMISE = "SOUMISE"
    VALIDEE = "VALIDEE"
    CORRECTION_DEMANDEE = "CORRECTION_DEMANDEE"
