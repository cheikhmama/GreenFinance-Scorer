"""Schémas Pydantic d'entrée/sortie du module d'extraction documentaire.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).

IndicateurExtrait / ExtractionEntreprise forment le contrat de tool-use forcé de l'appel Claude
(app/ingestion/extractor.py) — portés VERBATIM depuis notebooks/_prompt_4_4_extraction.py, où ils
ont été validés (mêmes champs, mêmes descriptions) : ne pas les modifier sans revalider le
protocole d'extraction.

Contrat HTTP inchangé pendant le renommage anglais (docs/RENAME_PLAN.md §1, règle 3) : les champs
JSON restent en français ; RapportESGPublic/RapportESGDetail/IndicateurESGDetail traduisent
explicitement ESGReport/ESGMetric vers ce contrat. Exception assumée : les valeurs de `statut`
sont celles de ReportStatus (le découpage statut / extraction change leur sens).
"""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.core.enums import (
    CanalDepot,
    ExtractionStatus,
    MethodeDonnee,
    NiveauConfiance,
    Pillar,
    ReportStatus,
    StatutCouvertureIndicateur,
    TypeRapport,
)
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
    MetricCoverage,
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
    confiance: NiveauConfiance | None = Field(
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


def rapport_vers_contrat(rapport: ESGReport) -> dict[str, Any]:
    """Point unique de traduction ESGReport -> champs JSON historiques (attributs scalaires
    seulement : les relations ne sont chargées que par RapportESGDetail, jamais pour une liste)."""
    return {
        "id": rapport.id,
        "entreprise_id": rapport.company_id,
        "type": rapport.type,
        "canal": rapport.channel,
        "date_creation": rapport.created_at,
        "date_depot": rapport.submitted_at,
        "statut": rapport.status,
        "statut_extraction": rapport.extraction_status,
        "fichier_source": rapport.source_file,
        "nom_fichier_origine": rapport.original_filename,
        "annee_reporting": rapport.fiscal_year,
        "extraction_terminee_le": rapport.extraction_finished_at,
        "extraction_erreur": rapport.extraction_error,
        "tentatives_extraction": rapport.extraction_attempts,
        "version": rapport.version,
        "rapport_precedent_id": rapport.previous_report_id,
    }


class RapportESGPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Relations à ajouter au contrat traduit (surchargé par RapportESGDetail) : nom JSON ->
    # attribut d'ESGReport.
    _relations_contrat: ClassVar[dict[str, str]] = {}

    @model_validator(mode="before")
    @classmethod
    def _depuis_rapport(cls, data: Any) -> Any:
        if not isinstance(data, ESGReport):
            return data
        contrat = rapport_vers_contrat(data)
        for nom_json, attribut in cls._relations_contrat.items():
            contrat[nom_json] = getattr(data, attribut)
        return contrat

    id: uuid.UUID
    entreprise_id: uuid.UUID
    type: TypeRapport
    canal: CanalDepot
    date_creation: datetime
    # Nuls pour un brouillon (DRAFT, tâche 1.5) : ni fichier ni dépôt tant que la déclaration
    # n'est pas soumise.
    date_depot: datetime | None
    statut: ReportStatus
    # Avancement de l'extraction, distinct du statut métier (ExtractionStatus) — ajouté au
    # contrat avec le découpage de l'ancien statut unique, pour que le frontend distingue un
    # rapport en file, en cours, extrait ou en échec sans le déduire des horodatages.
    statut_extraction: ExtractionStatus
    fichier_source: str | None
    nom_fichier_origine: str | None
    annee_reporting: int | None
    extraction_terminee_le: datetime | None
    extraction_erreur: str | None
    tentatives_extraction: int
    version: int
    rapport_precedent_id: uuid.UUID | None


class PreuveDocumentairePublic(BaseModel):
    """Contrat JSON historique d'une Evidence (docs/RENAME_PLAN.md §1, règle 3)."""

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _depuis_evidence(cls, data: Any) -> Any:
        if not isinstance(data, Evidence):
            return data
        return {
            "id": data.id,
            "nom_document": data.document_name,
            "annee": data.year,
            "nombre_pages_total": data.total_pages,
            "page_debut": data.page_start,
            "page_fin": data.page_end,
            "pdf_extrait_genere": data.excerpt_pdf_path,
        }

    id: uuid.UUID
    nom_document: str
    annee: int
    nombre_pages_total: int
    page_debut: int
    page_fin: int
    pdf_extrait_genere: str


class IndicateurESGDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _depuis_metric(cls, data: Any) -> Any:
        if not isinstance(data, ESGMetric):
            return data
        return {
            "id": data.id,
            "pilier": data.pillar,
            "code": data.metric_code,
            "valeur": data.value,
            "unite": data.unit,
            "methode": data.method,
            "preuve": data.proof,
            "valeur_brute": data.raw_value,
            "section": data.section,
            "citation_source": data.proof_text,
            "annee_valeur": data.value_year,
            "confiance": data.confidence,
        }

    id: uuid.UUID
    pilier: Pillar
    code: str
    valeur: float
    unite: str
    methode: MethodeDonnee
    preuve: PreuveDocumentairePublic
    valeur_brute: str | None
    section: str | None
    citation_source: str | None
    annee_valeur: int | None
    confiance: NiveauConfiance | None


class DonneeCarboneDetail(BaseModel):
    """Contrat JSON historique d'une CarbonEmission (docs/RENAME_PLAN.md §1, règle 3)."""

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _depuis_emission(cls, data: Any) -> Any:
        if not isinstance(data, CarbonEmission):
            return data
        return {
            "id": data.id,
            "scope": data.scope,
            "categorie_ges": data.ghg_category,
            "valeur_tonnes_co2e": data.tonnes_co2e,
            "annee": data.year,
            "methode": data.method,
            "score_qualite_pcaf": data.pcaf_data_quality,
            "preuve": data.proof,
            "valeur_brute": data.raw_value,
            "section": data.section,
            "citation_source": data.proof_text,
            "annee_valeur": data.value_year,
            "confiance": data.confidence,
        }

    id: uuid.UUID
    scope: int
    categorie_ges: str | None
    valeur_tonnes_co2e: float
    annee: int
    methode: MethodeDonnee
    # Nulle quand la qualité PCAF ne peut pas être dérivée (tâche 2.3) — plus de placeholder 3.
    score_qualite_pcaf: int | None
    preuve: PreuveDocumentairePublic
    valeur_brute: str | None
    section: str | None
    citation_source: str | None
    annee_valeur: int | None
    confiance: NiveauConfiance | None


class CouvertureIndicateurPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _depuis_couverture(cls, data: Any) -> Any:
        if not isinstance(data, MetricCoverage):
            return data
        return {"code": data.metric_code, "statut": data.status}

    code: str
    statut: StatutCouvertureIndicateur


class CouvertureResume(BaseModel):
    """Transparence sur ce qui manque (décision produit, voir app/ingestion/completeness.py) :
    total_cibles/trouves permettent d'afficher "14/23 indicateurs communiqués" plutôt que de
    laisser deviner une absence à partir d'un tiret muet ; codes_manquants liste tout code dont le
    statut n'est pas TROUVE (NON_TROUVE et ABSENT_CONFIRME y comptent tous les deux comme
    "manquant" — la distinction entre les deux reste disponible via CouvertureIndicateurPublic.statut
    pour qui a besoin de savoir si l'absence a été confirmée ou seulement pas encore trouvée)."""

    total_cibles: int
    trouves: int
    codes_manquants: list[str]


class RapportESGDetail(RapportESGPublic):
    """Étend RapportESGPublic avec les données extraites. Ne contient JAMAIS l'avis de l'auditeur
    (app/audit/schemas.py::AvisAudit*) — l'auditeur_id ne doit jamais pouvoir fuiter vers une
    réponse Entreprise par accident de composition de schéma, pas seulement par discipline."""

    _relations_contrat: ClassVar[dict[str, str]] = {
        "indicateurs": "metrics",
        "donnees_carbone": "carbon_data",
        "score_global_declare": "declared_global_score",
        "score_global_declare_preuve": "declared_global_score_proof",
        "couvertures": "coverages",
    }

    indicateurs: list[IndicateurESGDetail]
    donnees_carbone: list[DonneeCarboneDetail]
    # Score global auto-déclaré par l'entreprise (distinct du score officiel Score, calculé
    # indépendamment par la plateforme) — voir app/ingestion/models.py::ESGReport pour la
    # justification de ce champ direct plutôt qu'un ESGMetric.
    score_global_declare: float | None
    score_global_declare_preuve: PreuveDocumentairePublic | None
    # Le score OFFICIEL, calculé par la plateforme (app/scoring/engine.py::score_public) —
    # jamais confondu avec score_global_declare ci-dessus. None tant que le rapport n'a pas
    # encore été validé par un Auditeur/Admin (calculer_score ne tourne qu'à ce moment-là,
    # voir app/admin/review_queue.py::valider_rapport) — pas une absence de donnée, un état réel
    # du cycle de vie du rapport.
    score_officiel: ScoreESGPublic | None = None
    # exclude=True : source du computed_field ci-dessous, jamais sérialisé tel quel
    # (ESGReport.coverages, la relation SQLModel, alimente ce champ via _relations_contrat).
    couvertures: list[CouvertureIndicateurPublic] = Field(default_factory=list, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def couverture(self) -> CouvertureResume:
        return CouvertureResume(
            total_cibles=len(self.couvertures),
            trouves=sum(
                1 for c in self.couvertures if c.statut == StatutCouvertureIndicateur.TROUVE
            ),
            codes_manquants=[
                c.code for c in self.couvertures if c.statut != StatutCouvertureIndicateur.TROUVE
            ],
        )
