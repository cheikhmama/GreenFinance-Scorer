"""Indicateurs cibles de l'extraction (déplacés depuis app/ingestion/extractor.py, tâche 5.8).

Module léger : l'API en a besoin (liste de complétude d'un brouillon, rattachement de chaque code à
son pilier) sans importer la pile d'extraction (Docling, torch, bge-m3). Le pipeline les importe
d'ici ; les requêtes sémantiques par code restent dans extractor.py.
"""

from dataclasses import dataclass
from typing import Literal

from app.core.enums import Pillar


@dataclass(frozen=True)
class CibleIndicateur:
    code: str
    # "rapport_score_global" : score transversal auto-déclaré par l'entreprise (ex. "Score global
    # ESG : 66/100"), écrit directement sur ESGReport.declared_global_score — aucun pilier E/S/G
    # ne convient à une valeur transversale aux trois.
    cible: Literal["donnee_carbone", "indicateur_esg", "rapport_score_global"]
    scope: int | None = None
    categorie_ges: str | None = None
    pilier: Pillar | None = None


# Les 7 codes carbone/environnement déjà validés sur le corpus pilote (voir
# data_test/ground_truth.yaml), plus le socle Social/Gouvernance harmonisé retenu en Phase 5 §9
# (voir config/weights/default.yaml et le diagnostic associé — analyse de couverture sur
# data_test/reference_esg_8_entreprises.json), plus un second lot (ci-dessous) ajouté pour la
# transparence humaine (Admin/Auditeur/Investisseur consultant un rapport doit voir ce qui y est
# réellement écrit, avec preuve page par page — garantie G1) : un consommateur légitime distinct
# du moteur de scoring, qui continue de ne lire que les codes présents dans
# config/weights/default.yaml (app/scoring/engine.py ignore silencieusement tout code inconnu du
# YAML — confirmé par lecture directe, aucun risque de modifier un score déjà calculé).
INDICATEURS_CIBLES: list[CibleIndicateur] = [
    CibleIndicateur("scope_1", "donnee_carbone", scope=1),
    # Scope 2 non différencié marché/localisation — le cas le plus courant en pratique (voir
    # data_test/reference_esg_8_entreprises.json, "Scope 2 communiqué comme une valeur unique...
    # pour les 8 entreprises") : sans ce code, un Scope 2 pourtant explicite dans le rapport ne
    # matche jamais scope_2_market_based/location_based et disparaît silencieusement.
    CibleIndicateur("scope_2", "donnee_carbone", scope=2),
    CibleIndicateur(
        "scope_2_market_based", "donnee_carbone", scope=2, categorie_ges="market_based"
    ),
    CibleIndicateur(
        "scope_2_location_based", "donnee_carbone", scope=2, categorie_ges="location_based"
    ),
    CibleIndicateur("scope_3", "donnee_carbone", scope=3),
    CibleIndicateur(
        "intensite_scope_1_2_marketbased", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "intensite_scope_1_2_3_hors_cat11", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "intensite_scope_1_2_3_total", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur("femmes_management_pourcentage", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("deces_professionnels", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("femmes_conseil_pourcentage", "indicateur_esg", pilier=Pillar.GOUVERNANCE),
    # Second lot — transparence humaine, repris du catalogue déjà pensé dans
    # data_test/reference_esg_8_entreprises.json (codes déjà nommés, jamais branchés jusqu'ici).
    # Liste non exhaustive : le pattern (un CibleIndicateur par fait numérique avec page-preuve)
    # se répète, d'autres codes pourront s'ajouter au fil des rapports rencontrés.
    CibleIndicateur("taille_conseil", "indicateur_esg", pilier=Pillar.GOUVERNANCE),
    CibleIndicateur(
        "administrateurs_independants_pourcentage", "indicateur_esg", pilier=Pillar.GOUVERNANCE
    ),
    CibleIndicateur("effectif_total", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("femmes_effectif_pourcentage", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("heures_formation_par_employe", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("taux_frequence_accidents", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur(
        "part_renouvelable_pourcentage", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    CibleIndicateur(
        "dechets_valorises_pourcentage", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT
    ),
    # Scores auto-déclarés par l'entreprise dans sa propre synthèse ESG — par pilier uniquement
    # (pas de "global" : Pilier n'a que 3 valeurs, et la plateforme calcule déjà son propre score
    # officiel via Score/config/weights/default.yaml ; ajouter un score global auto-déclaré à
    # côté créerait une confusion entre "ce que l'entreprise prétend" et "ce que la plateforme
    # calcule" — décision produit à part entière, pas un ajout silencieux ici).
    CibleIndicateur("score_environnement_declare", "indicateur_esg", pilier=Pillar.ENVIRONNEMENT),
    CibleIndicateur("score_social_declare", "indicateur_esg", pilier=Pillar.SOCIAL),
    CibleIndicateur("score_gouvernance_declare", "indicateur_esg", pilier=Pillar.GOUVERNANCE),
    CibleIndicateur("score_global_declare", "rapport_score_global"),
]
