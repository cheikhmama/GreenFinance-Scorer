"""Attribution SHAP exacte (tâche 3.2) — propriétés vérifiées sur des rapports tirés au hasard
sous la méthodologie de référence réelle (config/weights/default.yaml)."""

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.enums import Pillar
from app.explainability.decomposition import decomposer, references_moyennes
from app.scoring.config_schema import charger_configuration_depuis_fichier
from app.scoring.engine import _calculer, termes_effectifs

SCHEMA = charger_configuration_depuis_fichier(Path("config/weights/default.yaml"))
CODES = [
    (pilier, code) for pilier, config in SCHEMA.piliers.items() for code in config.indicateurs
]
VALEUR = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)


def _valeurs(tirage: dict[tuple[Pillar, str], float]) -> dict[Pillar, dict[str, float]]:
    valeurs: dict[Pillar, dict[str, float]] = {pilier: {} for pilier in Pillar}
    for (pilier, code), valeur in tirage.items():
        valeurs[pilier][code] = valeur
    return valeurs


rapports = st.dictionaries(st.sampled_from(CODES), VALEUR, min_size=1)


@settings(max_examples=300, deadline=None)
@given(rapport=rapports)
def test_la_forme_lineaire_retombe_sur_le_score_du_moteur(rapport) -> None:
    valeurs = _valeurs(rapport)
    termes = termes_effectifs(SCHEMA, valeurs)
    resultat = _calculer(SCHEMA, valeurs)

    assert resultat is not None
    assert sum(t.poids_effectif for t in termes) == pytest.approx(1, abs=1e-12)
    assert sum(t.poids_effectif * t.valeur_normalisee for t in termes) == pytest.approx(
        resultat.global_score, abs=1e-9
    )


@settings(max_examples=300, deadline=None)
@given(rapport=rapports, pairs=st.lists(st.dictionaries(st.sampled_from(CODES), VALEUR), max_size=6))
def test_les_contributions_somment_exactement_a_score_moins_reference(rapport, pairs) -> None:
    termes = termes_effectifs(SCHEMA, _valeurs(rapport))
    references = references_moyennes([termes_effectifs(SCHEMA, _valeurs(p)) for p in pairs])

    decomposition = decomposer(termes, references)

    total = sum(c.contribution for c in decomposition.contributions)
    assert total == pytest.approx(decomposition.score - decomposition.score_reference, abs=1e-9)
    assert len(decomposition.contributions) == len(termes)
    for contribution in decomposition.contributions:
        if contribution.reference is None:
            # Aucun pair ne publie cet indicateur : jamais une moyenne inventée.
            assert contribution.contribution == 0


def test_sans_pairs_la_reference_est_le_score_lui_meme() -> None:
    termes = termes_effectifs(SCHEMA, _valeurs({CODES[0]: 10.0, CODES[-1]: 3.0}))

    decomposition = decomposer(termes, {})

    assert decomposition.score_reference == pytest.approx(decomposition.score)
    assert all(c.contribution == 0 and c.reference is None for c in decomposition.contributions)


def test_contribution_calculee_a_la_main() -> None:
    """Un seul indicateur présent : poids effectif 1, φ = valeur normalisée − moyenne des pairs."""
    pilier, code = Pillar.GOUVERNANCE, "femmes_conseil_pourcentage"
    config = SCHEMA.piliers[pilier].indicateurs[code]
    etendue = config.borne_max - config.borne_min
    valeur = config.borne_min + 0.8 * etendue  # normalisée à 80
    pairs = [config.borne_min + part * etendue for part in (0.2, 0.4, 0.6)]  # moyenne 40

    termes = termes_effectifs(SCHEMA, _valeurs({(pilier, code): valeur}))
    references = references_moyennes(
        [termes_effectifs(SCHEMA, _valeurs({(pilier, code): v})) for v in pairs]
    )
    decomposition = decomposer(termes, references)

    assert config.plus_haut_est_meilleur
    assert decomposition.score == pytest.approx(80)
    assert decomposition.score_reference == pytest.approx(40)
    [contribution] = decomposition.contributions
    assert contribution.poids_effectif == pytest.approx(1)
    assert contribution.contribution == pytest.approx(40)
