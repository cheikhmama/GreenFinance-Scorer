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
    CompanyStatus,
    DevisePosition,
    ReportStatus,
    Role,
    StatutAnalyse,
    StatutProjet,
)


class AffecterAuditeurRequest(BaseModel):
    auditeur_id: uuid.UUID


class ModifierEntrepriseAdminRequest(BaseModel):
    """Remplace entièrement le profil d'une entreprise (identité, description, site officiel,
    montant minimum) — jamais un patch partiel champ par champ, même principe que
    CreerUtilisateurRequest pour nom_entreprise/secteur/pays. Le logo suit un circuit séparé
    (POST/DELETE /admin/entreprises/{id}/logo, voir plus bas) : un fichier binaire validé par sa
    signature réelle n'a pas sa place dans un payload JSON de chaîne libre. montant_minimum_
    investissement et devise_montant_minimum se renseignent toujours ensemble ou se vident tous
    les deux ensemble, jamais un montant minimum sans sa devise (voir app/company/models.py)."""

    nom: str
    secteur: str
    pays: str
    description: str | None = None
    site_officiel: str | None = None
    montant_minimum_investissement: Decimal | None = Field(
        default=None, gt=0, max_digits=20, decimal_places=2
    )
    devise_montant_minimum: DevisePosition | None = None

    @field_validator("nom", "secteur", "pays")
    @classmethod
    def _verifier_non_vide(cls, valeur: str) -> str:
        valeur = valeur.strip()
        if not valeur:
            raise ValueError("Ce champ ne peut pas être vide.")
        return valeur

    @model_validator(mode="after")
    def _verifier_paire_montant_devise(self) -> "ModifierEntrepriseAdminRequest":
        if (self.montant_minimum_investissement is None) != (self.devise_montant_minimum is None):
            raise ValueError(
                "montant_minimum_investissement et devise_montant_minimum doivent être fournis "
                "ensemble ou omis ensemble."
            )
        return self


class DecisionAdminRequest(BaseModel):
    commentaire: str | None = None


class CreerUtilisateurRequest(BaseModel):
    email: EmailNormalise
    # Nom de la personne ou de l'institution titulaire du compte (Utilisateur.nom), distinct de
    # nom_entreprise ci-dessous (le nom de l'Entreprise elle-même, requis seulement quand
    # role == ENTREPRISE). Optionnel : l'Administrateur ne le saisit pas systématiquement, voir
    # creer_utilisateur() pour la valeur déduite de l'e-mail dans ce cas.
    nom: str | None = None
    role: Role
    # Requis uniquement quand role == ENTREPRISE — le profil Entreprise (app/company/models.py)
    # est créé dans le même geste, conformément à la règle actée en Phase 0 (« Entreprise — créée
    # par l'Administrateur, provisioning »). Ignorés pour tout autre rôle.
    nom_entreprise: str | None = None
    secteur: str | None = None
    pays: str | None = None


class UtilisateurCree(BaseModel):
    """Réponse de la création d'un compte — jamais de mot de passe ici : un lien d'activation
    est envoyé par e-mail à la personne titulaire (voir app/admin/utilisateurs.py::creer_utilisateur
    et app/auth/activation.py)."""

    id: uuid.UUID
    email: str
    nom: str
    role: Role
    date_creation: datetime
    actif: bool


class EntrepriseAdmin(EntreprisePublic):
    """Vue Administrateur d'une entreprise, quel que soit son statut — contrairement à
    EntreprisePublic (renvoyée à l'Entreprise elle-même), expose utilisateur_id : savoir si un
    compte est rattaché est précisément ce dont l'Administrateur a besoin pour distinguer une
    entreprise gérée en autonomie d'une entreprise sans compte (ex. fiche de référence, ou
    provisionnée avant qu'un compte ne lui soit rattaché — voir app/company/models.py)."""

    utilisateur_id: uuid.UUID | None
    nombre_rapports: int
    dernier_statut_rapport: ReportStatus | None
    # Permet au frontend de lier "Voir le rapport"/"Valider" directement au rapport le plus
    # récent, sans détour par la liste des rapports — None si aucun rapport déposé.
    dernier_rapport_id: uuid.UUID | None


