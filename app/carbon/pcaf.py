"""Moteur carbone PCAF d'un portefeuille (tâche 2.3, docs/WORKFLOWS.md §2.4).

Fonctions pures : aucune session, aucune E/S. Les données d'entrée (montants déjà convertis dans
la devise du portefeuille, émissions du dernier rapport validé) sont assemblées par
app/investor/carbon.py ; tout ce qui est calculé ici est donc testable sans base.

Méthode — PCAF Part A, actions cotées et obligations d'entreprise :
- facteur d'attribution AFᵢ = montantᵢ / EVICᵢ ;
- émissions financées FE = Σ AFᵢ × Eᵢ, Scopes 1+2 d'un côté et Scope 3 de l'autre — jamais
  additionnés (le Scope 3 double-compte entre entreprises, PCAF le publie séparément) ;
- empreinte carbone = FE₁₊₂ / valeur couverte × 1 M (tCO₂e par million investi) ;
- WACI = Σ wᵢ × (E₁ + E₂)ᵢ / chiffre d'affairesᵢ × 1 M (tCO₂e par million de chiffre d'affaires),
  poids renormalisés sur les lignes couvertes ;
- qualité des données = moyenne pondérée par les montants du score PCAF (1 = meilleur).

Une donnée manquante n'est jamais comptée comme zéro : la ligne est exclue du calcul concerné,
avec son motif, et fait baisser la couverture (part du montant total effectivement couverte).
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from app.core.enums import DataMethod

MILLION = Decimal(1_000_000)

# PCAF Part A, options de qualité : 1 émissions déclarées et vérifiées par un tiers, 2 déclarées
# non vérifiées, 3 calculées à partir de données physiques d'activité, 4 estimées à partir de
# données économiques, 5 moyennes sectorielles. L'extraction ne sait pas si les émissions
# publiées ont fait l'objet d'une assurance externe : une valeur déclarée reste donc au score 2,
# jamais promue à 1 sans cette information.
QUALITE_PAR_METHODE: dict[DataMethod, int] = {
    DataMethod.RAPPORTEE: 2,
    DataMethod.CALCULEE: 3,
    DataMethod.ESTIMEE: 4,
}

# Scope 2 : la base « market-based » reflète les achats d'énergie de l'entreprise (celle que PCAF
# recommande) ; à défaut la valeur non précisée, puis « location-based ».
PREFERENCE_SCOPE_2: tuple[str | None, ...] = ("market_based", None, "location_based")


def qualite_donnee_pcaf(methode: DataMethod) -> int:
    return QUALITE_PAR_METHODE[methode]


class CarbonExclusionReason(str, Enum):
    """Pourquoi une ligne ne participe pas aux émissions financées (Scopes 1+2)."""

    UNMATCHED = "UNMATCHED"  # ligne importée sans entreprise
    NO_VALIDATED_REPORT = "NO_VALIDATED_REPORT"
    MISSING_EMISSIONS = "MISSING_EMISSIONS"  # Scope 1 ou Scope 2 absent du rapport
    MISSING_EVIC = "MISSING_EVIC"


@dataclass(frozen=True)
class Emission:
    tonnes_co2e: float
    qualite: int | None


@dataclass(frozen=True)
class EmissionsEntreprise:
    """Émissions du dernier rapport validé d'une entreprise, une valeur déjà choisie par scope."""

    annee: int | None
    scope_1: Emission | None
    scope_2: Emission | None
    scope_2_base: str | None
    scope_3: Emission | None


@dataclass(frozen=True)
class LignePCAF:
    position_id: uuid.UUID
    montant: Decimal  # dans la devise du portefeuille
    rapprochee: bool
    evic: Decimal | None  # dans la devise du portefeuille
    chiffre_affaires: Decimal | None  # dans la devise du portefeuille
    emissions: EmissionsEntreprise | None


@dataclass(frozen=True)
class ResultatLigne:
    position_id: uuid.UUID
    facteur_attribution: Decimal | None
    emissions_financees_scope_1_2: float | None
    emissions_financees_scope_3: float | None
    intensite_carbone: float | None  # (E₁ + E₂) / chiffre d'affaires × 1 M
    qualite: int | None  # Scopes 1+2 : la moins bonne des deux
    motif_exclusion: CarbonExclusionReason | None


@dataclass(frozen=True)
class ResultatPortefeuille:
    valeur_totale: Decimal
    emissions_financees_scope_1_2: float | None
    emissions_financees_scope_3: float | None
    empreinte_carbone_scope_1_2: float | None
    waci_scope_1_2: float | None
    qualite_scope_1_2: float | None
    qualite_scope_3: float | None
    couverture_scope_1_2: float  # part du montant total, entre 0 et 1
    couverture_scope_3: float
    couverture_waci: float
    lignes: list[ResultatLigne]


