"""Génère un rapport ESG synthétique long (250 pages par défaut) et sa vérité terrain.

Sert au banc mémoire/temps (scripts/bench_extraction_memoire.py) et au test de fumée Docling réel :
ce que le corpus de référence court (data_test/reference_e2e/) n'exerce pas — la conversion par
lots d'un long rapport, des pages scannées (OCR), un texte sur deux colonnes, des tableaux à
en-têtes groupés et un tableau coupé entre deux pages (le total Scope 3 n'est que sur la seconde).

Les valeurs sont placées à des fractions fixes du document : la vérité terrain (scenario.json, même
forme que data_test/reference_e2e/*/scenario.json, plus `pages_scannees` et `valeur_affichee`)
reste juste quel que soit le nombre de pages. Généré à la demande, jamais commité :

    uv run python scripts/generate_large_esg_pdf.py storage/pilot_corpus/synthetique-250p
    uv run python scripts/generate_large_esg_pdf.py <dossier> --pages 400 --scannees 20
"""

import argparse
import json
from pathlib import Path

import pymupdf

LARGEUR, HAUTEUR = pymupdf.paper_size("a4")
MARGE = 50
NOM = "Helios Materials"
ANNEE = 2025

# Tableaux d'indicateurs : (position dans le document, titre, groupes de lignes).
# Chaque ligne : (code, libellé, valeur, unité, valeur affichée, valeur de l'exercice précédent).
CARBONE = (
    0.35,
    "Tableau 4.2 — Émissions de gaz à effet de serre",
    [
        (
            "Émissions directes et indirectes énergie",
            [
                ("scope_1", "Scope 1 — émissions directes", 48210.0, "tCO2e", "48 210", "51 034"),
                ("scope_2_market_based", "Scope 2 — market-based", 12650.0, "tCO2e", "12 650", "14 020"),
                ("scope_2_location_based", "Scope 2 — location-based", 23480.0, "tCO2e", "23 480", "24 110"),
            ],
        ),
        (
            "Intensités carbone (par million d'euros de chiffre d'affaires)",
            [
                ("intensite_scope_1_2_marketbased", "Intensité Scope 1+2 (market-based)", 18.4, "tCO2e/M€", "18,4", "20,1"),
                ("intensite_scope_1_2_3_hors_cat11", "Intensité Scope 1+2+3 hors catégorie 11", 96.2, "tCO2e/M€", "96,2", "101,7"),
                ("intensite_scope_1_2_3_total", "Intensité Scope 1+2+3 totale", 212.5, "tCO2e/M€", "212,5", "220,3"),
            ],
        ),
    ],
)
DECHETS = (
    0.55,
    "Tableau 5.1 — Déchets",
    [("Gestion des déchets", [("dechets_valorises_pourcentage", "Part des déchets valorisés", 78.0, "%", "78 %", "74 %")])],
)
SOCIAL = (
    0.65,
    "Tableau 7.3 — Effectifs, santé et sécurité",
    [
        (
            "Effectifs",
            [
                ("effectif_total", "Effectif total au 31 décembre", 18240.0, "salariés", "18 240", "17 905"),
                ("femmes_effectif_pourcentage", "Part de femmes dans l'effectif", 31.5, "%", "31,5 %", "30,2 %"),
                ("femmes_management_pourcentage", "Part de femmes dans le management", 27.0, "%", "27 %", "25 %"),
                ("heures_formation_par_employe", "Heures de formation par salarié", 22.6, "heures", "22,6", "21,0"),
            ],
        ),
        (
            "Santé et sécurité",
            [
                ("deces_professionnels", "Décès liés au travail", 1.0, "nombre", "1 décès", "2 décès"),
                ("taux_frequence_accidents", "Taux de fréquence des accidents avec arrêt", 2.31, "taux", "2,31", "2,58"),
            ],
        ),
    ],
)
GOUVERNANCE = (
    0.80,
    "Tableau 9.1 — Composition du conseil d'administration",
    [
        (
            "Conseil d'administration",
            [
                ("taille_conseil", "Nombre d'administrateurs", 14.0, "membres", "14 membres", "13 membres"),
                ("femmes_conseil_pourcentage", "Part de femmes au conseil", 42.9, "%", "42,9 %", "38,5 %"),
                ("administrateurs_independants_pourcentage", "Part d'administrateurs indépendants", 64.3, "%", "64,3 %", "61,5 %"),
            ],
        )
    ],
)
# Page scannée portant une valeur : lisible seulement après OCR.
ENERGIE = (0.25, ("part_renouvelable_pourcentage", "Part d'électricité renouvelable", 46.0, "%", "46 %", "39 %"))
# Tableau des catégories Scope 3 coupé : catégories sur une page, total sur la suivante.
SCOPE_3 = (0.48, ("scope_3", "Total Scope 3", 1284500.0, "tCO2e", "1 284 500", "1 312 800"))