class JournalAuditPublic(BaseModel):
    """Vue Administrateur d'une entrée du journal d'audit — aucun champ sensible à masquer, la
    table elle-même ne contient jamais de secret (voir app/core/audit.py)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    acteur_id: uuid.UUID | None
    action: str
    type_ressource: str
    id_ressource: uuid.UUID | None
    date: datetime
    resultat: str
    ancienne_valeur: str | None
    nouvelle_valeur: str | None
    correlation_id: str | None


class TableauDeBordAdmin(BaseModel):
    """Indicateurs agrégés du tableau de bord Administrateur (voir app/admin/dashboard.py)."""

    entreprises_inscrites: int
    rapports_soumis: int
    rapports_valides: int
    rapports_rejetes: int
    entreprises_publiees: int
    audits_en_retard: int
    rapports_a_affecter: int
    decisions_a_rendre: int
    demandes_republication: int
    utilisateurs_en_attente: int
    # États incohérents/orphelins qu'aucune file normale ne surface (voir
    # app/admin/review_queue.py::lister_rapports_echec_extraction/lister_rapports_orphelins_en_validation)
    # — jamais silencieusement ignorés, même quand ils sont rares ou (aujourd'hui) inatteignables
    # via le seul parcours applicatif normal.
    rapports_echec_extraction: int
    rapports_orphelins: int
    # Effectifs de comptes actifs par rôle — pas de champ "entreprises" ici, voir
    # entreprises_inscrites ci-dessus, la mesure déjà pertinente pour ce rôle.
    administrateurs_actifs: int
    auditeurs_actifs: int
    investisseurs_actifs: int
    chercheurs_actifs: int
    institutions_actives: int


class ScoreVerificationAdmin(BaseModel):
    """Aperçu, sans rien persister, de si un rapport PENDING_DECISION pourrait être scoré —
    affiché avant que l'Admin ne clique Valider (voir app/scoring/engine.py::score_calculable),
    plutôt que de le laisser découvrir l'échec après coup."""

    calculable: bool


class StatistiquesAuditeursAdmin(BaseModel):
    """Voir app/audit/assignment.py::statistiques_charge_globale — comptes_actifs et
    audits_en_retard vivent déjà dans TableauDeBordAdmin, pas répétés ici."""

    dossiers_affectes: int
    avis_rendus: int


class StatistiquesInvestisseursAdmin(BaseModel):
    """Voir app/investor/portfolio.py::statistiques_admin — comptes_actifs vit déjà dans
    TableauDeBordAdmin, pas répété ici."""

    portefeuilles_non_archives: int
    positions_declarees: int
    entreprises_distinctes: int


class StatistiquesChercheursAdmin(BaseModel):
    """Voir app/researcher/analyses.py::statistiques_admin — comptes_actifs vit déjà dans
    TableauDeBordAdmin, pas répété ici."""

    chercheurs_affectes_projets_ouverts: int
    analyses_brouillon: int
    analyses_soumises: int
    analyses_validees: int
    analyses_correction_demandee: int


class StatistiquesInstitutionsAdmin(BaseModel):
    """Voir app/institution/projets.py::statistiques_admin — comptes_actifs vit déjà dans
    TableauDeBordAdmin, pas répété ici."""

    projets_ouverts: int
    projets_clotures: int
    invitations_en_attente: int
    analyses_a_examiner: int


class ApercuActeursAdmin(BaseModel):
    """Voir app/admin/apercu.py::construire_apercu_acteurs."""

    auditeurs: StatistiquesAuditeursAdmin
    investisseurs: StatistiquesInvestisseursAdmin
    chercheurs: StatistiquesChercheursAdmin
    institutions: StatistiquesInstitutionsAdmin


