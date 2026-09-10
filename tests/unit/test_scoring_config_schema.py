from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.enums import Pilier
from app.scoring.config_schema import (
    ConfigurationScoring,
    charger_configuration_depuis_fichier,
)

_BASE = {
    "version": 1,
    "nom": "Test",
    "piliers": {
        "ENVIRONNEMENT": {
            "poids": 0.5,
            "indicateurs": {
                "code_e": {
                    "poids": 1.0,
                    "plus_haut_est_meilleur": False,
                    "borne_min": 0,
                    "borne_max": 100,
                }
            },
        },
        "SOCIAL": {
            "poids": 0.25,
            "indicateurs": {
                "code_s": {
                    "poids": 1.0,
                    "plus_haut_est_meilleur": True,
                    "borne_min": 0,
                    "borne_max": 50,
                }
            },
        },
        "GOUVERNANCE": {
            "poids": 0.25,
            "indicateurs": {
                "code_g": {
                    "poids": 1.0,
                    "plus_haut_est_meilleur": True,
                    "borne_min": 0,
                    "borne_max": 50,
                }
            },
        },
    },
}


def test_configuration_valide_est_acceptee() -> None:
    configuration = ConfigurationScoring.model_validate(_BASE)
    assert configuration.piliers[Pilier.ENVIRONNEMENT].poids == 0.5


def test_pilier_manquant_est_rejete() -> None:
    donnees = {**_BASE, "piliers": {k: v for k, v in _BASE["piliers"].items() if k != "GOUVERNANCE"}}
    with pytest.raises(ValidationError, match="piliers manquants"):
        ConfigurationScoring.model_validate(donnees)


def test_somme_des_poids_des_piliers_hors_de_1_est_rejetee() -> None:
    donnees = {**_BASE, "piliers": {**_BASE["piliers"]}}
    donnees["piliers"] = {
        **donnees["piliers"],
        "ENVIRONNEMENT": {**donnees["piliers"]["ENVIRONNEMENT"], "poids": 0.9},
    }
    with pytest.raises(ValidationError, match="poids des piliers"):
        ConfigurationScoring.model_validate(donnees)


def test_somme_des_poids_des_indicateurs_dun_pilier_hors_de_1_est_rejetee() -> None:
    donnees = {**_BASE}
    donnees["piliers"] = {
        **donnees["piliers"],
        "SOCIAL": {
            "poids": 0.25,
            "indicateurs": {
                "code_s": {
                    "poids": 0.3,
                    "plus_haut_est_meilleur": True,
                    "borne_min": 0,
                    "borne_max": 50,
                }
            },
        },
    }
    with pytest.raises(ValidationError, match="ses indicateurs"):
        ConfigurationScoring.model_validate(donnees)


def test_pilier_sans_indicateur_est_rejete() -> None:
    donnees = {**_BASE}
    donnees["piliers"] = {**donnees["piliers"], "SOCIAL": {"poids": 0.25, "indicateurs": {}}}
    with pytest.raises(ValidationError, match="au moins un indicateur"):
        ConfigurationScoring.model_validate(donnees)


def test_borne_max_inferieure_ou_egale_a_borne_min_est_rejetee() -> None:
    donnees = {**_BASE}
    donnees["piliers"] = {
        **donnees["piliers"],
        "GOUVERNANCE": {
            "poids": 0.25,
            "indicateurs": {
                "code_g": {
                    "poids": 1.0,
                    "plus_haut_est_meilleur": True,
                    "borne_min": 50,
                    "borne_max": 50,
                }
            },
        },
    }
    with pytest.raises(ValidationError, match="borne_max"):
        ConfigurationScoring.model_validate(donnees)


def test_fichier_de_reference_reel_est_valide() -> None:
    """config/weights/default.yaml (Phase 5 §9) doit toujours passer ce même schéma -- une
    régression ici serait une erreur de méthodologie silencieuse, pas juste un test qui casse."""
    configuration = charger_configuration_depuis_fichier(Path("config/weights/default.yaml"))
    assert configuration.piliers[Pilier.SOCIAL].indicateurs["femmes_management_pourcentage"].poids == 0.6