PARAGRAPHE = (
    "{nom} poursuit la transformation de son modèle industriel. Au cours de l'exercice, le groupe "
    "a engagé {n} projets d'efficacité énergétique sur ses sites européens, pour un investissement "
    "cumulé de {m} millions d'euros. Les engagements climatiques validés en 2021 prévoient une "
    "réduction de 42 % des émissions absolues d'ici 2030 par rapport à 2019, couvrant l'ensemble des "
    "filiales consolidées. La démarche s'appuie sur un dialogue régulier avec les parties prenantes, "
    "les fournisseurs stratégiques et les représentants du personnel. "
)


def _page(doc: pymupdf.Document) -> pymupdf.Page:
    return doc.new_page(width=LARGEUR, height=HAUTEUR)


def _entete(page: pymupdf.Page, numero: int) -> None:
    page.insert_text((MARGE, 30), f"{NOM} — Rapport de durabilité {ANNEE}", fontsize=8, color=(0.4, 0.4, 0.4))
    page.insert_text((LARGEUR - MARGE - 20, HAUTEUR - 25), str(numero), fontsize=8)


def _deux_colonnes(page: pymupdf.Page, numero: int) -> None:
    """Texte courant sur deux colonnes, avec des chiffres qui ne sont pas des indicateurs cibles."""
    texte = "".join(PARAGRAPHE.format(nom=NOM, n=numero % 17 + 3, m=numero % 40 + 12) for _ in range(5))
    largeur_colonne = (LARGEUR - 2 * MARGE - 20) / 2
    for i in range(2):
        x0 = MARGE + i * (largeur_colonne + 20)
        page.insert_textbox(pymupdf.Rect(x0, 60, x0 + largeur_colonne, HAUTEUR - 60), texte, fontsize=9)


def _tableau(page: pymupdf.Page, titre: str, groupes, y: float = 80) -> float:
    """Tableau à en-têtes groupés (une ligne de groupe, puis ses lignes), traits dessinés."""
    page.insert_text((MARGE, y), titre, fontsize=12)
    y += 18
    colonnes = [MARGE, MARGE + 280, MARGE + 370, MARGE + 450]
    page.insert_text((colonnes[1], y), f"{ANNEE}", fontsize=9)
    page.insert_text((colonnes[2], y), f"{ANNEE - 1}", fontsize=9)
    page.insert_text((colonnes[3], y), "Unité", fontsize=9)
    for nom_groupe, lignes in groupes:
        y += 20
        page.draw_line((MARGE, y - 13), (LARGEUR - MARGE, y - 13))
        page.insert_text((MARGE, y), nom_groupe, fontsize=9, fontname="helv")
        for _code, libelle, _valeur, unite, affichee, precedente in lignes:
            y += 16
            page.insert_text((MARGE + 10, y), libelle, fontsize=9)
            page.insert_text((colonnes[1], y), affichee, fontsize=9)
            page.insert_text((colonnes[2], y), precedente, fontsize=9)
            page.insert_text((colonnes[3], y), unite, fontsize=9)
    page.draw_line((MARGE, y + 6), (LARGEUR - MARGE, y + 6))
    return y + 30


def _scanner(doc: pymupdf.Document, source: pymupdf.Document) -> None:
    """Ajoute la page unique de `source` comme simple image, sans couche texte (page scannée)."""
    pixmap = source[0].get_pixmap(dpi=150)
    page = _page(doc)
    page.insert_image(page.rect, pixmap=pixmap)


