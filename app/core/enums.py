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


class StatutRapport(str, Enum):
    ENVOYE = "ENVOYE"
    EN_EXTRACTION = "EN_EXTRACTION"
    AFFECTE_AUDITEUR = "AFFECTE_AUDITEUR"
    EN_VALIDATION = "EN_VALIDATION"
    VALIDE = "VALIDE"
    REJETE = "REJETE"
    DEMANDE_CORRECTION = "DEMANDE_CORRECTION"


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


class DecisionAudit(str, Enum):
    RECOMMANDE_VALIDATION = "RECOMMANDE_VALIDATION"
    ANOMALIE_SIGNALEE = "ANOMALIE_SIGNALEE"


class Role(str, Enum):
    ADMINISTRATEUR = "ADMINISTRATEUR"
    ENTREPRISE = "ENTREPRISE"
    AUDITEUR = "AUDITEUR"
    INVESTISSEUR = "INVESTISSEUR"
    CHERCHEUR = "CHERCHEUR"
    INSTITUTION = "INSTITUTION"


class DevisePosition(str, Enum):
    MRU = "MRU"
    USD = "USD"
    EUR = "EUR"


class TypeDureeInvestissement(str, Enum):
    OUVERTE = "OUVERTE"
    FIXE = "FIXE"
