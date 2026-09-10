"""Schémas Pydantic d'entrée/sortie du module Administrateur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.company.schemas import EntreprisePublic
from app.core.enums import Role, StatutRapport


class AffecterAuditeurRequest(BaseModel):
    auditeur_id: uuid.UUID


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
    """Réponse de la création d'un compte — mot_de_passe_temporaire n'apparaît qu'ici, une
    seule fois, jamais journalisé ni renvoyé par une autre route (voir app/admin/utilisateurs.py
    et app/core/audit.py)."""

    id: uuid.UUID
    email: str
    nom: str
    role: Role
    date_creation: datetime
    actif: bool
    mot_de_passe_temporaire: str


class ChangerRoleRequest(BaseModel):
    role: Role


class EntrepriseAdmin(EntreprisePublic):
    """Vue Administrateur d'une entreprise, quel que soit son statut — contrairement à
    EntreprisePublic (renvoyée à l'Entreprise elle-même), expose utilisateur_id : savoir si un
    compte est rattaché est précisément ce dont l'Administrateur a besoin pour distinguer une
    entreprise gérée en autonomie d'une entreprise sans compte (ex. fiche de référence, ou
    provisionnée avant qu'un compte ne lui soit rattaché — voir app/company/models.py)."""

    utilisateur_id: uuid.UUID | None
    nombre_rapports: int
    dernier_statut_rapport: StatutRapport | None


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