def _ligne_indicateur(ligne) -> dict:
    code, _libelle, valeur, unite, affichee, _precedente = ligne
    return {"code": code, "valeur_attendue": valeur, "unite": unite, "valeur_affichee": affichee}


def generer(dossier: Path, *, pages: int = 250, pages_scannees: int = 10) -> None:
    if pages < 30:
        raise ValueError("Au moins 30 pages : chaque tableau occupe sa propre page.")
    dossier.mkdir(parents=True, exist_ok=True)

    def position(fraction: float) -> int:
        return max(3, round(fraction * pages))

    tableaux = {position(f): (titre, groupes) for f, titre, groupes in (CARBONE, DECHETS, SOCIAL, GOUVERNANCE)}
    page_energie = position(ENERGIE[0])
    page_scope_3 = position(SCOPE_3[0]) + 1  # total sur la seconde page du tableau coupé
    reservees = set(tableaux) | {page_energie, page_scope_3 - 1, page_scope_3, 1, 2}
    # Pages scannées réparties dans le document ; la page énergie en fait toujours partie.
    autres = [p for p in range(3, pages + 1) if p not in reservees]
    pas = max(1, len(autres) // max(1, pages_scannees - 1))
    scannees = sorted({page_energie, *autres[::pas][: pages_scannees - 1]})

    attendus: list[dict] = []
    doc = pymupdf.open()
    for numero in range(1, pages + 1):
        if numero in scannees:
            source = pymupdf.open()
            page = source.new_page(width=LARGEUR, height=HAUTEUR)
            _entete(page, numero)
            if numero == page_energie:
                ligne = ENERGIE[1]
                _tableau(page, "Tableau 3.4 — Énergie", [("Mix énergétique", [ligne])])
                attendus.append({**_ligne_indicateur(ligne), "page_attendue": numero})
            else:
                _deux_colonnes(page, numero)
            _scanner(doc, source)
            continue
        page = _page(doc)
        _entete(page, numero)
        if numero == 1:
            page.insert_text((MARGE, 300), NOM, fontsize=28)
            page.insert_text((MARGE, 340), f"Rapport de durabilité {ANNEE}", fontsize=16)
        elif numero in tableaux:
            titre, groupes = tableaux[numero]
            _tableau(page, titre, groupes)
            for _nom, lignes in groupes:
                attendus.extend({**_ligne_indicateur(lg), "page_attendue": numero} for lg in lignes)
        elif numero == page_scope_3 - 1:
            categories = [
                (f"cat_{i}", f"Catégorie {i}", 0.0, "tCO2e", f"{(i * 37_123) % 400_000:,}".replace(",", " "), "—")
                for i in range(1, 16)
            ]
            _tableau(page, "Tableau 4.5 — Scope 3 par catégorie (suite page suivante)", [("Catégories", categories)])
        elif numero == page_scope_3:
            ligne = SCOPE_3[1]
            _tableau(page, "Tableau 4.5 — Scope 3 par catégorie (fin)", [("Total", [ligne])])
            attendus.append({**_ligne_indicateur(ligne), "page_attendue": numero})
        else:
            _deux_colonnes(page, numero)
    doc.save(dossier / "rapport.pdf", garbage=3, deflate=True)

    scenario = {
        "_a_propos": "Rapport synthétique long (scripts/generate_large_esg_pdf.py) — banc mémoire.",
        "entreprise": {"nom": NOM, "secteur": "Matériaux", "pays": "France"},
        "rapport": {"fichier": "rapport.pdf", "type": "RAPPORT_ESG", "annee_reporting": ANNEE, "pages": pages},
        "pages_scannees": scannees,
        "extraction_attendue": {"indicateurs": sorted(attendus, key=lambda i: i["page_attendue"])},
    }
    (dossier / "scenario.json").write_text(json.dumps(scenario, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dossier", type=Path)
    parser.add_argument("--pages", type=int, default=250)
    parser.add_argument("--scannees", type=int, default=10)
    args = parser.parse_args()
    generer(args.dossier, pages=args.pages, pages_scannees=args.scannees)
    print(f"{args.dossier / 'rapport.pdf'} ({args.pages} pages) et scenario.json écrits.")


if __name__ == "__main__":
    main()
