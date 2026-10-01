"""Schémas Pydantic d'entrée/sortie du module d'extraction documentaire.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).

IndicateurExtrait / ExtractionEntreprise forment le contrat de tool-use forcé de l'appel Claude
(app/ingestion/extractor.py) — portés VERBATIM depuis notebooks/_prompt_4_4_extraction.py, où ils
ont été validés (mêmes champs, mêmes descriptions) : ne pas les modifier sans revalider le
protocole d'extraction.

Contrat HTTP en anglais depuis la tâche 4.7 (docs/RENAME_PLAN.md §3e) : les champs JSON portent
les noms des attributs d'ESGReport / ESGMetric / CarbonEmission / Evidence / MetricCoverage, lus
directement (from_attributes) — plus aucune traduction intermédiaire.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.enums import (
    ConfidenceLevel,
    DataMethod,
    MetricCoverageStatus,
    Pillar,
    ReportStatus,
    ReportType,
    SubmissionChannel,
)
from app.scoring.schemas import ScoreESGPublic


class IndicateurExtrait(BaseModel):
    code: str
    valeur: float | None = Field(
        default=None, description="Valeur numerique trouvee, null si absente des extraits fournis"
    )
    unite: str | None = Field(
        default=None, description="Unite de la valeur, telle qu'ecrite dans le document"
    )
    page_source: int | None = Field(
        default=None,
        description="Numero de page physique (indique par --- Page N ---) ou la valeur a ete trouvee",
    )
    trouve: bool = Field(
        description="False si l'indicateur n'apparait pas explicitement dans les extraits fournis"
    )
    # Champs étendus (Phase 6) — tous optionnels, jamais fabriqués si le LLM ne les fournit pas
    # (None reste None, jamais une valeur inventée à la place).
    valeur_brute: str | None = Field(
        default=None, description="Valeur telle qu'ecrite litteralement dans le document, avec sa mise en forme d'origine"
    )
    section: str | None = Field(
        default=None, description="Titre ou rubrique la plus proche visible dans les extraits fournis"
    )
    citation_source: str | None = Field(
        default=None, description="Courte citation verbatim des extraits fournis qui justifie la valeur"
    )
    annee_valeur: int | None = Field(
        default=None,
        description="Annee a laquelle se rapporte la valeur telle qu'indiquee dans le document",
    )
    confiance: ConfidenceLevel | None = Field(
        default=None, description="Niveau de confiance du LLM dans la clarte de la donnee trouvee"
    )
    non_divulgation_citation: str | None = Field(
        default=None,
        description=(
            "Citation verbatim d'une declaration explicite de non-divulgation de cet indicateur "
            "cette annee. Ne remplir que si le document le declare explicitement, jamais sur une "
            "simple absence silencieuse."
        ),
    )
    non_divulgation_page: int | None = Field(
        default=None, description="Page ou se trouve la declaration de non-divulgation citee ci-dessus"
    )


class ExtractionEntreprise(BaseModel):
    entreprise: str
    indicateurs: list[IndicateurExtrait]


class RapportESGPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    type: ReportType
    channel: SubmissionChannel
    created_at: datetime
    # Nuls pour un brouillon (DRAFT, tâche 1.5) : ni fichier ni dépôt tant que la déclaration
    # n'est pas soumise.
    submitted_at: datetime | None
    # Statut unique, extraction comprise (tâche 5.1). L'espace Entreprise regroupe les états
    # d'examen en un seul libellé ; les rôles internes voient l'état détaillé.
    status: ReportStatus
    source_file: str | None
    original_filename: str | None
    fiscal_year: int | None
    extraction_finished_at: datetime | None
    extraction_error: str | None
    extraction_attempts: int
    version: int
    previous_report_id: uuid.UUID | None


class PreuveDocumentairePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_name: str
    year: int
    total_pages: int
    page_start: int
    page_end: int
    excerpt_pdf_path: str


class IndicateurESGDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pillar: Pillar
    metric_code: str
    value: float
    unit: str
    method: DataMethod
    proof: PreuveDocumentairePublic
    raw_value: str | None
    section: str | None
    proof_text: str | None
    value_year: int | None
    confidence: ConfidenceLevel | None


class DonneeCarboneDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: int
    ghg_category: str | None
    tonnes_co2e: float
    year: int
    method: DataMethod
    # Nulle quand la qualité PCAF ne peut pas être dérivée (tâche 2.3) — plus de placeholder 3.
    pcaf_data_quality: int | None
    proof: PreuveDocumentairePublic
    raw_value: str | None
    section: str | None
    proof_text: str | None
    value_year: int | None
    confidence: ConfidenceLevel | None


class CouvertureIndicateurPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_code: str
    status: MetricCoverageStatus


class CouvertureResume(BaseModel):
    """Transparence sur ce qui manque (décision produit, voir app/ingestion/completeness.py) :
    total_targets/found permettent d'afficher "14/23 indicateurs communiqués" plutôt que de
    laisser deviner une absence à partir d'un tiret muet ; missing_codes liste tout code dont le
    statut n'est pas TROUVE (NON_TROUVE et ABSENT_CONFIRME y comptent tous les deux comme
    "manquant" — la distinction entre les deux reste disponible via CouvertureIndicateurPublic.status
    pour qui a besoin de savoir si l'absence a été confirmée ou seulement pas encore trouvée)."""

    total_targets: int
    found: int
    missing_codes: list[str]


class RapportESGDetail(RapportESGPublic):
    """Étend RapportESGPublic avec les données extraites. Ne contient JAMAIS l'avis de l'auditeur
    (app/audit/schemas.py::AuditOpinion*) — l'auditeur_id ne doit jamais pouvoir fuiter vers une
    réponse Entreprise par accident de composition de schéma, pas seulement par discipline."""

    metrics: list[IndicateurESGDetail]
    carbon_data: list[DonneeCarboneDetail]
    # Score global auto-déclaré par l'entreprise (distinct du score officiel Score, calculé
    # indépendamment par la plateforme) — voir app/ingestion/models.py::ESGReport pour la
    # justification de ce champ direct plutôt qu'un ESGMetric.
    declared_global_score: float | None
    declared_global_score_proof: PreuveDocumentairePublic | None
    # Le score OFFICIEL, calculé par la plateforme (app/scoring/engine.py::score_public) —
    # jamais confondu avec declared_global_score ci-dessus. None tant que le rapport n'a pas
    # encore été validé par un Auditeur/Admin (calculer_score ne tourne qu'à ce moment-là,
    # voir app/admin/review_queue.py::valider_rapport) — pas une absence de donnée, un état réel
    # du cycle de vie du rapport.
    # Jamais lu depuis ESGReport (dont `official_score` est le float dénormalisé) : les routes le
    # posent par model_copy(update=...) ; l'alias de validation empêche from_attributes de le lire.
    official_score: ScoreESGPublic | None = Field(
        default=None, validation_alias="official_score_public"
    )
    # exclude=True : source du computed_field ci-dessous, jamais sérialisé tel quel
    # (alimenté par la relation SQLModel ESGReport.coverages).
    coverages: list[CouvertureIndicateurPublic] = Field(default_factory=list, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def coverage(self) -> CouvertureResume:
        return CouvertureResume(
            total_targets=len(self.coverages),
            found=sum(
                1 for c in self.coverages if c.status == MetricCoverageStatus.TROUVE
            ),
            missing_codes=[
                c.metric_code for c in self.coverages if c.status != MetricCoverageStatus.TROUVE
            ],
        )
