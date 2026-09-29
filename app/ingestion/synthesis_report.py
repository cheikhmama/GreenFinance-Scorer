"""Génération du rapport de synthèse PDF produit par la plateforme (distinct du rapport original
déposé par l'Entreprise, fichier_source sur ESGReport, jamais touché ici).

Composé et régénéré à deux déclencheurs (jamais versionné séparément, le fichier précédent est
simplement remplacé) :
  1. Fin de app/ingestion/extractor.py::run_extraction_pipeline -- score officiel encore
     indisponible à ce stade (calculer_score ne tourne qu'à la validation Auditeur/Admin), la
     section correspondante affiche explicitement "en attente de validation".
  2. Fin de app/admin/review_queue.py::valider_rapport, juste après calculer_score -- régénéré
     avec le score officiel réel.

Séparation stricte, jamais mélangée visuellement, cohérente avec config/weights/default.yaml :
  - les indicateurs ESG réellement extraits (hors les 3 codes auto-déclarés) alimentent le score
    calculé et sont présentés comme tels ;
  - les données carbone Scope 1/2/3 (DonneeCarbone) sont présentées, mais explicitement étiquetées
    comme non intégrées au score calculé (tonnage brut sans dénominateur, voir le commentaire de
    config/weights/default.yaml) ;
  - les scores auto-déclarés par l'entreprise (CODES_AUTO_DECLARES_PAR_PILIER +
    ESGReport.declared_global_score) vivent dans leur propre section "déclaré par l'entreprise",
    jamais confondus avec ce que la plateforme calcule elle-même -- même principe que le reste de
    la plateforme : jamais de boîte noire, jamais un chiffre dont on ne peut pas dire la source.

Fonction pure : ne touche pas la session DB au-delà des lectures nécessaires à l'assemblage,
l'appelant décide de la persistance (app.core.storage) et de l'affectation du chemin résultant à
ESGReport.synthesis_report_path.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlmodel import Session, col, select

from app.core.database import utcnow
from app.ingestion.extractor import CODES_AUTO_DECLARES_PAR_PILIER
from app.ingestion.models import DonneeCarbone, ESGMetric, ESGReport
from app.scoring.engine import score_officiel
from app.scoring.models import ScoreESG

_STYLES = getSampleStyleSheet()
_STYLE_TITRE = ParagraphStyle(
    "TitreSynthese", parent=_STYLES["Heading1"], textColor=colors.HexColor("#0f6b4f")
)
_STYLE_SECTION = ParagraphStyle(
    "SectionSynthese", parent=_STYLES["Heading2"], textColor=colors.HexColor("#16324f")
)
_STYLE_AVERTISSEMENT = ParagraphStyle(
    "AvertissementSynthese", parent=_STYLES["Italic"], textColor=colors.HexColor("#93601f")
)

_EN_TETE_TABLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f4ef")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe2d3")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
)


def _section_score_officiel(score: ScoreESG | None) -> list:
    elements: list = [Paragraph("Score ESG officiel (calculé par la plateforme)", _STYLE_SECTION)]
    if score is None:
        elements.append(
            Paragraph(
                "En attente de validation par un Auditeur -- ce rapport n'a pas encore été "
                "validé, aucun score officiel n'existe à ce jour.",
                _STYLE_AVERTISSEMENT,
            )
        )
        return elements

    donnees = [
        ["Pilier", "Score (/100)"],
        ["Environnement", f"{score.score_environnement:.1f}" if score.score_environnement is not None else "-"],
        ["Social", f"{score.score_social:.1f}" if score.score_social is not None else "-"],
        ["Gouvernance", f"{score.score_gouvernance:.1f}" if score.score_gouvernance is not None else "-"],
        ["Score global", f"{score.valeur_globale:.1f}"],
    ]
    table = Table(donnees, colWidths=[8 * cm, 4 * cm])
    table.setStyle(_EN_TETE_TABLE)
    elements.append(table)
    return elements


def _section_indicateurs(indicateurs: list[ESGMetric]) -> list:
    reels = [i for i in indicateurs if i.metric_code not in CODES_AUTO_DECLARES_PAR_PILIER]
    elements: list = [Paragraph("Indicateurs ESG extraits", _STYLE_SECTION)]
    if not reels:
        elements.append(Paragraph("Aucun indicateur extrait pour ce rapport.", _STYLES["Normal"]))
        return elements

    donnees = [["Code", "Pilier", "Valeur", "Unité", "Année", "Page source"]]
    for indicateur in reels:
        donnees.append(
            [
                indicateur.metric_code,
                indicateur.pillar.value,
                f"{indicateur.value:g}",
                indicateur.unit or "-",
                str(indicateur.value_year) if indicateur.value_year else "-",
                f"p. {indicateur.proof.page_debut}",
            ]
        )
    table = Table(donnees, colWidths=[5 * cm, 2.7 * cm, 2 * cm, 2 * cm, 1.8 * cm, 2 * cm])
    table.setStyle(_EN_TETE_TABLE)
    elements.append(table)
    return elements


def _section_carbone(donnees_carbone: list[DonneeCarbone]) -> list:
    elements: list = [Paragraph("Émissions carbone (Scope 1/2/3)", _STYLE_SECTION)]
    elements.append(
        Paragraph(
            "Valeurs brutes en tCO2e, non intégrées au score calculé -- comparer un tonnage "
            "absolu entre entreprises de tailles différentes n'a pas de sens sans dénominateur "
            "(voir config/weights/default.yaml). Les 3 indicateurs d'intensité carbone déjà "
            "présents dans la section précédente sont le proxy normalisé retenu pour le score.",
            _STYLE_AVERTISSEMENT,
        )
    )
    if not donnees_carbone:
        elements.append(Paragraph("Aucune donnée carbone extraite pour ce rapport.", _STYLES["Normal"]))
        return elements

    donnees = [["Scope", "Catégorie GES", "Valeur (tCO2e)", "Année", "Page source"]]
    for dc in donnees_carbone:
        donnees.append(
            [
                str(dc.scope),
                dc.categorie_ges or "-",
                f"{dc.valeur_tonnes_co2e:g}",
                str(dc.annee_valeur or dc.annee),
                f"p. {dc.preuve.page_debut}",
            ]
        )
    table = Table(donnees, colWidths=[2 * cm, 3.5 * cm, 3 * cm, 2 * cm, 2 * cm])
    table.setStyle(_EN_TETE_TABLE)
    elements.append(table)
    return elements


def _section_declare_par_lentreprise(rapport: ESGReport, indicateurs: list[ESGMetric]) -> list:
    declares = [i for i in indicateurs if i.metric_code in CODES_AUTO_DECLARES_PAR_PILIER]
    elements: list = [Paragraph("Déclaré par l'entreprise (non vérifié indépendamment)", _STYLE_SECTION)]
    elements.append(
        Paragraph(
            "Cette section reprend des scores communiqués par l'entreprise elle-même dans son "
            "propre rapport -- jamais mélangés au score officiel calculé par la plateforme "
            "ci-dessus, qui seul fait foi pour la comparaison entre entreprises.",
            _STYLE_AVERTISSEMENT,
        )
    )
    lignes = [["Élément", "Valeur déclarée"]]
    if rapport.declared_global_score is not None:
        lignes.append(["Score ESG global déclaré", f"{rapport.declared_global_score:g}"])
    for indicateur in declares:
        lignes.append([indicateur.metric_code, f"{indicateur.value:g} {indicateur.unit or ''}".strip()])
    if len(lignes) == 1:
        elements.append(Paragraph("Aucun score auto-déclaré trouvé dans ce rapport.", _STYLES["Normal"]))
        return elements

    table = Table(lignes, colWidths=[8 * cm, 4 * cm])
    table.setStyle(_EN_TETE_TABLE)
    elements.append(table)
    return elements


def generer_rapport_synthese(session: Session, rapport: ESGReport) -> bytes:
    indicateurs = list(
        session.exec(select(ESGMetric).where(col(ESGMetric.report_id) == rapport.id)).all()
    )
    donnees_carbone = list(
        session.exec(select(DonneeCarbone).where(col(DonneeCarbone.rapport_id) == rapport.id)).all()
    )
    score = score_officiel(session, rapport.id)

    tampon = io.BytesIO()
    document = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    elements: list = [
        Paragraph(f"Rapport de synthèse ESG -- {rapport.company.name}", _STYLE_TITRE),
        Paragraph(
            f"{rapport.company.sector} · {rapport.company.country} · Année de reporting "
            f"{rapport.fiscal_year or '-'} · Généré le "
            f"{utcnow().strftime('%d/%m/%Y')}",
            _STYLES["Normal"],
        ),
        Spacer(1, 0.6 * cm),
    ]
    elements += _section_score_officiel(score)
    elements.append(Spacer(1, 0.5 * cm))
    elements += _section_indicateurs(indicateurs)
    elements.append(Spacer(1, 0.5 * cm))
    elements += _section_carbone(donnees_carbone)
    elements.append(Spacer(1, 0.5 * cm))
    elements += _section_declare_par_lentreprise(rapport, indicateurs)

    document.build(elements)
    return tampon.getvalue()
