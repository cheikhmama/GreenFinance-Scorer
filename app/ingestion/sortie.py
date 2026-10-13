"""Sortie JSON d'une extraction, hors base de données : l'outil MCP extract_esg_report la renvoie
telle quelle à l'agent appelant.

Même règle que l'enregistrement (garantie G1) : une valeur n'est publiée qu'avec sa page source,
sinon rien ne permet de la vérifier. Chaque valeur porte sa correspondance dans les référentiels
publics (app/ingestion/referentiels.py).
"""

from typing import Literal

from pydantic import BaseModel

from app.core.enums import ConfidenceLevel, MetricCoverageStatus
from app.ingestion.cibles import INDICATEURS_CIBLES
from app.ingestion.referentiels import Referentiels, charger_referentiels
from app.ingestion.schemas import ExtractionEntreprise

Famille = Literal["CARBONE", "ENVIRONNEMENT", "SOCIAL", "GOUVERNANCE", "GLOBAL"]


class DocumentSortie(BaseModel):
    nom: str
    pages: int
    sha256: str


class ExecutionSortie(BaseModel):
    modele: str
    prompt_version: str
    docling_version: str
    pages_ocr: int
    duree_conversion_s: float
    duree_llm_s: float
    pic_memoire_mo: int | None


class IndicateurSortie(BaseModel):
    code: str
    famille: Famille
    valeur: float
    unite: str | None
    page_source: int
    citation: str | None
    annee_valeur: int | None
    confiance: ConfidenceLevel | None
    referentiels: Referentiels


class CouvertureSortie(BaseModel):
    code: str
    statut: MetricCoverageStatus


class RapportExtraitJSON(BaseModel):
    entreprise: str
    annee: int | None
    document: DocumentSortie
    execution: ExecutionSortie
    indicateurs: list[IndicateurSortie]
    couverture: list[CouvertureSortie]


def famille_du_code(code: str) -> Famille:
    cible = next(c for c in INDICATEURS_CIBLES if c.code == code)
    if cible.cible == "donnee_carbone":
        return "CARBONE"
    if cible.pilier is None:
        return "GLOBAL"
    return cible.pilier.value  # type: ignore[return-value]


def construire_sortie(
    extraction: ExtractionEntreprise,
    *,
    annee: int | None,
    document: DocumentSortie,
    execution: ExecutionSortie,
    statuts: dict[str, MetricCoverageStatus],
) -> RapportExtraitJSON:
    referentiels = charger_referentiels()
    indicateurs = [
        IndicateurSortie(
            code=i.code,
            famille=famille_du_code(i.code),
            valeur=i.valeur,
            unite=i.unite,
            page_source=i.page_source,
            citation=i.citation_source,
            annee_valeur=i.annee_valeur,
            confiance=i.confiance,
            referentiels=referentiels[i.code],
        )
        for i in extraction.indicateurs
        if i.trouve and i.valeur is not None and i.page_source is not None and i.code in referentiels
    ]
    return RapportExtraitJSON(
        entreprise=extraction.entreprise,
        annee=annee,
        document=document,
        execution=execution,
        indicateurs=indicateurs,
        couverture=[CouvertureSortie(code=code, statut=statut) for code, statut in statuts.items()],
    )