def choisir_scope_2(par_categorie: dict[str | None, Emission]) -> tuple[Emission | None, str | None]:
    for categorie in PREFERENCE_SCOPE_2:
        if categorie in par_categorie:
            return par_categorie[categorie], categorie
    return None, None


def _qualite_pire(*qualites: int | None) -> int | None:
    if any(q is None for q in qualites):
        return None
    return max(q for q in qualites if q is not None)


def calculer_ligne(ligne: LignePCAF) -> ResultatLigne:
    emissions = ligne.emissions
    motif: CarbonExclusionReason | None = None
    if not ligne.rapprochee:
        motif = CarbonExclusionReason.UNMATCHED
    elif emissions is None:
        motif = CarbonExclusionReason.NO_VALIDATED_REPORT
    elif emissions.scope_1 is None or emissions.scope_2 is None:
        motif = CarbonExclusionReason.MISSING_EMISSIONS
    elif ligne.evic is None or ligne.evic <= 0:
        motif = CarbonExclusionReason.MISSING_EVIC

    facteur = (
        ligne.montant / ligne.evic
        if emissions is not None and ligne.evic is not None and ligne.evic > 0
        else None
    )
    fe_1_2 = intensite = qualite = None
    if emissions is not None and emissions.scope_1 is not None and emissions.scope_2 is not None:
        total_1_2 = emissions.scope_1.tonnes_co2e + emissions.scope_2.tonnes_co2e
        qualite = _qualite_pire(emissions.scope_1.qualite, emissions.scope_2.qualite)
        if facteur is not None:
            fe_1_2 = float(facteur) * total_1_2
        if ligne.chiffre_affaires is not None and ligne.chiffre_affaires > 0:
            intensite = total_1_2 / float(ligne.chiffre_affaires / MILLION)
    fe_3 = (
        float(facteur) * emissions.scope_3.tonnes_co2e
        if facteur is not None and emissions is not None and emissions.scope_3 is not None
        else None
    )
    return ResultatLigne(
        position_id=ligne.position_id,
        facteur_attribution=facteur,
        emissions_financees_scope_1_2=fe_1_2,
        emissions_financees_scope_3=fe_3,
        intensite_carbone=intensite,
        qualite=qualite,
        motif_exclusion=motif,
    )


def _moyenne_ponderee(paires: list[tuple[Decimal, float]]) -> float | None:
    poids_total = sum((poids for poids, _ in paires), Decimal(0))
    if poids_total == 0:
        return None
    return sum(float(poids) * valeur for poids, valeur in paires) / float(poids_total)


def calculer_portefeuille(lignes: list[LignePCAF]) -> ResultatPortefeuille:
    resultats = [calculer_ligne(ligne) for ligne in lignes]
    montants = {ligne.position_id: ligne.montant for ligne in lignes}
    qualites_3 = {
        ligne.position_id: ligne.emissions.scope_3.qualite
        for ligne in lignes
        if ligne.emissions is not None and ligne.emissions.scope_3 is not None
    }
    valeur_totale = sum(montants.values(), Decimal(0))

    couverts_1_2 = [r for r in resultats if r.emissions_financees_scope_1_2 is not None]
    couverts_3 = [r for r in resultats if r.emissions_financees_scope_3 is not None]
    couverts_waci = [r for r in resultats if r.intensite_carbone is not None]

    def valeur(couverts: list[ResultatLigne]) -> Decimal:
        return sum((montants[r.position_id] for r in couverts), Decimal(0))

    def part(couverts: list[ResultatLigne]) -> float:
        return float(valeur(couverts) / valeur_totale) if valeur_totale else 0.0

    fe_1_2 = (
        sum(r.emissions_financees_scope_1_2 or 0.0 for r in couverts_1_2) if couverts_1_2 else None
    )
    fe_3 = sum(r.emissions_financees_scope_3 or 0.0 for r in couverts_3) if couverts_3 else None
    valeur_1_2 = valeur(couverts_1_2)
    empreinte = fe_1_2 / float(valeur_1_2 / MILLION) if fe_1_2 is not None and valeur_1_2 else None

    return ResultatPortefeuille(
        valeur_totale=valeur_totale,
        emissions_financees_scope_1_2=fe_1_2,
        emissions_financees_scope_3=fe_3,
        empreinte_carbone_scope_1_2=empreinte,
        waci_scope_1_2=_moyenne_ponderee(
            [(montants[r.position_id], r.intensite_carbone or 0.0) for r in couverts_waci]
        ),
        qualite_scope_1_2=_moyenne_ponderee(
            [(montants[r.position_id], float(r.qualite)) for r in couverts_1_2 if r.qualite]
        ),
        qualite_scope_3=_moyenne_ponderee(
            [
                (montants[r.position_id], float(q))
                for r in couverts_3
                if (q := qualites_3.get(r.position_id)) is not None
            ]
        ),
        couverture_scope_1_2=part(couverts_1_2),
        couverture_scope_3=part(couverts_3),
        couverture_waci=part(couverts_waci),
        lignes=resultats,
    )
