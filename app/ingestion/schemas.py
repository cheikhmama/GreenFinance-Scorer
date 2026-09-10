"""Schémas Pydantic d'entrée/sortie du module d'extraction documentaire.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).

IndicateurExtrait / ExtractionEntreprise forment le contrat de tool-use forcé de l'appel Claude
(app/ingestion/extractor.py) — portés VERBATIM depuis notebooks/_prompt_4_4_extraction.py, où ils
ont été validés (mêmes champs, mêmes descriptions) : ne pas les modifier sans revalider le
protocole d'extraction.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import CanalDepot, MethodeDonnee, Pilier, StatutRapport, TypeRapport


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


class ExtractionEntreprise(BaseModel):
    entreprise: str
    indicateurs: list[IndicateurExtrait]


class RapportESGPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entreprise_id: uuid.UUID
    type: TypeRapport
    canal: CanalDepot
    date_depot: datetime
    statut: StatutRapport
    fichier_source: str
    annee_reporting: int | None
    extraction_terminee_le: datetime | None
    extraction_erreur: str | None
    version: int
    rapport_precedent_id: uuid.UUID | None


class PreuveDocumentairePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom_document: str
    annee: int
    nombre_pages_total: int
    page_debut: int
    page_fin: int
    pdf_extrait_genere: str


class IndicateurESGDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pilier: Pilier
    code: str
    valeur: float
    unite: str
    methode: MethodeDonnee
    preuve: PreuveDocumentairePublic


class DonneeCarboneDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope: int
    categorie_ges: str | None
    valeur_tonnes_co2e: float
    annee: int
    methode: MethodeDonnee
    score_qualite_pcaf: int
    preuve: PreuveDocumentairePublic


class RapportESGDetail(RapportESGPublic):
    """Étend RapportESGPublic avec les données extraites. Ne contient JAMAIS l'avis de l'auditeur
    (app/audit/schemas.py::AvisAudit*) — l'auditeur_id ne doit jamais pouvoir fuiter vers une
    réponse Entreprise par accident de composition de schéma, pas seulement par discipline."""

    indicateurs: list[IndicateurESGDetail]
    donnees_carbone: list[DonneeCarboneDetail]
