import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.core.enums import Pillar
from app.scoring.config_schema import (
    ConfigurationScoring,
    charger_configuration_depuis_fichier,
    empreinte_configuration,
)

# dict[str, Any], pas un TypedDict : cette fixture n'existe que pour nourrir model_validate
# (qui accepte une structure arbitraire), jamais lue champ par champ avec des types précis.
_BASE: dict[str, Any] = {
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
    assert configuration.piliers[Pillar.ENVIRONNEMENT].poids == 0.5


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
    """config/weights/default.yaml (Phase 5 §9, élargi v2) doit toujours passer ce même schéma --
    une régression ici serait une erreur de méthodologie silencieuse, pas juste un test qui casse."""
    configuration = charger_configuration_depuis_fichier(Path("config/weights/default.yaml"))
    assert configuration.version == 2
    assert configuration.piliers[Pillar.SOCIAL].indicateurs["femmes_management_pourcentage"].poids == 0.35
    # v2 ajoute 3 indicateurs (un par pilier concerné hors Gouvernance) -- jamais le tonnage
    # carbone brut ni les scores auto-déclarés, exclus par principe (voir le commentaire du YAML).
    assert "part_renouvelable_pourcentage" in configuration.piliers[Pillar.ENVIRONNEMENT].indicateurs
    assert "dechets_valorises_pourcentage" in configuration.piliers[Pillar.ENVIRONNEMENT].indicateurs
    assert "femmes_effectif_pourcentage" in configuration.piliers[Pillar.SOCIAL].indicateurs
    for pilier_codes in (
        configuration.piliers[Pillar.ENVIRONNEMENT].indicateurs,
        configuration.piliers[Pillar.SOCIAL].indicateurs,
        configuration.piliers[Pillar.GOUVERNANCE].indicateurs,
    ):
        assert "score_environnement_declare" not in pilier_codes
        assert "score_social_declare" not in pilier_codes
        assert "score_gouvernance_declare" not in pilier_codes
        assert not any(code.startswith("scope_") for code in pilier_codes)


def test_empreinte_insensible_a_la_forme_sensible_au_fond() -> None:
    contenu = Path("config/weights/default.yaml").read_text(encoding="utf-8")
    donnees = yaml.safe_load(contenu)

    reformate = yaml.safe_dump(donnees, sort_keys=False, indent=4)
    donnees["piliers"]["SOCIAL"]["poids"] += 0.01
    modifie = yaml.safe_dump(donnees)

    assert empreinte_configuration(reformate) == empreinte_configuration(contenu)
    assert empreinte_configuration(modifie) != empreinte_configuration(contenu)


def test_empreinte_identique_a_celle_de_la_migration() -> None:
    """La migration c1d4a8e2f935 a figé sa propre copie du calcul d'empreinte (une migration ne
    doit pas dépendre du code applicatif) : les deux doivent rester identiques, sinon les
    configurations reprises à la migration ne seraient plus jamais retrouvées par leur empreinte."""
    chemin = next(Path("alembic/versions").glob("c1d4a8e2f935_*.py"))
    spec = importlib.util.spec_from_file_location("migration_3_1", chemin)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    contenu = Path("config/weights/default.yaml").read_text(encoding="utf-8")

    assert migration._empreinte(contenu) == empreinte_configuration(contenu)
