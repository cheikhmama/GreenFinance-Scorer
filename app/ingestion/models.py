"""Entités de persistance produites par le pipeline d'extraction documentaire.

ESGReport porte le cycle de vie documentaire (ReportStatus) et l'avancement de son extraction
(ExtractionStatus). Les entités qui en dérivent (ESGMetric, DonneeCarbone, PreuveDocumentaire —
Prompt 3.5 ; SignalementEcart — Prompt 3.8) sont exclusivement produites
par le pipeline automatique (Étapes 4 à 7) : un Auditeur les consulte et
les valide via AvisAudit (app/audit/models.py), il ne les crée jamais
lui-même — aucun champ ni table ici ne permet une saisie manuelle par
l'Auditeur.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    ExtractionStatus,
    MethodeDonnee,
    NiveauConfiance,
    Pilier,
    ReportStatus,
    StatutCouvertureIndicateur,
    TypeRapport,
    sa_enum_column,
)

if TYPE_CHECKING:
    from app.audit.models import AvisAudit
    from app.auth.models import Utilisateur
    from app.company.models import Company
    from app.scoring.models import ScoreESG


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
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = Field(foreign_key="companies.id", ondelete="CASCADE")
    type: TypeRapport = Field(sa_column=sa_enum_column(TypeRapport))
    channel: CanalDepot = Field(sa_column=sa_enum_column(CanalDepot))
    submitted_at: datetime = Field(default_factory=utcnow)
    status: ReportStatus = Field(
        default=ReportStatus.SUBMITTED, sa_column=sa_enum_column(ReportStatus)
    )
    # Avancement du pipeline d'extraction, distinct du statut métier (docs/RENAME_PLAN.md §2.4) :
    # un rapport reste SUBMITTED pendant toute l'extraction, qu'elle soit en file, en cours,
    # terminée ou échouée.
    extraction_status: ExtractionStatus = Field(
        default=ExtractionStatus.QUEUED, sa_column=sa_enum_column(ExtractionStatus)
    )
    source_file: str
    # Nom du fichier PDF tel que fourni par le client au dépôt, affiché tel quel dans les espaces
    # Entreprise/Admin/Auditeur à la place du type de rapport — jamais utilisé comme chemin de
    # stockage (voir _enregistrer_fichier, app/company/rapports.py). Nullable : les rapports
    # déposés avant cette colonne n'ont pas cette valeur.
    original_filename: str | None = Field(default=None)
    # Persisté dès le dépôt (Phase 4 §4.3). Nullable : les rapports déposés avant cette passe
    # n'ont pas cette valeur.
    fiscal_year: int | None = Field(default=None)
    # Champ interne réservé à l'accountability (voir aussi AvisAudit.auditeur_id) : jamais exposé
    # à l'Entreprise.
    auditor_id: uuid.UUID | None = Field(
        default=None, foreign_key="utilisateur.id", ondelete="SET NULL", index=True
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
    # officiel (ScoreESG / official_score), calculé indépendamment par la plateforme. Toujours
    # accompagné de sa preuve documentaire (garantie G1 "aucune valeur sans preuve").
    declared_global_score: float | None = Field(default=None)
    declared_global_score_proof_id: uuid.UUID | None = Field(
        default=None, foreign_key="preuve_documentaire.id", ondelete="SET NULL", index=True
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
    auditor: Optional["Utilisateur"] = Relationship(back_populates="rapports_audites")
    metrics: list["ESGMetric"] = Relationship(back_populates="report")
    carbon_data: list["DonneeCarbone"] = Relationship(back_populates="rapport")
    scores: list["ScoreESG"] = Relationship(back_populates="rapport")
    audit_opinions: list["AvisAudit"] = Relationship(back_populates="rapport")
    declared_global_score_proof: Optional["PreuveDocumentaire"] = Relationship()
    coverages: list["CouvertureIndicateur"] = Relationship(back_populates="rapport")


class PreuveDocumentaire(SQLModel, table=True):
    __tablename__ = "preuve_documentaire"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nom_document: str
    annee: int
    nombre_pages_total: int
    page_debut: int
    page_fin: int
    pdf_extrait_genere: str

    indicateurs: list["ESGMetric"] = Relationship(back_populates="proof")
    donnees_carbone: list["DonneeCarbone"] = Relationship(back_populates="preuve")


class ESGMetric(SQLModel, table=True):
    """Table `esg_metrics` (docs/RENAME_PLAN.md §2.3). Un seul point de donnée par code et par
    rapport : l'extracteur dédoublonne avant insertion, la contrainte l'impose en base."""

    __tablename__ = "esg_metrics"
    __table_args__ = (
        UniqueConstraint("report_id", "metric_code", name="uq_esg_metrics_report_metric_code"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    report_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE")
    pillar: Pilier = Field(sa_column=sa_enum_column(Pilier))
    metric_code: str
    value: float
    unit: str
    method: MethodeDonnee = Field(sa_column=sa_enum_column(MethodeDonnee))
    proof_id: uuid.UUID = Field(
        foreign_key="preuve_documentaire.id", ondelete="CASCADE", index=True
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
    confidence: NiveauConfiance | None = Field(
        default=None, sa_column=sa_enum_column(NiveauConfiance, nullable=True)
    )
    # Correction par l'Auditeur (docs/WORKFLOWS.md §1.2) : la valeur extraite reste intacte,
    # override_value la remplace au calcul du score quand auditor_overridden est vrai.
    auditor_overridden: bool = Field(default=False)
    override_value: float | None = Field(default=None)
    override_reason: str | None = Field(default=None)
    overridden_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="utilisateur.id", ondelete="SET NULL", index=True
    )
    overridden_at: datetime | None = Field(default=None)

    report: ESGReport = Relationship(back_populates="metrics")
    proof: PreuveDocumentaire = Relationship(back_populates="indicateurs")
    discrepancy_flags: list["SignalementEcart"] = Relationship(back_populates="indicateur")


class DonneeCarbone(SQLModel, table=True):
    """Scope/qualité PCAF/valeur sont bornés à la fois côté Pydantic (Field ci-dessous) et côté
    PostgreSQL (__table_args__, Phase 5 §6) — un INSERT direct ou un futur endpoint qui
    contournerait le modèle Pydantic reste protégé par la contrainte SQL."""

    __tablename__ = "donnee_carbone"
    __table_args__ = (
        CheckConstraint("scope IN (1, 2, 3)", name="ck_donnee_carbone_scope_valide"),
        CheckConstraint(
            "score_qualite_pcaf BETWEEN 1 AND 5", name="ck_donnee_carbone_pcaf_borne"
        ),
        CheckConstraint(
            "valeur_tonnes_co2e >= 0", name="ck_donnee_carbone_valeur_non_negative"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE", index=True)
    scope: int = Field(ge=1, le=3)
    categorie_ges: str | None = None
    valeur_tonnes_co2e: float = Field(ge=0)
    annee: int
    methode: MethodeDonnee = Field(sa_column=sa_enum_column(MethodeDonnee))
    score_qualite_pcaf: int = Field(ge=1, le=5)
    preuve_id: uuid.UUID = Field(foreign_key="preuve_documentaire.id")
    # Champs étendus de traçabilité (Phase 6) — voir ESGMetric ci-dessus pour la justification,
    # identique ici.
    valeur_brute: str | None = Field(default=None)
    section: str | None = Field(default=None)
    citation_source: str | None = Field(default=None)
    annee_valeur: int | None = Field(default=None)
    confiance: NiveauConfiance | None = Field(
        default=None, sa_column=sa_enum_column(NiveauConfiance, nullable=True)
    )

    rapport: ESGReport = Relationship(back_populates="carbon_data")
    preuve: PreuveDocumentaire = Relationship(back_populates="donnees_carbone")


class CouvertureIndicateur(SQLModel, table=True):
    """Persiste, pour CHAQUE code de INDICATEURS_CIBLES (pas seulement les trouvés), ce que le
    LLM a réellement répondu à l'extraction. Sert deux besoins distincts avec la même donnée :
    signaler à l'écran qu'une donnée est absente plutôt que de la laisser silencieusement invisible
    (transparence, décision produit), et distinguer les 3 statuts (voir StatutCouvertureIndicateur,
    app/core/enums.py) pour juger si la sélection adaptative de pages (app/ingestion/extractor.py)
    fait manquer des indicateurs sur un long rapport. Une ligne par (rapport, code) — remplacée à
    chaque nouvelle tentative d'extraction du même rapport (voir run_extraction_pipeline, même
    purge que ESGMetric)."""

    __tablename__ = "couverture_indicateur"
    __table_args__ = (
        UniqueConstraint("rapport_id", "code", name="uq_couverture_indicateur_rapport_code"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    rapport_id: uuid.UUID = Field(foreign_key="esg_reports.id", ondelete="CASCADE")
    code: str
    statut: StatutCouvertureIndicateur = Field(sa_column=sa_enum_column(StatutCouvertureIndicateur))
    pages_examinees: int

    rapport: ESGReport = Relationship(back_populates="coverages")


class SignalementEcart(SQLModel, table=True):
    """Écart signalé sur un indicateur précis — jamais uniquement sur un
    rapport entier."""

    __tablename__ = "signalement_ecart"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    indicateur_id: uuid.UUID = Field(foreign_key="esg_metrics.id", ondelete="CASCADE", index=True)
    entreprise_id: uuid.UUID = Field(foreign_key="companies.id", ondelete="CASCADE", index=True)
    nature_ecart: str
    statut: str = Field(default="OUVERT")
    date_signalement: datetime = Field(default_factory=utcnow)

    indicateur: ESGMetric = Relationship(back_populates="discrepancy_flags")
    entreprise: "Company" = Relationship(back_populates="discrepancy_flags")
