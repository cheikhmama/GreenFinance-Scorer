"""Attribution SHAP exacte du score ESG (tâche 3.2, docs/ARCHITECTURE.md §7).

Le score global est une fonction linéaire des valeurs normalisées des indicateurs présents
(app/scoring/engine.py::termes_effectifs) : score = Σ wᵢ × xᵢ. Pour un modèle linéaire, les
valeurs SHAP ont une forme close — φᵢ = wᵢ × (xᵢ − x̄ᵢ), x̄ᵢ la valeur de référence de
l'indicateur — et somment exactement à score − score_reference, où score_reference = Σ wᵢ × x̄ᵢ.
Ni entraînement, ni échantillonnage : le résultat est exact et reproductible.

Fonctions pures, sans session : les références (moyennes des pairs) sont calculées par
app/explainability/explanation.py.

Indicateur sans aucune valeur de référence chez les pairs : sa référence est sa propre valeur
(contribution nulle) et `reference` reste None — jamais une moyenne inventée ; l'écart qu'il
porte reste donc dans score_reference, pas dans une contribution.
"""

from dataclasses import dataclass

from app.core.enums import Pillar
from app.scoring.engine import TermeScore


@dataclass(frozen=True)
class Contribution:
    pilier: Pillar
    code: str
    valeur: float  # valeur effective déclarée (correction de l'Auditeur incluse)
    valeur_normalisee: float  # 0-100
    reference: float | None  # moyenne normalisée des pairs, None si aucun pair ne la publie
    poids_effectif: float
    contribution: float  # φᵢ, en points de score


@dataclass(frozen=True)
class Decomposition:
    score: float
    score_reference: float
    contributions: list[Contribution]


def references_moyennes(
    pairs: list[list[TermeScore]],
) -> dict[tuple[Pillar, str], float]:
    """Moyenne des valeurs normalisées de chaque indicateur sur les pairs qui le publient."""
    sommes: dict[tuple[Pillar, str], list[float]] = {}
    for termes in pairs:
        for terme in termes:
            sommes.setdefault((terme.pilier, terme.code), []).append(terme.valeur_normalisee)
    return {cle: sum(valeurs) / len(valeurs) for cle, valeurs in sommes.items()}


def decomposer(
    termes: list[TermeScore], references: dict[tuple[Pillar, str], float]
) -> Decomposition:
    contributions = []
    for terme in termes:
        reference = references.get((terme.pilier, terme.code))
        base = terme.valeur_normalisee if reference is None else reference
        contributions.append(
            Contribution(
                pilier=terme.pilier,
                code=terme.code,
                valeur=terme.valeur,
                valeur_normalisee=terme.valeur_normalisee,
                reference=reference,
                poids_effectif=terme.poids_effectif,
                contribution=terme.poids_effectif * (terme.valeur_normalisee - base),
            )
        )
    # Cascade : piliers dans l'ordre de l'énumération, indicateurs par |φ| décroissant.
    ordre_piliers = {pilier: rang for rang, pilier in enumerate(Pillar)}
    contributions.sort(key=lambda c: (ordre_piliers[c.pilier], -abs(c.contribution), c.code))
    return Decomposition(
        score=sum(t.poids_effectif * t.valeur_normalisee for t in termes),
        score_reference=sum(
            t.poids_effectif * references.get((t.pilier, t.code), t.valeur_normalisee)
            for t in termes
        ),
        contributions=contributions,
    )
