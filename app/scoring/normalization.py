"""Normalisation des indicateurs bruts avant scoring (Phase 5 §9).

Une seule fonction, volontairement simple : ramène une valeur brute hétérogène (un pourcentage,
un compte, une intensité en gCO2e/kWh...) à une sous-note 0-100 comparable, à partir des bornes
et du sens (plus haut est meilleur, ou l'inverse) déclarés dans app/scoring/config_schema.py. La
borne n'est pas un jugement de valeur absolu : c'est un choix méthodologique versionné, ajustable
sans toucher au code — voir config/weights/default.yaml.
"""


def normaliser(
    valeur: float, *, borne_min: float, borne_max: float, plus_haut_est_meilleur: bool
) -> float:
    """Ramène `valeur` à une sous-note 0-100. Une valeur hors bornes est plafonnée (jamais
    négative, jamais > 100) plutôt que de produire un score qui sortirait de l'échelle."""
    fraction = (valeur - borne_min) / (borne_max - borne_min)
    fraction = min(1.0, max(0.0, fraction))
    if not plus_haut_est_meilleur:
        fraction = 1.0 - fraction
    return fraction * 100