class TrancheScorePublic(BaseModel):
    borne_min: int
    borne_max: int
    nombre_entreprises: int


class PerformanceESGAdmin(BaseModel):
    """Voir app/admin/apercu.py::calculer_performance_esg — score_*_moyen est None quand aucune
    entreprise du périmètre n'a de valeur exploitable pour ce pilier, jamais 0."""

    score_global_moyen: float | None
    score_environnement_moyen: float | None
    score_social_moyen: float | None
    score_gouvernance_moyen: float | None
    entreprises_avec_score: int
    entreprises_perimetre: int
    distribution: list[TrancheScorePublic]


class EntrepriseAvecScoreAdmin(BaseModel):
    """Une ligne du détail derrière les cartes de performance ESG — score_* à None quand
    l'entreprise n'a pas de score admissible, jamais 0 (voir PerformanceESGAdmin)."""

    id: uuid.UUID
    nom: str
    secteur: str
    pays: str
    score_global: float | None
    score_environnement: float | None
    score_social: float | None
    score_gouvernance: float | None


class ChargeAuditeurAdmin(BaseModel):
    """Une ligne du détail derrière "Dossiers affectés" (app/audit/assignment.py::
    lister_charge_auditeurs)."""

    auditeur_id: uuid.UUID
    email: str
    dossiers_affectes: int
    dossiers_en_retard: int
    avis_rendus: int


class PortefeuilleAdmin(BaseModel):
    """Une ligne du détail derrière "Portefeuilles non archivés" (app/investor/portfolio.py::
    lister_portefeuilles_admin). montant_total dans devise_reference, jamais additionné entre
    portefeuilles de devises différentes."""

    id: uuid.UUID
    nom: str
    investisseur_email: str
    devise_reference: DevisePosition
    nombre_positions: int
    montant_total: float
    date_creation: datetime


class AnalyseAdmin(BaseModel):
    """Une ligne du détail derrière "Analyses par statut" (app/researcher/analyses.py::
    lister_analyses_admin). Une ligne = une version précise, jamais fusionnée avec ses versions
    précédentes/suivantes (voir Analyse.analyse_precedente_id)."""

    id: uuid.UUID
    titre: str
    statut: StatutAnalyse
    version: int
    chercheur_email: str
    projet_nom: str
    date_creation: datetime
    date_soumission: datetime | None
    date_decision: datetime | None


class ProjetAdmin(BaseModel):
    """Une ligne du détail derrière "Projets ouverts/clôturés" (app/institution/projets.py::
    lister_projets_admin)."""

    id: uuid.UUID
    nom: str
    statut: StatutProjet
    institution_email: str
    nombre_chercheurs: int
    date_creation: datetime
    date_limite: datetime | None
    date_cloture: datetime | None


class OnboardingDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class CompanyOnboardingRequest(BaseModel):
    """PATCH /admin/companies/{id}/onboard (tâche 1.4, contrat JSON en anglais). Un refus exige un
    motif : il est transmis au demandeur par e-mail."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    decision: OnboardingDecision
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _motif_si_refus(self) -> "CompanyOnboardingRequest":
        if self.decision == OnboardingDecision.REJECT and not self.reason:
            raise ValueError("Un motif est requis pour refuser une inscription.")
        return self


class CompanyOnboardingResult(BaseModel):
    """`status` est None après un refus : l'inscription refusée est supprimée (le demandeur peut
    en déposer une nouvelle), il n'y a plus d'entreprise à décrire."""

    company_id: uuid.UUID
    decision: OnboardingDecision
    status: CompanyStatus | None
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
    revenue_currency: DevisePosition | None = None
    enterprise_value: Decimal | None = Field(default=None, gt=0, max_digits=20, decimal_places=2)
    enterprise_value_currency: DevisePosition | None = None
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
    revenue_currency: DevisePosition | None
    enterprise_value: float | None
    enterprise_value_currency: DevisePosition | None
    enterprise_value_as_of: date | None
