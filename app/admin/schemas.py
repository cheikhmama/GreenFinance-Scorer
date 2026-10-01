"""Schémas Pydantic d'entrée/sortie du module Administrateur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.auth.schemas import EmailNormalise
from app.company.identifiers import isin_valide, lei_valide
from app.company.schemas import EntreprisePublic
from app.core.enums import (
    AnalysisStatus,
    Currency,
    KycCheckResult,
    ProjectStatus,
    RegistrationStatus,
    ReportStatus,
    Role,
)


class AffecterAuditeurRequest(BaseModel):
    auditor_id: uuid.UUID


class ModifierEntrepriseAdminRequest(BaseModel):
    """Remplace entièrement le profil d'une entreprise (identité, description, site officiel,
    montant minimum) — jamais un patch partiel champ par champ, même principe que
    CreerUtilisateurRequest pour nom_entreprise/secteur/pays. Le logo suit un circuit séparé
    (POST/DELETE /admin/entreprises/{id}/logo, voir plus bas) : un fichier binaire validé par sa
    signature réelle n'a pas sa place dans un payload JSON de chaîne libre. montant_minimum_
    investissement et devise_montant_minimum se renseignent toujours ensemble ou se vident tous
    les deux ensemble, jamais un montant minimum sans sa devise (voir app/company/models.py)."""

    name: str
    sector: str
    country: str
    description: str | None = None
    website: str | None = None
    minimum_investment_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=20, decimal_places=2
    )
    minimum_investment_currency: Currency | None = None

    @field_validator("name", "sector", "country")
    @classmethod
    def _verifier_non_vide(cls, valeur: str) -> str:
        valeur = valeur.strip()
        if not valeur:
            raise ValueError("Ce champ ne peut pas être vide.")
        return valeur

    @model_validator(mode="after")
    def _verifier_paire_montant_devise(self) -> "ModifierEntrepriseAdminRequest":
        if (self.minimum_investment_amount is None) != (self.minimum_investment_currency is None):
            raise ValueError(
                "montant_minimum_investissement et devise_montant_minimum doivent être fournis "
                "ensemble ou omis ensemble."
            )
        return self


class DecisionAdminRequest(BaseModel):
    comment: str | None = None


class CreerUtilisateurRequest(BaseModel):
    email: EmailNormalise
    # Nom de la personne ou de l'institution titulaire du compte (Utilisateur.nom), distinct de
    # nom_entreprise ci-dessous (le nom de l'Entreprise elle-même, requis seulement quand
    # role == ENTREPRISE). Optionnel : l'Administrateur ne le saisit pas systématiquement, voir
    # creer_utilisateur() pour la valeur déduite de l'e-mail dans ce cas.
    name: str | None = None
    role: Role
    # Requis uniquement quand role == ENTREPRISE — le profil Entreprise (app/company/models.py)
    # est créé dans le même geste, conformément à la règle actée en Phase 0 (« Entreprise — créée
    # par l'Administrateur, provisioning »). Ignorés pour tout autre rôle.
    company_name: str | None = None
    sector: str | None = None
    country: str | None = None


class UtilisateurCree(BaseModel):
    """Réponse de la création d'un compte — jamais de mot de passe ici : un lien d'activation
    est envoyé par e-mail à la personne titulaire (voir app/admin/utilisateurs.py::creer_utilisateur
    et app/auth/activation.py)."""

    id: uuid.UUID
    email: str
    name: str
    role: Role
    created_at: datetime
    active: bool


class EntrepriseAdmin(EntreprisePublic):
    """Vue Administrateur d'une entreprise, quel que soit son statut — contrairement à
    EntreprisePublic (renvoyée à l'Entreprise elle-même), expose utilisateur_id : savoir si un
    compte est rattaché est précisément ce dont l'Administrateur a besoin pour distinguer une
    entreprise gérée en autonomie d'une entreprise sans compte (ex. fiche de référence, ou
    provisionnée avant qu'un compte ne lui soit rattaché — voir app/company/models.py)."""

    owner_user_id: uuid.UUID | None
    report_count: int
    latest_report_status: ReportStatus | None
    # Permet au frontend de lier "Voir le rapport"/"Valider" directement au rapport le plus
    # récent, sans détour par la liste des rapports — None si aucun rapport déposé.
    latest_report_id: uuid.UUID | None


class JournalAuditPublic(BaseModel):
    """Vue Administrateur d'une entrée du journal d'audit — aucun champ sensible à masquer, la
    table elle-même ne contient jamais de secret (voir app/core/audit.py)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None
    occurred_at: datetime
    result: str
    old_value: str | None
    new_value: str | None
    correlation_id: str | None


class TableauDeBordAdmin(BaseModel):
    """Indicateurs agrégés du tableau de bord Administrateur (voir app/admin/dashboard.py)."""

    registered_companies: int
    submitted_reports: int
    validated_reports: int
    rejected_reports: int
    published_companies: int
    overdue_audits: int
    reports_to_assign: int
    pending_decisions: int
    republication_requests: int
    pending_users: int
    # États incohérents/orphelins qu'aucune file normale ne surface (voir
    # app/admin/review_queue.py::lister_rapports_echec_extraction/lister_rapports_orphelins_en_validation)
    # — jamais silencieusement ignorés, même quand ils sont rares ou (aujourd'hui) inatteignables
    # via le seul parcours applicatif normal.
    failed_extraction_reports: int
    orphan_reports: int
    # Effectifs de comptes actifs par rôle — pas de champ "entreprises" ici, voir
    # entreprises_inscrites ci-dessus, la mesure déjà pertinente pour ce rôle.
    active_admins: int
    active_auditors: int
    active_investors: int
    active_researchers: int
    active_institutions: int


class ScoreVerificationAdmin(BaseModel):
    """Aperçu, sans rien persister, de si un rapport PENDING_DECISION pourrait être scoré —
    affiché avant que l'Admin ne clique Valider (voir app/scoring/engine.py::apercu_score),
    plutôt que de le laisser découvrir l'échec après coup. `calculable` est faux aussi quand la
    couverture est sous le minimum de la méthodologie (tâche 3.1)."""

    computable: bool
    coverage_rate: float | None = None
    min_coverage: float | None = None


class ScoreRecalculeAdmin(BaseModel):
    """Réponse de POST /admin/rapports/{id}/recalculer-score : les colonnes du Score recalculé,
    dont la couverture."""

    id: uuid.UUID
    report_id: uuid.UUID
    config_id: uuid.UUID
    global_score: float
    environmental_score: float | None
    social_score: float | None
    governance_score: float | None
    coverage_rate: float | None
    computed_at: datetime


class StatistiquesAuditeursAdmin(BaseModel):
    """Voir app/audit/assignment.py::statistiques_charge_globale — comptes_actifs et
    audits_en_retard vivent déjà dans TableauDeBordAdmin, pas répétés ici."""

    assigned_reports: int
    opinions_submitted: int


class StatistiquesInvestisseursAdmin(BaseModel):
    """Voir app/investor/portfolio.py::statistiques_admin — comptes_actifs vit déjà dans
    TableauDeBordAdmin, pas répété ici."""

    active_portfolios: int
    declared_positions: int
    distinct_companies: int


class StatistiquesChercheursAdmin(BaseModel):
    """Voir app/researcher/analyses.py::statistiques_admin — comptes_actifs vit déjà dans
    TableauDeBordAdmin, pas répété ici."""

    researchers_on_open_projects: int
    draft_analyses: int
    submitted_analyses: int
    approved_analyses: int
    analyses_changes_requested: int


class StatistiquesInstitutionsAdmin(BaseModel):
    """Voir app/institution/projets.py::statistiques_admin — comptes_actifs vit déjà dans
    TableauDeBordAdmin, pas répété ici."""

    open_projects: int
    closed_projects: int
    pending_invitations: int
    analyses_to_review: int


class ApercuActeursAdmin(BaseModel):
    """Voir app/admin/apercu.py::construire_apercu_acteurs."""

    auditors: StatistiquesAuditeursAdmin
    investors: StatistiquesInvestisseursAdmin
    researchers: StatistiquesChercheursAdmin
    institutions: StatistiquesInstitutionsAdmin


class TrancheScorePublic(BaseModel):
    lower_bound: int
    upper_bound: int
    company_count: int


class PerformanceESGAdmin(BaseModel):
    """Voir app/admin/apercu.py::calculer_performance_esg — score_*_moyen est None quand aucune
    entreprise du périmètre n'a de valeur exploitable pour ce pilier, jamais 0."""

    average_global_score: float | None
    average_environmental_score: float | None
    average_social_score: float | None
    average_governance_score: float | None
    companies_with_score: int
    companies_in_scope: int
    distribution: list[TrancheScorePublic]


class EntrepriseAvecScoreAdmin(BaseModel):
    """Une ligne du détail derrière les cartes de performance ESG — score_* à None quand
    l'entreprise n'a pas de score admissible, jamais 0 (voir PerformanceESGAdmin)."""

    id: uuid.UUID
    name: str
    sector: str
    country: str
    global_score: float | None
    environmental_score: float | None
    social_score: float | None
    governance_score: float | None


class ChargeAuditeurAdmin(BaseModel):
    """Une ligne du détail derrière "Dossiers affectés" (app/audit/assignment.py::
    lister_charge_auditeurs)."""

    auditor_id: uuid.UUID
    email: str
    assigned_reports: int
    overdue_reports: int
    opinions_submitted: int


class PortefeuilleAdmin(BaseModel):
    """Une ligne du détail derrière "Portefeuilles non archivés" (app/investor/portfolio.py::
    lister_portefeuilles_admin). montant_total dans devise_reference, jamais additionné entre
    portefeuilles de devises différentes."""

    id: uuid.UUID
    name: str
    investor_email: str
    reference_currency: Currency
    position_count: int
    total_amount: float
    created_at: datetime


class AnalyseAdmin(BaseModel):
    """Une ligne du détail derrière "Analyses par statut" (app/researcher/analyses.py::
    lister_analyses_admin). Une ligne = une version précise, jamais fusionnée avec ses versions
    précédentes/suivantes (voir Analysis.previous_analysis_id)."""

    id: uuid.UUID
    title: str
    status: AnalysisStatus
    version: int
    researcher_email: str
    project_name: str
    created_at: datetime
    submitted_at: datetime | None
    decided_at: datetime | None


class ProjetAdmin(BaseModel):
    """Une ligne du détail derrière "Projets ouverts/clôturés" (app/institution/projets.py::
    lister_projets_admin)."""

    id: uuid.UUID
    name: str
    status: ProjectStatus
    institution_email: str
    researcher_count: int
    created_at: datetime
    deadline: datetime | None
    closed_at: datetime | None


class OnboardingDecision(str, Enum):
    APPROVE = "approve"
    # Tâche 5.3 : la demande passe INFO_REQUESTED, le demandeur répond depuis sa page de suivi.
    REQUEST_INFO = "request_info"
    REJECT = "reject"


class CompanyOnboardingRequest(BaseModel):
    """PATCH /admin/companies/{id}/onboard (tâches 1.4 et 5.3, contrat JSON en anglais). Un refus
    exige un motif (`reason`), une demande d'informations un message (`message`) : l'un comme
    l'autre est transmis au demandeur par e-mail et reste lisible sur sa page de suivi."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision: OnboardingDecision
    reason: str | None = Field(default=None, max_length=1000)
    message: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _texte_requis(self) -> "CompanyOnboardingRequest":
        if self.decision == OnboardingDecision.REJECT and not self.reason:
            raise ValueError("Un motif est requis pour refuser une inscription.")
        if self.decision == OnboardingDecision.REQUEST_INFO and not self.message:
            raise ValueError("Un message est requis pour demander des informations.")
        return self


class CompanyOnboardingResult(BaseModel):
    """`status` vaut ACTIVE après validation, INFO_REQUESTED après une demande d'informations,
    REJECTED après refus (tâche 5.2 : l'inscription refusée est conservée, plus supprimée)."""

    company_id: uuid.UUID
    decision: OnboardingDecision
    status: RegistrationStatus
    onboarded_at: datetime | None


class CompanyIdentifiersRequest(BaseModel):
    """PATCH /admin/companies/{id}/identifiers (tâche 2.2, contrat JSON en anglais). Seuls les
    champs présents dans le corps changent ; `null` efface l'identifiant. Distinct de la
    modification du profil (remplacement complet) pour qu'un formulaire qui ignore ces champs ne
    les efface jamais."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    isin: str | None = None
    lei: str | None = None
    ticker: str | None = Field(default=None, max_length=20)

    @field_validator("isin")
    @classmethod
    def _isin(cls, valeur: str | None) -> str | None:
        if not valeur:
            return None
        valeur = valeur.replace(" ", "").upper()
        if not isin_valide(valeur):
            raise ValueError("ISIN invalide (12 caractères, chiffre de contrôle incorrect).")
        return valeur

    @field_validator("lei")
    @classmethod
    def _lei(cls, valeur: str | None) -> str | None:
        if not valeur:
            return None
        valeur = valeur.replace(" ", "").upper()
        if not lei_valide(valeur):
            raise ValueError("LEI invalide (20 caractères, chiffres de contrôle incorrects).")
        return valeur

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, valeur: str | None) -> str | None:
        if not valeur:
            return None
        valeur = valeur.replace(" ", "").upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}", valeur):
            raise ValueError("Ticker invalide (lettres, chiffres, point ou tiret).")
        return valeur


class CompanyIdentifiers(BaseModel):
    company_id: uuid.UUID
    isin: str | None
    lei: str | None
    ticker: str | None


class CompanyFinancialsRequest(BaseModel):
    """PUT /admin/companies/{id}/financials (tâche 2.3, contrat JSON en anglais) : les
    données financières dont le moteur PCAF a besoin (docs/WORKFLOWS.md §2.4). Chiffre d'affaires
    pour la WACI, EVIC (valeur d'entreprise trésorerie incluse) pour le facteur d'attribution.
    Chaque montant va de pair avec sa devise ; la date de l'EVIC est facultative mais affichée à
    côté des émissions, pour juger de l'écart entre les deux exercices. Remplacement complet : un
    champ omis vaut null."""

    model_config = ConfigDict(extra="forbid")

    revenue: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=2)
    revenue_currency: Currency | None = None
    enterprise_value: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=2)
    enterprise_value_currency: Currency | None = None
    enterprise_value_as_of: date | None = None

    @model_validator(mode="after")
    def _montant_et_devise_ensemble(self) -> "CompanyFinancialsRequest":
        if (self.revenue is None) != (self.revenue_currency is None):
            raise ValueError("revenue et revenue_currency vont ensemble.")
        if (self.enterprise_value is None) != (self.enterprise_value_currency is None):
            raise ValueError("enterprise_value et enterprise_value_currency vont ensemble.")
        if self.enterprise_value is None and self.enterprise_value_as_of is not None:
            raise ValueError("enterprise_value_as_of n'a de sens qu'avec enterprise_value.")
        return self


class CompanyFinancials(BaseModel):
    """Réponse de GET / PUT /admin/companies/{id}/financials : montants en nombres JSON (un
    Decimal serait sérialisé en chaîne)."""

    company_id: uuid.UUID
    revenue: float | None
    revenue_currency: Currency | None
    enterprise_value: float | None
    enterprise_value_currency: Currency | None
    enterprise_value_as_of: date | None


class KycCheck(BaseModel):
    """Un contrôle KYC (tâche 5.3) : son résultat, ce qui l'explique, et d'où vient l'information."""

    code: str
    label: str
    result: KycCheckResult
    detail: str
    source: str


class KycReport(BaseModel):
    """GET /admin/companies/{id}/kyc — de quoi décider d'une inscription dans une seule fenêtre :
    identité déclarée, contact, lettre de mandat, échanges avec le demandeur, contrôles."""

    company_id: uuid.UUID
    company_name: str
    status: RegistrationStatus
    lei: str | None
    isin: str | None
    website: str | None
    contact_name: str | None
    contact_email: str | None
    registered_at: datetime | None
    mandate_letter_available: bool
    mandate_letter_uploaded_at: datetime | None
    info_request_message: str | None
    info_requested_at: datetime | None
    info_response_message: str | None
    checked_at: datetime
    checks: list[KycCheck]
