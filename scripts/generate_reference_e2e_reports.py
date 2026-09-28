"""Génère les rapports PDF synthétiques du corpus de référence E2E (data_test/reference_e2e/).

Distinct de data_test/ground_truth.yaml (corpus de rapports RÉELS, utilisé pour valider la
PRÉCISION d'extraction face à la vraie complexité documentaire). Ce corpus-ci sert à valider le
WORKFLOW COMPLET — dépôt, extraction, audit, décision, publication — avec des rapports courts et
sans ambiguïté, contenant volontairement les 7 codes de app/ingestion/extractor.py::INDICATEURS_CIBLES.

Régénérer après une modification d'un scenario.json :
    uv run python scripts/generate_reference_e2e_reports.py
"""

import json
from pathlib import Path
from typing import Any

import pymupdf

RACINE = Path(__file__).resolve().parent.parent / "data_test" / "reference_e2e"

LABELS_INDICATEURS = {
    "scope_1": "Émissions directes (Scope 1)",
    "scope_2": "Émissions indirectes énergie, non différenciées (Scope 2)",
    "scope_2_market_based": "Émissions indirectes énergie - méthode market-based (Scope 2)",
    "scope_2_location_based": "Émissions indirectes énergie - méthode location-based (Scope 2)",
    "scope_3": "Autres émissions indirectes de la chaîne de valeur (Scope 3)",
    "intensite_scope_1_2_marketbased": "Intensité carbone Scope 1+2 (market-based)",
    "intensite_scope_1_2_3_hors_cat11": "Intensité carbone Scope 1+2+3 (hors catégorie 11)",
    "intensite_scope_1_2_3_total": "Intensité carbone Scope 1+2+3 (total)",
    "part_renouvelable_pourcentage": "Part d'énergie renouvelable dans le mix",
    "dechets_valorises_pourcentage": "Part des déchets valorisés ou recyclés",
    # Socle Social/Gouvernance harmonisé (Phase 5 §9) — voir config/weights/default.yaml.
    "femmes_management_pourcentage": "Part de femmes au sein du management",
    "deces_professionnels": "Décès professionnels sur l'exercice",
    "femmes_conseil_pourcentage": "Part de femmes au conseil d'administration",
    # Second lot — transparence humaine (voir app/ingestion/extractor.py::INDICATEURS_CIBLES).
    "taille_conseil": "Taille du conseil d'administration",
    "administrateurs_independants_pourcentage": "Part d'administrateurs indépendants",
    "effectif_total": "Effectif total",
    "femmes_effectif_pourcentage": "Part de femmes dans l'effectif total",
    "heures_formation_par_employe": "Heures de formation moyennes par salarié",
    "taux_frequence_accidents": "Taux de fréquence des accidents avec arrêt",
    "score_environnement_declare": "Score Environnement auto-déclaré",
    "score_social_declare": "Score Social auto-déclaré",
    "score_gouvernance_declare": "Score Gouvernance auto-déclaré",
    "score_global_declare": "Score ESG global auto-déclaré",
}

_CODES_ENVIRONNEMENT = {
    "scope_1",
    "scope_2",
    "scope_2_market_based",
    "scope_2_location_based",
    "scope_3",
    "intensite_scope_1_2_marketbased",
    "intensite_scope_1_2_3_hors_cat11",
    "intensite_scope_1_2_3_total",
    "part_renouvelable_pourcentage",
    "dechets_valorises_pourcentage",
}

_CODES_SCORES_DECLARES = {
    "score_environnement_declare",
    "score_social_declare",
    "score_gouvernance_declare",
    "score_global_declare",
}


def _page_couverture(doc: pymupdf.Document, nom: str, annee: int) -> None:
    page = doc.new_page()
    page.insert_text((72, 220), nom, fontsize=26, fontname="helv")
    page.insert_text((72, 260), "Rapport de durabilité", fontsize=16, fontname="helv")
    page.insert_text((72, 285), f"Exercice {annee}", fontsize=13, fontname="helv")
    page.insert_text(
        (72, 760),
        "Document de test - corpus de référence E2E GreenFinance Scorer, valeurs synthétiques.",
        fontsize=8,
        fontname="helv",
    )


def _page_sommaire(doc: pymupdf.Document, nom: str) -> None:
    page = doc.new_page()
    page.insert_text((72, 72), "Sommaire", fontsize=18, fontname="helv")
    lignes = [
        "1. Message de la direction",
        "2. Performance environnementale et climat",
        "3. Indicateurs sociaux et de gouvernance",
        "4. Perspectives et engagements",
        "5. Notes méthodologiques",
    ]
    for i, ligne in enumerate(lignes):
        page.insert_text((90, 120 + i * 24), ligne, fontsize=12, fontname="helv")
    page.insert_textbox(
        pymupdf.Rect(72, 240, 520, 420),
        f"{nom} publie chaque année un rapport de durabilité couvrant sa performance "
        "environnementale, sociale et de gouvernance. Le présent document rend compte des "
        "émissions de gaz à effet de serre de l'exercice, calculées conformément au GHG Protocol, "
        "ainsi que des principales actions de gouvernance de l'année.",
        fontsize=11,
        fontname="helv",
    )


