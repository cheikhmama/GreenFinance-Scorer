"""Entités de persistance produites par le pipeline d'extraction documentaire.

ESGReport porte le cycle de vie documentaire (ReportStatus) et l'avancement de son extraction
(ExtractionStatus). Les entités qui en dérivent (ESGMetric, CarbonEmission, Evidence —
Prompt 3.5 ; DiscrepancyFlag — Prompt 3.8) sont exclusivement produites
par le pipeline automatique (Étapes 4 à 7) : un Auditeur les consulte et
les valide via AuditOpinion (app/audit/models.py), il ne les crée jamais
lui-même — aucun champ ni table ici ne permet une saisie manuelle par
l'Auditeur.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import (
    ConfidenceLevel,
    DataMethod,
    ExtractionStatus,
    MetricCoverageStatus,
    Pillar,
    ReportStatus,
    ReportType,
    SubmissionChannel,
    sa_enum_column,
)

if TYPE_CHECKING:
    from app.audit.models import AuditOpinion
    from app.auth.models import User
    from app.company.models import Company
    from app.scoring.models import Score


class ESGReport(SQLModel, table=True):
    """Table `esg_reports` (docs/RENAME_PLAN.md §2.2)."""

    __tablename__ = "esg_reports"
    # Un même fichier (même empreinte) ne peut être déposé deux fois pour la même entreprise
    # (Phase 5 §6) — plusieurs NULL restent autorisés (rapports déposés avant l'introduction du
    # checksum), PostgreSQL ne les compare jamais égaux entre eux dans une contrainte UNIQUE.
    # (company_id, fiscal_year) est indexé mais jamais unique : plusieurs types de rapport et
    # plusieurs versions coexistent pour une même année (docs/ARCHITECTURE.md §3.2).
    __table_args__ = (
        UniqueConstraint(
            "company_id", "checksum_sha256", name="uq_esg_reports_company_checksum"
        ),
        Index("ix_esg_reports_company_fiscal_year", "company_id", "fiscal_year"),
        # Un seul brouillon ouvert par exercice et par type de rapport (tâche 1.5) : ouvrir deux
        # sessions de déclaration pour la même période serait une erreur de saisie, jamais utile.
        Index(
            "uq_esg_reports_one_draft_per_period",
            "company_id",
            "fiscal_year",
            "type",
            unique=True,
            postgresql_where=text("status = 'DRAFT'"),
        ),
        # Un brouillon n'a encore ni fichier ni date de dépôt ; tout autre statut en a toujours.
        CheckConstraint(
            "status = 'DRAFT' OR (source_file IS NOT NULL AND submitted_at IS NOT NULL)",
            name="ck_esg_reports_file_unless_draft",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = Field(foreign_key="companies.id", ondelete="CASCADE")
    type: ReportType = Field(sa_column=sa_enum_column(ReportType))
    channel: SubmissionChannel = Field(sa_column=sa_enum_column(SubmissionChannel))
    created_at: datetime = Field(default_factory=utcnow)
    # Moment du dépôt du fichier : nul tant que le rapport est un brouillon (DRAFT, tâche 1.5).
    submitted_at: datetime | None = Field(default=None)
    status: ReportStatus = Field(
        default=ReportStatus.SUBMITTED, sa_column=sa_enum_column(ReportStatus)
    )
    # Avancement du pipeline d'extraction, distinct du statut métier (docs/RENAME_PLAN.md §2.4) :
    # un rapport reste SUBMITTED pendant toute l'extraction, qu'elle soit en file, en cours,
    # terminée ou échouée.
    extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.QUEUED, sa_column=sa_enum_column(ExtractionStatus)
    )
    # Chemin de stockage du PDF déposé — nul tant que le rapport est un brouillon.
    source_file: str | None = Field(default=None)
    # Nom du fichier PDF tel que fourni par le client au dépôt, affiché tel quel dans les espaces
    # Entreprise/Admin/Auditeur à la place du type de rapport — jamais utilisé comme chemin de
    # stockage (voir _enregistrer_fichier, app/company/rapports.py). Nullable : les rapports
    # déposés avant cette colonne n'ont pas cette valeur.
    original_filename: str | None = Field(default=None)
    # Persisté dès le dépôt (Phase 4 §4.3). Nullable : les rapports déposés avant cette passe
    # n'ont pas cette valeur.
    fiscal_year: int | None = Field(default=None)
    # Champ interne réservé à l'accountability (voir aussi AuditOpinion.auditor_id) : jamais exposé
    # à l'Entreprise.
    auditor_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL", index=True
    )
    # Posée par affecter_auditeur (app/audit/assignment.py) au moment de l'affectation —
    # nécessaire pour calculer un retard d'audit (app/core/config.py::sla_audit_jours).
    assigned_at: datetime | None = Field(default=None)
    # Horodatages du pipeline d'extraction (Étape 5, Phase 6). extraction_error ne contient
    # jamais str(exception) (fuite potentielle de contenu sensible), seulement une chaîne de
    # classification fixe — voir app/ingestion/extractor.py. extraction_started_at est posé à
    # chaque entrée dans le pipeline : RUNNING au-delà de settings.extraction_timeout_minutes
    # signale un traitement interrompu.
    extraction_started_at: datetime | None = Field(default=None)
    extraction_finished_at: datetime | None = Field(default=None)
    extraction_error: str | None = Field(default=None)
    extraction_attempts: int = Field(default=0)
    # Versioning (Phase 4 §4.1) : une correction ne réécrit jamais l'original — elle crée une
    # nouvelle ligne, previous_report_id pointant vers celle qu'elle remplace.
    version: int = Field(default=1)
    previous_report_id: uuid.UUID | None = Field(
        default=None, foreign_key="esg_reports.id", ondelete="SET NULL", index=True
    )
    # Empreinte du contenu déposé (Phase 4 §4.2) — détecte un doublon avant tout traitement.
    checksum_sha256: str | None = Field(default=None, index=True)
    # Score ESG global auto-déclaré par l'entreprise dans sa propre synthèse — distinct du score
    # officiel (Score / official_score), calculé indépendamment par la plateforme. Toujours
    # accompagné de sa preuve documentaire (garantie G1 "aucune valeur sans preuve").
    declared_global_score: float | None = Field(default=None)
    declared_global_score_proof_id: uuid.UUID | None = Field(
        default=None, foreign_key="evidence.id", ondelete="SET NULL", index=True
    )
    # Chemin de stockage (app/core/storage.py) du dernier PDF de synthèse généré par la
    # plateforme (app/ingestion/synthesis_report.py) — remplacé à chaque régénération.
    synthesis_report_path: str | None = Field(default=None)
    # Score officiel dénormalisé, taux de couverture et empreinte de la configuration de
    # scoring utilisée — posés dans la transaction de validation (tâches 1.6 et 3.1).
    official_score: float | None = Field(default=None)
    coverage_rate: float | None = Field(default=None)
    config_hash: str | None = Field(default=None, max_length=64)

    company: "Company" = Relationship(back_populates="reports")
    auditor: Optional["User"] = Relationship(back_populates="audited_reports")
    metrics: list["ESGMetric"] = Relationship(back_populates="report")
    carbon_data: list["CarbonEmission"] = Relationship(back_populates="report")
    scores: list["Score"] = Relationship(back_populates="report")
    audit_opinions: list["AuditOpinion"] = Relationship(back_populates="report")
    declared_global_score_proof: Optional["Evidence"] = Relationship()
    coverages: list["MetricCoverage"] = Relationship(back_populates="report")


class Evidence(SQLModel, table=True):
    """Table `evidence` (docs/RENAME_PLAN.md §4, tâche 2.3) : extrait PDF prouvant une valeur
    extraite — aucune valeur sans preuve."""

    __tablename__ = "evidence"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_name: str
    year: int
    total_pages: int
    page_start: int
    page_end: int
    # Chemin relatif sous le stockage (app/core/storage.py), jamais absolu.
    excerpt_pdf_path: str

    metrics: list["ESGMetric"] = Relationship(back_populates="proof")
    carbon_emissions: list["CarbonEmission"] = Relationship(back_populates="proof")


class ESGMetric(SQLModel, table=True):
    """Table `esg_metrics` (docs/RENAME_PLAN.md §2.3). Un seul point de donnée par code et par
    rapport : l'extracteur dédoublonne avant insertion, la contrainte l'impose en base."""

    __tablename__ = "esg_metrics"
    __table_args__ = (
        UniqueConstraint("report_id", "metric_code", name="uq_esg_metrics_report_metric_code"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE")
    pillar: Pillar = Field(sa_column=sa_enum_column(Pillar))
    metric_code: str
    value: float
    unit: str
    method: DataMethod = Field(sa_column=sa_enum_column(DataMethod))
    proof_id: uuid.UUID = Field(
        foreign_key="evidence.id", ondelete="CASCADE", index=True
    )
    # Champs étendus de traçabilité (Phase 6) — renseignés par le LLM d'extraction quand
    # disponibles, jamais fabriqués : None reste None plutôt qu'une valeur inventée. raw_value
    # conserve la mise en forme d'origine (value est la version numérique normalisée) ;
    # section/proof_text donnent à l'Auditeur une trace vérifiable au-delà du simple numéro de
    # page ; value_year peut différer de l'année de reporting déclarée au dépôt.
    raw_value: str | None = Field(default=None)
    section: str | None = Field(default=None)
    proof_text: str | None = Field(default=None)
    value_year: int | None = Field(default=None)
    confidence: ConfidenceLevel | None = Field(
        default=None, sa_column=sa_enum_column(ConfidenceLevel, nullable=True)
    )
    # Correction par l'Auditeur (docs/WORKFLOWS.md §1.2) : la valeur extraite reste intacte,
    # override_value la remplace au calcul du score quand auditor_overridden est vrai.
    auditor_overridden: bool = Field(default=False)
    override_value: float | None = Field(default=None)
    override_reason: str | None = Field(default=None)
    overridden_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL", index=True
    )
    overridden_at: datetime | None = Field(default=None)

    report: ESGReport = Relationship(back_populates="metrics")
    proof: Evidence = Relationship(back_populates="metrics")
    discrepancy_flags: list["DiscrepancyFlag"] = Relationship(back_populates="metric")


class CarbonEmission(SQLModel, table=True):
    """Table `carbon_emissions` (docs/RENAME_PLAN.md §4, tâche 2.3). Scope, qualité PCAF et
    valeur sont bornés à la fois côté Pydantic et côté PostgreSQL (__table_args__) — un INSERT
    direct reste protégé par la contrainte SQL.

    pcaf_data_quality (1 = meilleure, 5 = pire) est dérivée de la méthode d'obtention à
    l'extraction (app/carbon/pcaf.py::qualite_donnee_pcaf) ; nulle quand elle ne peut pas l'être —
    jamais une valeur par défaut qui se ferait passer pour une vraie notation."""

    __tablename__ = "carbon_emissions"
    __table_args__ = (
        CheckConstraint("scope IN (1, 2, 3)", name="ck_carbon_emissions_scope"),
        # Nulle acceptée : un CHECK sur NULL n'échoue pas.
        CheckConstraint(
            "pcaf_data_quality BETWEEN 1 AND 5", name="ck_carbon_emissions_pcaf_data_quality_range"
        ),
        CheckConstraint("tonnes_co2e >= 0", name="ck_carbon_emissions_tonnes_non_negative"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE", index=True)
    scope: int = Field(ge=1, le=3)
    # Précision du Scope 2 (`market_based` / `location_based`), nulle quand le rapport ne la donne pas.
    ghg_category: str | None = None
    tonnes_co2e: float = Field(ge=0)
    year: int
    method: DataMethod = Field(sa_column=sa_enum_column(DataMethod))
    pcaf_data_quality: int | None = Field(default=None, ge=1, le=5)
    proof_id: uuid.UUID = Field(foreign_key="evidence.id", ondelete="CASCADE", index=True)
    # Traçabilité (Phase 6) — voir ESGMetric ci-dessus, même justification.
    raw_value: str | None = Field(default=None)
    section: str | None = Field(default=None)
    proof_text: str | None = Field(default=None)
    value_year: int | None = Field(default=None)
    confidence: ConfidenceLevel | None = Field(
        default=None, sa_column=sa_enum_column(ConfidenceLevel, nullable=True)
    )

    report: ESGReport = Relationship(back_populates="carbon_data")
    proof: Evidence = Relationship(back_populates="carbon_emissions")


class MetricCoverage(SQLModel, table=True):
    """Persiste, pour CHAQUE code de INDICATEURS_CIBLES (pas seulement les trouvés), ce que le
    LLM a réellement répondu à l'extraction. Sert deux besoins distincts avec la même donnée :
    signaler à l'écran qu'une donnée est absente plutôt que de la laisser silencieusement invisible
    (transparence, décision produit), et distinguer les 3 statuts (voir MetricCoverageStatus,
    app/core/enums.py) pour juger si la sélection adaptative de pages (app/ingestion/extractor.py)
    fait manquer des indicateurs sur un long rapport. Une ligne par (rapport, code) — remplacée à
    chaque nouvelle tentative d'extraction du même rapport (voir run_extraction_pipeline, même
    purge que ESGMetric)."""

    __tablename__ = "metric_coverage"
    __table_args__ = (
        UniqueConstraint("report_id", "metric_code", name="uq_metric_coverage_report_metric_code"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE")
    metric_code: str
    status: MetricCoverageStatus = Field(sa_column=sa_enum_column(MetricCoverageStatus))
    pages_examined: int

    report: ESGReport = Relationship(back_populates="coverages")


class DiscrepancyFlag(SQLModel, table=True):
    """Table `discrepancy_flags` (tâche 2.3) : écart signalé sur un indicateur précis — jamais
    uniquement sur un rapport entier."""

    __tablename__ = "discrepancy_flags"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    metric_id: uuid.UUID = Field(foreign_key="esg_metrics.id", ondelete="CASCADE", index=True)
    company_id: uuid.UUID = Field(foreign_key="companies.id", ondelete="CASCADE", index=True)
    nature: str
    status: str = Field(default="OUVERT")
    flagged_at: datetime = Field(default_factory=utcnow)

    metric: ESGMetric = Relationship(back_populates="discrepancy_flags")
    company: "Company" = Relationship(back_populates="discrepancy_flags")
