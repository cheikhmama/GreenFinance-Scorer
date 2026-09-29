"""Schémas Pydantic d'entrée/sortie du module Administrateur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator, model_validator

from app.company.schemas import EntreprisePublic
from app.core.enums import (
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
    montant_minimum_investissement: float | None = None
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
    email: EmailStr
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