def _page_tableau_indicateurs(
    doc: pymupdf.Document, titre: str, sous_titre: str, indicateurs: list[dict[str, Any]]
) -> None:
    page = doc.new_page()
    page.insert_text((72, 72), titre, fontsize=16, fontname="helv")
    page.insert_text((72, 100), sous_titre, fontsize=10, fontname="helv")

    y = 140
    page.insert_text((72, y), "Indicateur", fontsize=10, fontname="helv")
    page.insert_text((430, y), "Valeur", fontsize=10, fontname="helv")
    page.insert_text((500, y), "Unité", fontsize=10, fontname="helv")
    y += 6
    page.draw_line((72, y), (560, y))
    y += 22

    for indicateur in indicateurs:
        label = LABELS_INDICATEURS[indicateur["code"]]
        page.insert_textbox(pymupdf.Rect(72, y - 10, 420, y + 20), label, fontsize=9.5, fontname="helv")
        valeur = indicateur["valeur_attendue"]
        # 3 décimales sous 10 (sinon un ratio comme 0.041 tCO2e/t minerai s'arrondirait à "0.0",
        # indiscernable d'un zéro réel) ; 1 décimale au-delà, où l'échelle rend ce niveau de
        # précision sans intérêt visuel (ex. 17 990 000.0 tCO2e).
        decimales = 3 if abs(valeur) < 10 else 1
        valeur_str = f"{valeur:,.{decimales}f}".replace(",", " ")
        page.insert_text((430, y), valeur_str, fontsize=9.5, fontname="helv")
        page.insert_text((500, y), indicateur["unite"], fontsize=9.5, fontname="helv")
        y += 34

    page.insert_text(
        (72, 740),
        "Périmètre : entités consolidées. Méthode : rapportée, non recalculée par un tiers.",
        fontsize=8,
        fontname="helv",
    )


def _page_perspectives(doc: pymupdf.Document, nom: str) -> None:
    """Page narrative sans aucune donnée chiffrée ciblée par le pipeline — vérifie que celui-ci
    ignore correctement une page non pertinente, même quand son titre ("Perspectives et
    engagements") évoque un sujet proche des deux pages de données qui l'entourent."""
    page = doc.new_page()
    page.insert_text((72, 72), "4. Perspectives et engagements", fontsize=16, fontname="helv")
    page.insert_textbox(
        pymupdf.Rect(72, 110, 520, 400),
        f"{nom} a poursuivi en 2025 le renforcement de sa gouvernance climat, avec un comité "
        "dédié rattaché au conseil d'administration et une revue trimestrielle de la trajectoire "
        "de réduction des émissions. Sur le volet social, l'entreprise a maintenu ses programmes "
        "de formation et de prévention. Cette page ne contient volontairement aucune donnée "
        "chiffrée ciblée par le pipeline d'extraction - elle sert à vérifier que celui-ci ignore "
        "correctement les pages non pertinentes.",
        fontsize=11,
        fontname="helv",
    )


def _page_methodologie(doc: pymupdf.Document) -> None:
    page = doc.new_page()
    page.insert_text((72, 72), "5. Notes méthodologiques", fontsize=16, fontname="helv")
    page.insert_textbox(
        pymupdf.Rect(72, 110, 520, 300),
        "Les émissions de Scope 1, 2 et 3 sont calculées selon le GHG Protocol Corporate "
        "Standard. Le Scope 2 est rapporté selon les deux méthodes market-based et "
        "location-based. Les intensités carbone rapportent les émissions à l'activité de "
        "l'exercice. Document de test à des fins de validation de plateforme - les valeurs "
        "n'engagent aucune entreprise réelle.",
        fontsize=11,
        fontname="helv",
    )


def generer_pdf(dossier: Path, scenario: dict[str, Any]) -> None:
    nom = scenario["entreprise"]["nom"]
    annee = scenario["rapport"]["annee_reporting"]
    indicateurs = scenario["extraction_attendue"]["indicateurs"]
    indicateurs_climat = [i for i in indicateurs if i["code"] in _CODES_ENVIRONNEMENT]
    indicateurs_scores = [i for i in indicateurs if i["code"] in _CODES_SCORES_DECLARES]
    indicateurs_social_gouvernance = [
        i
        for i in indicateurs
        if i["code"] not in _CODES_ENVIRONNEMENT and i["code"] not in _CODES_SCORES_DECLARES
    ]

    doc = pymupdf.open()
    _page_couverture(doc, nom, annee)
    _page_sommaire(doc, nom)
    _page_tableau_indicateurs(
        doc,
        "2. Performance environnementale et climat",
        "Émissions de gaz à effet de serre (GHG Protocol) - valeurs de l'exercice de reporting.",
        indicateurs_climat,
    )
    _page_tableau_indicateurs(
        doc,
        "3. Indicateurs sociaux et de gouvernance",
        "Socle harmonisé Social/Gouvernance (Phase 5 §9) - valeurs de l'exercice de reporting.",
        indicateurs_social_gouvernance,
    )
    if indicateurs_scores:
        _page_tableau_indicateurs(
            doc,
            "3bis. Scores ESG auto-déclarés",
            "Scores publiés par l'entreprise elle-même dans sa propre synthèse — distincts du "
            "score recalculé par le moteur de scoring de la plateforme.",
            indicateurs_scores,
        )
    _page_perspectives(doc, nom)
    _page_methodologie(doc)

    fichier = dossier / scenario["rapport"]["fichier"]
    doc.save(fichier)
    doc.close()
    print(f"écrit {fichier} ({len(indicateurs)} indicateurs, page {indicateurs[0]['page_attendue']})")


def main() -> None:
    for dossier in sorted(p for p in RACINE.iterdir() if p.is_dir()):
        scenario_path = dossier / "scenario.json"
        if not scenario_path.exists():
            continue
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        generer_pdf(dossier, scenario)


if __name__ == "__main__":
    main()
