"""Generate the final GreenFinance Scorer defence presentation.

The deck is intentionally built with native PowerPoint shapes so it remains
editable. It uses only verified project facts and labels simulated UI data.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"
ASSET_DIR = OUT_DIR / "presentation_assets"
PPTX_PATH = OUT_DIR / "GreenFinance_Scorer_Soutenance_FINAL_REVISEE.pptx"
SCRIPT_PATH = OUT_DIR / "GreenFinance_Scorer_Script_Oral_REVISE.md"

SLIDE_W = 13.333
SLIDE_H = 7.5


def rgb(value: str) -> RGBColor:
    value = value.lstrip("#")
    return RGBColor(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


NAVY = "#0B1F33"
BLUE = "#16324F"
GREEN = "#0F6B4F"
EMERALD = "#16A36B"
MINT = "#E8F4EF"
OFF_WHITE = "#F4F8F6"
WHITE = "#FFFFFF"
SLATE = "#5B6573"
MID = "#98A2B3"
LINE = "#DDE6E2"
AMBER = "#E59A21"
AMBER_LIGHT = "#FFF4DF"
PURPLE = "#7C3AED"
PURPLE_LIGHT = "#F2ECFF"
TEAL = "#0E7490"
TEAL_LIGHT = "#E6F7FA"
RED = "#C2413B"
RED_LIGHT = "#FDECEC"

FONT_HEAD = "Aptos Display"
FONT_BODY = "Aptos"


def _set_fill(shape, color: str) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(color)


def _set_line(shape, color: str | None = None, width: float = 1.0) -> None:
    if color is None:
        shape.line.fill.background()
        return
    shape.line.color.rgb = rgb(color)
    shape.line.width = Pt(width)


def add_box(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = WHITE,
    line: str | None = LINE,
    radius: bool = True,
    line_width: float = 1.0,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    _set_fill(shape, fill)
    _set_line(shape, line, line_width)
    return shape


def add_text(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    text: str,
    *,
    size: float = 14,
    color: str = BLUE,
    bold: bool = False,
    font: str = FONT_BODY,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margin: float = 0.0,
    italic: bool = False,
    uppercase: bool = False,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    paragraph = tf.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_before = Pt(0)
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = text.upper() if uppercase else text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = rgb(color)
    return box


def add_multiline(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    lines: list[str],
    *,
    size: float = 13,
    color: str = BLUE,
    bullet_color: str = GREEN,
    gap: float = 4,
    bold_first: bool = False,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0)
    tf.margin_right = Inches(0)
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    for index, line in enumerate(lines):
        paragraph = tf.paragraphs[0] if index == 0 else tf.add_paragraph()
        paragraph.space_before = Pt(0)
        paragraph.space_after = Pt(gap)
        bullet = paragraph.add_run()
        bullet.text = "• "
        bullet.font.name = FONT_BODY
        bullet.font.size = Pt(size)
        bullet.font.bold = True
        bullet.font.color.rgb = rgb(bullet_color)
        run = paragraph.add_run()
        run.text = line
        run.font.name = FONT_BODY
        run.font.size = Pt(size)
        run.font.bold = bold_first and index == 0
        run.font.color.rgb = rgb(color)
    return box


def add_badge(
    slide,
    x: float,
    y: float,
    text: str,
    *,
    fill: str = MINT,
    color: str = GREEN,
    width: float | None = None,
):
    width = width or max(0.85, 0.09 * len(text) + 0.38)
    add_box(slide, x, y, width, 0.32, fill=fill, line=None, radius=True)
    add_text(
        slide,
        x,
        y + 0.01,
        width,
        0.28,
        text,
        size=8.5,
        color=color,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
        uppercase=True,
    )
    return width


def add_circle_label(
    slide,
    x: float,
    y: float,
    d: float,
    label: str,
    *,
    fill: str = GREEN,
    color: str = WHITE,
    size: float = 13,
):
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    _set_fill(circle, fill)
    _set_line(circle, None)
    add_text(
        slide,
        x,
        y,
        d,
        d,
        label,
        size=size,
        color=color,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )
    return circle


def add_arrow(slide, x: float, y: float, w: float, h: float, color: str = EMERALD):
    arrow = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y), Inches(w), Inches(h))
    _set_fill(arrow, color)
    _set_line(arrow, None)
    return arrow


def add_background(slide, color: str) -> None:
    add_box(slide, 0, 0, SLIDE_W, SLIDE_H, fill=color, line=None, radius=False)


def add_brand(slide, *, dark: bool = False) -> None:
    add_circle_label(slide, 0.62, 0.38, 0.36, "G", fill=EMERALD, size=11)
    add_text(
        slide,
        1.08,
        0.42,
        2.2,
        0.26,
        "GreenFinance Scorer",
        size=10.5,
        color=WHITE if dark else BLUE,
        bold=True,
        valign=MSO_ANCHOR.MIDDLE,
    )


def add_header(
    slide,
    eyebrow: str,
    title: str,
    subtitle: str | None = None,
    *,
    dark: bool = False,
    title_size: float = 27,
) -> None:
    title_color = WHITE if dark else NAVY
    subtitle_color = "#C7D4DF" if dark else SLATE
    add_text(slide, 0.72, 0.42, 6.8, 0.25, eyebrow, size=9.5, color=EMERALD, bold=True, uppercase=True)
    add_text(slide, 0.72, 0.72, 11.9, 0.62, title, size=title_size, color=title_color, bold=True, font=FONT_HEAD)
    if subtitle:
        add_text(slide, 0.72, 1.35, 11.7, 0.4, subtitle, size=12.5, color=subtitle_color)


def add_footer(slide, number: int, *, dark: bool = False, source: str | None = None) -> None:
    color = "#91A4B5" if dark else MID
    add_text(slide, 12.15, 7.08, 0.45, 0.24, f"{number:02d}", size=8.5, color=color, bold=True, align=PP_ALIGN.RIGHT)


def add_picture_card(slide, path: Path, x: float, y: float, w: float, h: float, *, border: str = LINE):
    add_box(slide, x - 0.06, y - 0.06, w + 0.12, h + 0.12, fill=WHITE, line=border, radius=True)
    slide.shapes.add_picture(str(path), Inches(x), Inches(y), width=Inches(w), height=Inches(h))


def add_note(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text.strip()


def new_slide(prs: Presentation, color: str = OFF_WHITE):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_background(slide, color)
    return slide


def slide_01(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, NAVY)
    add_brand(slide, dark=True)
    add_badge(slide, 10.15, 0.43, "Projet de fin d’études", fill="#173A56", color="#BFEEDC", width=2.45)
    add_text(slide, 0.78, 1.28, 7.6, 0.78, "GreenFinance Scorer", size=40, color=WHITE, bold=True, font=FONT_HEAD)
    add_text(
        slide,
        0.8,
        2.16,
        7.7,
        1.3,
        "Plateforme open source d’évaluation ESG et climatique\ndes portefeuilles d’investissement",
        size=21,
        color="#BFEEDC",
        bold=True,
        font=FONT_HEAD,
    )

    add_box(slide, 8.9, 1.5, 3.55, 3.15, fill="#132C43", line="#29475F", radius=True)
    add_text(slide, 9.25, 1.82, 2.8, 0.28, "PÉRIMÈTRE DU PROJET", size=10, color="#BFEEDC", bold=True)
    cover_items = [
        ("ESG", "Scoring configurable"),
        ("CO₂", "Scopes 1, 2 et 3"),
        ("PCAF", "Empreinte financée"),
        ("PDF", "Preuves documentaires"),
    ]
    y = 2.32
    for icon, label in cover_items:
        add_circle_label(slide, 9.25, y, 0.52, icon, fill=EMERALD, size=8.5)
        add_text(slide, 9.95, y + 0.06, 2.0, 0.32, label, size=10.8, color=WHITE, bold=True)
        y += 0.58

    add_box(slide, 0.8, 4.45, 7.55, 1.75, fill="#132C43", line="#29475F", radius=True)
    metadata = [
        ("PRÉSENTÉ PAR", "[Nom et prénom]"),
        ("FORMATION", "[Intitulé du Master]"),
        ("ÉTABLISSEMENT", "[Nom de l’établissement]"),
        ("ENCADREMENT", "[Nom de l’encadrant]"),
    ]
    for idx, (label, value) in enumerate(metadata):
        row, col = divmod(idx, 2)
        x = 1.08 + col * 3.55
        y = 4.75 + row * 0.68
        add_text(slide, x, y, 1.25, 0.2, label, size=8, color="#91A4B5", bold=True)
        add_text(slide, x, y + 0.23, 2.7, 0.3, value, size=11, color=WHITE, bold=True)

    add_text(slide, 9.0, 5.18, 3.35, 0.28, "ANNÉE ACADÉMIQUE", size=8.5, color="#91A4B5", bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, 9.0, 5.55, 3.35, 0.38, "2025–2026", size=18, color=WHITE, bold=True, font=FONT_HEAD, align=PP_ALIGN.CENTER)
    add_note(
        slide,
        """
        Durée cible : 40 secondes.

        Bonjour. Je vais vous présenter GreenFinance Scorer, une plateforme open source d’évaluation ESG et climatique des portefeuilles d’investissement. Elle couvre l’analyse des rapports, le scoring configurable, les émissions Scope 1, 2 et 3, l’empreinte financée et la traçabilité documentaire.

        Transition : La présentation est organisée en six parties.
        """,
    )
    return "01", "Page de garde", "0:40"


def slide_02(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs)
    add_header(slide, "PARTIE 00", "SOMMAIRE — Structure de la soutenance", "Organisation générale de la présentation.")
    sections = [
        ("01", "INTRODUCTION", "Contexte · problématique · solution · objectifs", GREEN, MINT),
        ("02", "ANALYSE FONCTIONNELLE", "Acteurs · fonctionnalités · workflow", PURPLE, PURPLE_LIGHT),
        ("03", "CONCEPTION TECHNIQUE", "Pipeline · architecture · technologies", TEAL, TEAL_LIGHT),
        ("04", "DÉMONSTRATION", "Parcours utilisateur de bout en bout", AMBER, AMBER_LIGHT),
        ("05", "ÉVALUATION", "Résultats · recommandations · perspectives", BLUE, "#EAF0F5"),
        ("06", "CONCLUSION", "Synthèse · contribution · questions", EMERALD, MINT),
    ]
    for idx, (num, title, body, accent, fill) in enumerate(sections):
        row, col = divmod(idx, 2)
        x = 0.78 + col * 6.18
        y = 1.9 + row * 1.53
        add_box(slide, x, y, 5.72, 1.16, fill=WHITE, line=LINE, radius=True)
        add_circle_label(slide, x + 0.25, y + 0.25, 0.66, num, fill=accent, size=10)
        add_text(slide, x + 1.12, y + 0.2, 4.1, 0.3, title, size=12.2, color=NAVY, bold=True)
        add_text(slide, x + 1.12, y + 0.59, 4.15, 0.34, body, size=10.3, color=SLATE)
        add_box(slide, x + 5.52, y + 0.2, 0.06, 0.76, fill=accent, line=None, radius=False)
    add_footer(slide, 2)
    add_note(
        slide,
        """
        Durée cible : 45 secondes.

        La soutenance commence par le contexte, la problématique, la solution et les objectifs. Elle présente ensuite les acteurs et le workflow, puis le pipeline documentaire, l’architecture et les choix technologiques. Une démonstration illustre le parcours complet. Enfin, les résultats, les recommandations, les perspectives et la conclusion sont présentés.

        Transition : Commençons par le contexte et le besoin à l’origine du projet.
        """,
    )
    return "02", "Sommaire", "0:45"


def slide_03(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, NAVY)
    add_header(slide, "PARTIE 01", "INTRODUCTION — Contexte et problématique", "Analyse du besoin et limites des approches existantes.", dark=True, title_size=25)
    add_badge(slide, 0.82, 1.78, "Complexité documentaire", fill="#173A56", color="#BFEEDC", width=1.95)
    add_text(slide, 0.84, 2.27, 3.95, 1.28, "Rapport ESG : de quelques pages à\nplusieurs centaines de pages", size=20.5, color=WHITE, bold=True, font=FONT_HEAD)
    add_text(slide, 0.84, 3.67, 3.85, 0.78, "Textes, tableaux, annexes, unités, périodes et périmètres hétérogènes.", size=11.8, color="#C7D4DF")
    add_badge(slide, 0.84, 4.75, "Extraction manuelle coûteuse", fill="#173A56", color="#BFEEDC", width=2.15)

    # Black-box illustration.
    add_box(slide, 5.2, 1.78, 2.2, 3.65, fill="#13202B", line="#365267", radius=True)
    add_text(slide, 5.55, 2.15, 1.5, 0.4, "DONNÉES", size=10, color="#91A4B5", bold=True, align=PP_ALIGN.CENTER)
    for i in range(3):
        add_box(slide, 5.7 + i * 0.08, 2.72 + i * 0.12, 1.2, 1.38, fill="#203747", line="#4B6B82", radius=True)
    add_text(slide, 5.85, 3.2, 0.9, 0.25, "PDF", size=13, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_arrow(slide, 7.7, 3.18, 0.5, 0.28, color="#4B6B82")
    add_box(slide, 8.36, 1.78, 2.5, 3.65, fill="#050A0E", line="#365267", radius=True)
    add_text(slide, 8.72, 2.28, 1.8, 0.35, "MÉTHODE OPAQUE", size=10.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_multiline(slide, 8.72, 2.85, 1.82, 1.6, ["Périmètre", "Mesure", "Poids"], size=11, color="#C7D4DF", bullet_color=AMBER, gap=9)
    add_arrow(slide, 11.14, 3.18, 0.48, 0.28, color=AMBER)
    add_circle_label(slide, 11.85, 2.65, 1.15, "?", fill=AMBER, color=NAVY, size=26)
    add_text(slide, 11.42, 4.1, 1.95, 0.58, "SCORE DIFFICILE\nÀ AUDITER", size=9.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER)

    chips = ["Méthodes propriétaires", "Pondérations imposées", "Accès coûteux", "Provenance difficile à vérifier"]
    x = 5.2
    for idx, chip in enumerate(chips):
        width = [1.75, 1.75, 1.35, 2.2][idx]
        add_badge(slide, x, 5.78, chip, fill="#173A56", color="#C7D4DF", width=width)
        x += width + 0.18
    add_footer(slide, 3, dark=True)
    add_note(
        slide,
        """
        Durée cible : 1 minute 30.

        Les données ESG sont publiées dans des rapports dont la longueur peut aller de quelques pages à plusieurs centaines de pages. Les formats, unités, années et périmètres varient fortement. À cette difficulté documentaire s’ajoutent des méthodes propriétaires, des pondérations imposées et une provenance parfois difficile à vérifier. Le besoin est donc double : automatiser l’analyse et rendre chaque résultat auditable.

        Transition : La solution proposée répond directement à ces deux dimensions.
        """,
    )
    return "03", "Contexte et problématique", "1:40"


def slide_04(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs)
    add_header(slide, "PARTIE 01", "INTRODUCTION — Solution proposée", "Processus d’analyse, de vérification et de calcul.", title_size=25)

    stages = [
        ("01", "ANALYSER", "Comprendre le PDF"),
        ("02", "EXTRAIRE", "Valeur + unité + année"),
        ("03", "VÉRIFIER", "Page et preuve"),
        ("04", "CALCULER", "ESG + carbone"),
        ("05", "EXPLIQUER", "Décision auditable"),
    ]
    x = 0.78
    for idx, (num, label, detail) in enumerate(stages):
        add_box(slide, x, 2.0, 2.15, 1.25, fill=WHITE, line=LINE, radius=True)
        add_circle_label(slide, x + 0.17, 2.2, 0.52, num, fill=GREEN if idx < 3 else NAVY, size=9)
        add_text(slide, x + 0.82, 2.16, 1.12, 0.25, label, size=9.5, color=GREEN if idx < 3 else NAVY, bold=True)
        add_text(slide, x + 0.82, 2.48, 1.1, 0.48, detail, size=9.8, color=SLATE)
        if idx < len(stages) - 1:
            add_arrow(slide, x + 2.22, 2.48, 0.3, 0.2, color="#9FCAB9")
        x += 2.5

    # Evidence record.
    add_box(slide, 0.8, 3.82, 7.6, 2.42, fill=WHITE, line=LINE, radius=True)
    add_badge(slide, 1.08, 4.08, "Donnée extraite et vérifiée", width=2.05)
    add_text(slide, 1.08, 4.55, 2.5, 0.25, "SCOPE 1", size=9, color=SLATE, bold=True)
    add_text(slide, 1.08, 4.86, 2.95, 0.43, "143 510 tCO₂e", size=22, color=NAVY, bold=True, font=FONT_HEAD)
    add_text(slide, 1.08, 5.39, 2.7, 0.27, "FY2024 · publié par l’entreprise", size=10, color=SLATE)
    add_box(slide, 4.12, 4.23, 3.92, 1.55, fill=MINT, line=None, radius=True)
    add_text(slide, 4.4, 4.49, 3.35, 0.32, "Rapport officiel · page 3", size=10.5, color=GREEN, bold=True)
    add_text(slide, 4.4, 4.9, 3.28, 0.62, "« Scope 1 emissions ... 143,510 mtCO₂e »", size=11.2, color=BLUE, italic=True)

    values = [("Traçable", "Document + page"), ("Configurable", "Poids versionnés"), ("Reproductible", "Méthode explicite")]
    y = 3.82
    for idx, (label, detail) in enumerate(values):
        add_box(slide, 8.82, y, 3.48, 0.68, fill=[MINT, PURPLE_LIGHT, TEAL_LIGHT][idx], line=None, radius=True)
        add_circle_label(slide, 9.03, y + 0.12, 0.42, "✓", fill=[GREEN, PURPLE, TEAL][idx], size=8.5)
        add_text(slide, 9.62, y + 0.1, 1.25, 0.23, label, size=10.8, color=NAVY, bold=True)
        add_text(slide, 10.86, y + 0.1, 1.15, 0.35, detail, size=9.3, color=SLATE, align=PP_ALIGN.RIGHT)
        y += 0.86
    add_footer(slide, 4)
    add_note(
        slide,
        """
        Durée cible : 1 minute 30.

        La plateforme applique cinq opérations : analyser, extraire, vérifier, calculer et expliquer. Chaque donnée conserve sa valeur originale, son unité, sa période, son périmètre, le document et la page correspondante. Si une information n’est pas clairement présente, le système la signale pour vérification au lieu de produire une valeur non justifiée.

        Transition : Cette chaîne répond à quatre objectifs complémentaires.
        """,
    )
    return "04", "Solution proposée", "1:30"


def slide_05(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, NAVY)
    add_header(slide, "PARTIE 01", "INTRODUCTION — Objectifs et valeur ajoutée", "Quatre objectifs intégrés dans une plateforme ouverte.", dark=True, title_size=25)
    add_circle_label(slide, 5.55, 2.4, 2.2, "OUVERT\n& AUDITABLE", fill=GREEN, size=16)
    add_text(slide, 5.8, 4.72, 1.72, 0.44, "Une méthode visible\net configurable", size=10.5, color="#BFEEDC", bold=True, align=PP_ALIGN.CENTER)

    cards = [
        (0.82, 2.05, "01", "Extraire", "Automatiser les données ESG et carbone avec leurs preuves.", MINT, GREEN),
        (8.35, 2.05, "02", "Configurer", "Versionner les pondérations et rendre le score explicable.", PURPLE_LIGHT, PURPLE),
        (0.82, 4.6, "03", "Mesurer", "Scopes 1–3 et empreinte financée selon la méthode retenue.", TEAL_LIGHT, TEAL),
        (8.35, 4.6, "04", "Décider", "Comparer les entreprises et analyser un portefeuille traçable.", AMBER_LIGHT, AMBER),
    ]
    for x, y, num, title, body, fill, accent in cards:
        add_box(slide, x, y, 4.1, 1.5, fill="#132C43", line="#29475F", radius=True)
        add_circle_label(slide, x + 0.25, y + 0.26, 0.58, num, fill=accent, size=9)
        add_text(slide, x + 1.03, y + 0.25, 2.6, 0.3, title, size=15, color=WHITE, bold=True, font=FONT_HEAD)
        add_text(slide, x + 1.03, y + 0.67, 2.65, 0.58, body, size=10.5, color="#C7D4DF")
    add_footer(slide, 5, dark=True)
    add_note(
        slide,
        """
        Durée cible : 1 minute 20.

        Le projet intègre dans une même plateforme l’extraction sourcée, le scoring configurable, le calcul carbone et l’analyse de portefeuille. Les hypothèses, les pondérations et les preuves restent visibles afin que les résultats puissent être vérifiés et reproduits.

        Transition : Cette chaîne réunit six acteurs autour de la même donnée de référence.
        """,
    )
    return "05", "Objectifs et valeur ajoutée", "1:20"


def slide_06(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs)
    add_header(slide, "PARTIE 02", "ANALYSE FONCTIONNELLE — Acteurs et responsabilités", "Six espaces privés associés à des responsabilités métier.", title_size=23)
    add_circle_label(slide, 5.45, 2.55, 2.45, "DONNÉES ESG\nVALIDÉES", fill=NAVY, size=16)

    actors = [
        (0.85, 1.95, "AD", "Administrateur", "organise", PURPLE, PURPLE_LIGHT),
        (0.85, 4.55, "EN", "Company", "déclare", GREEN, MINT),
        (4.05, 5.3, "AU", "Auditeur", "vérifie", TEAL, TEAL_LIGHT),
        (8.72, 5.3, "IN", "Investisseur", "décide", AMBER, AMBER_LIGHT),
        (9.58, 1.95, "CH", "Chercheur", "analyse", EMERALD, MINT),
        (9.58, 4.05, "IT", "Institution", "collabore", BLUE, "#EAF0F5"),
    ]
    for x, y, initials, role, verb, accent, fill in actors:
        add_box(slide, x, y, 2.85, 1.02, fill=WHITE, line=LINE, radius=True)
        add_circle_label(slide, x + 0.18, y + 0.2, 0.62, initials, fill=accent, size=9)
        add_text(slide, x + 0.98, y + 0.19, 1.55, 0.28, role, size=11.2, color=NAVY, bold=True)
        add_text(slide, x + 0.98, y + 0.53, 1.55, 0.25, verb, size=10.2, color=accent, bold=True)

    # Simple connectors around the centre.
    for x, y, w in [(3.75, 2.74, 1.48), (3.75, 4.82, 1.32), (7.98, 2.74, 1.4), (7.95, 4.64, 1.3)]:
        add_arrow(slide, x, y, w, 0.17, color="#B8CEC5")
    add_box(slide, 3.08, 6.55, 7.2, 0.42, fill=MINT, line=None, radius=True)
    add_text(slide, 3.3, 6.62, 6.75, 0.25, "Comptes administrés · accès privé par rôle · actions synchronisées", size=10.5, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    add_footer(slide, 6)
    add_note(
        slide,
        """
        Durée cible : 1 minute 30.

        Six rôles sont prévus. L’administrateur crée et gère les comptes. L’entreprise dépose son rapport. L’auditeur vérifie les indicateurs et les preuves. L’investisseur compare et décide. Le chercheur analyse les données autorisées, tandis que l’institution organise la collaboration scientifique. Chaque rôle possède un espace privé, mais tous partagent la même donnée validée.

        Transition : Le workflow principal relie l’entreprise, le système, l’administrateur et l’auditeur.
        """,
    )
    return "06", "Acteurs et responsabilités", "1:30"


def slide_07(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, WHITE)
    add_header(slide, "PARTIE 02", "ANALYSE FONCTIONNELLE — Workflow principal", "Traitement, audit, correction, validation et publication.", title_size=23)
    steps = [
        ("Company", "1", "Déposer", "PDF + métadonnées", GREEN, MINT),
        ("Système", "2", "Analyser", "OCR + extraction", TEAL, TEAL_LIGHT),
        ("Admin", "3", "Affecter", "Choisir un auditeur", PURPLE, PURPLE_LIGHT),
        ("Auditeur", "4", "Vérifier", "Valeurs + preuves", BLUE, "#EAF0F5"),
        ("Company", "5", "Corriger", "Nouvelle version", GREEN, MINT),
        ("Admin", "6", "Publier", "Données validées", AMBER, AMBER_LIGHT),
    ]
    x = 0.65
    for idx, (role, num, title, detail, accent, fill) in enumerate(steps):
        add_badge(slide, x + 0.12, 2.02, role, fill=fill, color=accent, width=1.35)
        add_box(slide, x, 2.55, 1.85, 2.0, fill=WHITE, line=LINE, radius=True)
        add_circle_label(slide, x + 0.62, 2.82, 0.62, num, fill=accent, size=11)
        add_text(slide, x + 0.16, 3.58, 1.53, 0.31, title, size=14, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, x + 0.16, 4.0, 1.53, 0.36, detail, size=9.7, color=SLATE, align=PP_ALIGN.CENTER)
        if idx < len(steps) - 1:
            add_arrow(slide, x + 1.9, 3.35, 0.28, 0.22, color="#AFC5BC")
        x += 2.1
    # Correction loop.
    add_box(slide, 7.32, 5.05, 3.95, 0.62, fill=AMBER_LIGHT, line=None, radius=True)
    add_text(slide, 7.6, 5.16, 3.4, 0.34, "Boucle de correction si une preuve manque", size=10.5, color="#A55C00", bold=True, align=PP_ALIGN.CENTER)
    arrow = slide.shapes.add_shape(MSO_SHAPE.LEFT_ARROW, Inches(5.78), Inches(5.18), Inches(1.38), Inches(0.28))
    _set_fill(arrow, AMBER)
    _set_line(arrow, None)
    add_box(slide, 0.87, 6.1, 11.55, 0.62, fill=NAVY, line=None, radius=True)
    add_text(slide, 1.15, 6.22, 11.0, 0.32, "Synchronisation des statuts, actions et notifications entre les espaces utilisateurs.", size=12, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_footer(slide, 7)
    add_note(
        slide,
        """
        Durée cible : 1 minute 50.

        Le workflow commence par le dépôt du rapport. Le système lance l’analyse documentaire. L’administrateur affecte ensuite un auditeur, qui vérifie les indicateurs, l’unité, la période et la preuve. Si une information manque, une correction est demandée à l’entreprise. La nouvelle version revient dans le circuit avant validation et publication. Les changements de statut et les notifications sont synchronisés entre les espaces concernés.

        Transition : Une fois validées, ces données alimentent plusieurs usages sans créer de copies contradictoires.
        """,
    )
    return "07", "Workflow principal", "1:50"


def slide_08(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs)
    add_header(slide, "PARTIE 02", "ANALYSE FONCTIONNELLE — Fonctionnalités principales", "Principaux usages des données ESG validées.", title_size=23)
    cards = [
        ("company-results.png", "Company", "Résultats, Scope 1–3 et preuves", GREEN),
        ("investor-compare.png", "Investisseur", "Comparer et préparer une décision", AMBER),
        ("researcher-analyses.png", "Recherche & Institution", "Analyser, rattacher et exporter", TEAL),
    ]
    x = 0.7
    for file_name, role, caption, accent in cards:
        add_picture_card(slide, ASSET_DIR / file_name, x, 1.95, 3.75, 2.11)
        add_box(slide, x - 0.06, 4.28, 3.87, 1.55, fill=WHITE, line=LINE, radius=True)
        add_badge(slide, x + 0.18, 4.51, role, fill=MINT if accent == GREEN else (AMBER_LIGHT if accent == AMBER else TEAL_LIGHT), color=accent, width=1.55 if role != "Recherche & Institution" else 2.05)
        add_text(slide, x + 0.18, 5.04, 3.38, 0.47, caption, size=12, color=NAVY, bold=True)
        x += 4.17
    add_box(slide, 1.42, 6.25, 10.45, 0.52, fill=NAVY, line=None, radius=True)
    add_text(slide, 1.7, 6.35, 9.9, 0.3, "Fonctions communes : consulter la source · comparer · analyser · exporter", size=11.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_footer(slide, 8)
    add_note(
        slide,
        """
        Durée cible : 1 minute 30.

        La plateforme propose six espaces. Cette diapositive illustre trois usages majeurs : l’entreprise consulte ses résultats et les preuves, l’investisseur compare les entreprises et analyse son portefeuille, tandis que le chercheur et l’institution construisent, partagent et exportent leurs analyses.

        Transition : La valeur de ces interfaces dépend entièrement de la fiabilité du pipeline documentaire.
        """,
    )
    return "08", "Fonctionnalités principales", "1:30"


def slide_09(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, WHITE)
    add_header(slide, "PARTIE 03", "CONCEPTION TECHNIQUE — Pipeline documentaire", "Étapes d’analyse, d’extraction et de contrôle.", title_size=24)
    stages = [
        ("PDF", "Original conservé", "INGESTION", GREEN),
        ("OCR", "Docling + OCR", "STRUCTURATION", GREEN),
        ("JSON", "Nettoyage + tables", "NORMALISATION", GREEN),
        ("BGE", "bge-m3 + FAISS", "RECHERCHE", TEAL),
        ("LLM", "Extraction structurée", "EXTRACTION", AMBER),
        ("QC", "Précision + validation", "CONTRÔLE", PURPLE),
    ]
    x = 0.55
    for idx, (short, title, status, accent) in enumerate(stages):
        add_box(slide, x, 1.96, 1.72, 1.72, fill=OFF_WHITE, line=LINE, radius=True)
        add_circle_label(slide, x + 0.52, 2.18, 0.68, short, fill=accent, size=9)
        add_text(slide, x + 0.15, 3.0, 1.42, 0.35, title, size=10, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
        add_badge(slide, x + 0.2, 3.42, status, fill=MINT if accent == GREEN else (TEAL_LIGHT if accent == TEAL else (AMBER_LIGHT if accent == AMBER else PURPLE_LIGHT)), color=accent, width=1.32)
        if idx < len(stages) - 1:
            add_arrow(slide, x + 1.77, 2.66, 0.33, 0.2, color="#AFC5BC")
        x += 2.1

    safeguards = [
        ("01", "Aucune valeur sans page", "La citation doit appartenir au contexte transmis."),
        ("02", "Unité + période obligatoires", "Éviter les confusions d’année, d’intensité et de périmètre."),
        ("03", "L’incertitude déclenche une revue", "Absent ou contradictoire = non publié automatiquement."),
    ]
    x = 0.78
    for num, title, body in safeguards:
        add_box(slide, x, 4.38, 3.9, 1.62, fill=WHITE, line=LINE, radius=True)
        add_circle_label(slide, x + 0.23, 4.65, 0.5, num, fill=NAVY, size=9)
        add_text(slide, x + 0.9, 4.56, 2.72, 0.33, title, size=11.5, color=NAVY, bold=True)
        add_text(slide, x + 0.9, 4.98, 2.7, 0.6, body, size=9.7, color=SLATE)
        x += 4.16
    add_box(slide, 2.0, 6.28, 9.35, 0.5, fill=MINT, line=None, radius=True)
    add_text(slide, 2.25, 6.38, 8.85, 0.28, "Contrôles : page source · unité · période · cohérence · revue humaine", size=11.5, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    add_footer(slide, 9)
    add_note(
        slide,
        """
        Durée cible : 2 minutes 15.

        Le PDF original est conservé. Docling et l’OCR structurent les pages et les tableaux. Le contenu est normalisé, puis indexé par bge-m3 et FAISS afin de retrouver les passages candidats. L’extraction produit un JSON contraint. Des contrôles vérifient ensuite la page source, l’unité, la période et la cohérence avant validation. Une valeur incertaine est dirigée vers une revue humaine.

        Transition : Ce pipeline s’intègre dans une architecture qui sépare clairement les responsabilités.
        """,
    )
    return "09", "Pipeline documentaire", "2:15"


def slide_10(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs)
    add_header(slide, "PARTIE 03", "CONCEPTION TECHNIQUE — Architecture générale", "Organisation du frontend, des services métier, des données et de l’IA.", title_size=23)

    # UI layer.
    add_box(slide, 0.85, 1.9, 11.65, 0.72, fill=NAVY, line=None, radius=True)
    add_text(slide, 1.15, 2.04, 2.25, 0.3, "FRONTEND", size=10, color="#BFEEDC", bold=True)
    add_text(slide, 3.15, 2.02, 8.8, 0.34, "React + TypeScript · six espaces utilisateurs", size=13, color=WHITE, bold=True)

    add_arrow(slide, 6.43, 2.68, 0.48, 0.25, color="#9FCAB9")
    add_box(slide, 0.85, 3.03, 11.65, 0.72, fill=GREEN, line=None, radius=True)
    add_text(slide, 1.15, 3.17, 2.25, 0.3, "API", size=10, color="#D7F4E8", bold=True)
    add_text(slide, 3.15, 3.14, 8.8, 0.34, "FastAPI /api/v1 · Pydantic · authentification et permissions", size=13, color=WHITE, bold=True)

    add_arrow(slide, 6.43, 3.8, 0.48, 0.25, color="#9FCAB9")
    domains = ["Auth", "Ingestion", "Audit", "Scoring", "Carbone", "Portefeuille"]
    x = 0.85
    for idx, domain in enumerate(domains):
        accent = GREEN if idx < 4 else AMBER
        fill = MINT if idx < 4 else AMBER_LIGHT
        add_box(slide, x, 4.15, 1.72, 0.72, fill=fill, line=None, radius=True)
        add_text(slide, x + 0.1, 4.32, 1.52, 0.3, domain, size=10.5, color=accent, bold=True, align=PP_ALIGN.CENTER)
        x += 1.96

    # Data and AI layer.
    add_box(slide, 0.85, 5.28, 7.4, 1.0, fill=WHITE, line=LINE, radius=True)
    add_text(slide, 1.15, 5.52, 1.35, 0.25, "DONNÉES", size=9.5, color=SLATE, bold=True)
    add_text(slide, 2.45, 5.45, 5.45, 0.42, "PostgreSQL + pgvector · Redis · stockage PDF", size=12.2, color=NAVY, bold=True)
    add_box(slide, 8.52, 5.28, 3.98, 1.0, fill="#EAF0F5", line=None, radius=True)
    add_text(slide, 8.8, 5.48, 1.1, 0.25, "PIPELINE IA", size=9.5, color=BLUE, bold=True)
    add_text(slide, 9.92, 5.42, 2.3, 0.5, "Docling · bge-m3\nClaude / Gemini / local", size=10.7, color=NAVY, bold=True)

    add_badge(slide, 1.0, 6.57, "Modulaire", fill=MINT, color=GREEN, width=1.15)
    add_badge(slide, 2.35, 6.57, "Sécurisée", fill=TEAL_LIGHT, color=TEAL, width=1.15)
    add_badge(slide, 3.7, 6.57, "Extensible", fill=PURPLE_LIGHT, color=PURPLE, width=1.15)
    add_text(slide, 5.15, 6.59, 6.85, 0.25, "Fournisseur IA interchangeable derrière un contrat d’extraction commun.", size=9.5, color=SLATE, align=PP_ALIGN.RIGHT)
    add_footer(slide, 10)
    add_note(
        slide,
        """
        Durée cible : 1 minute 45.

        L’architecture sépare quatre niveaux. Le frontend React fournit les espaces par rôle. L’API FastAPI expose les fonctions versionnées et applique validation et permissions. Les modules métier isolent les responsabilités. PostgreSQL conserve les données structurées, Redis prépare les traitements asynchrones et le stockage conserve les documents. Le pipeline IA reste un composant remplaçable : Claude, Gemini ou un modèle local peuvent respecter le même schéma de sortie.

        Transition : Chaque technologie a donc été choisie pour une propriété précise du système.
        """,
    )
    return "10", "Architecture générale", "1:45"


def slide_11(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, WHITE)
    add_header(slide, "PARTIE 03", "CONCEPTION TECHNIQUE — Technologies utilisées", "Technologies principales et justification des choix.", title_size=23)
    technologies = [
        ("TS", "React + TypeScript", "Interfaces multi-rôles typées", GREEN, MINT),
        ("API", "FastAPI + Pydantic", "Contrats et validation explicites", PURPLE, PURPLE_LIGHT),
        ("DB", "PostgreSQL + SQLModel", "Intégrité, versions et traçabilité", BLUE, "#EAF0F5"),
        ("PDF", "Docling + PaddleOCR", "Textes, tableaux et pages scannées", TEAL, TEAL_LIGHT),
        ("AI", "bge-m3 + FAISS", "Recherche sémantique mesurable", AMBER, AMBER_LIGHT),
        ("CI", "Docker + GitHub Actions", "Reproductibilité et contrôle qualité", EMERALD, MINT),
    ]
    for idx, (icon, title, body, accent, fill) in enumerate(technologies):
        row, col = divmod(idx, 3)
        x = 0.72 + col * 4.2
        y = 1.95 + row * 2.15
        add_box(slide, x, y, 3.85, 1.72, fill=OFF_WHITE, line=LINE, radius=True)
        add_circle_label(slide, x + 0.25, y + 0.28, 0.64, icon, fill=accent, size=9.5)
        add_text(slide, x + 1.12, y + 0.27, 2.4, 0.32, title, size=12.2, color=NAVY, bold=True)
        add_text(slide, x + 1.12, y + 0.75, 2.35, 0.58, body, size=10.2, color=SLATE)
        add_badge(slide, x + 0.25, y + 1.22, "Pourquoi", fill=fill, color=accent, width=0.78)
    add_box(slide, 2.25, 6.34, 8.8, 0.48, fill=NAVY, line=None, radius=True)
    add_text(slide, 2.48, 6.43, 8.35, 0.28, "Critères de choix : typage · modularité · reproductibilité · ouverture", size=11, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_footer(slide, 11)
    add_note(
        slide,
        """
        Durée cible : 1 minute 30.

        React et TypeScript structurent les interfaces multi-rôles. FastAPI et Pydantic rendent les contrats d’API explicites. PostgreSQL et SQLModel garantissent l’intégrité et le versionnement. Docling et PaddleOCR comprennent les PDF et les tableaux. bge-m3 et FAISS permettent de mesurer la recherche sémantique indépendamment du modèle génératif. Docker et la CI rendent l’environnement reproductible. Le choix technologique répond donc directement à un besoin de confiance.

        Transition : Ces briques deviennent concrètes dans le parcours de démonstration.
        """,
    )
    return "11", "Technologies", "1:30"


def slide_12(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, NAVY)
    add_header(slide, "PARTIE 04", "DÉMONSTRATION — Parcours principal", "Vidéo du workflow complet de la plateforme.", dark=True, title_size=24)
    add_badge(slide, 10.35, 0.46, "Démonstration fonctionnelle", fill="#173A56", color="#BFEEDC", width=2.05)
    add_picture_card(slide, ASSET_DIR / "admin-dashboard.png", 0.82, 1.85, 8.35, 4.7, border="#29475F")
    # Play overlay.
    play = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(4.33), Inches(3.55), Inches(1.3), Inches(1.3))
    _set_fill(play, EMERALD)
    _set_line(play, WHITE, 1.5)
    triangle = slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(4.82), Inches(3.91), Inches(0.42), Inches(0.5))
    triangle.rotation = 90
    _set_fill(triangle, WHITE)
    _set_line(triangle, None)

    add_box(slide, 9.55, 1.85, 2.77, 4.7, fill="#132C43", line="#29475F", radius=True)
    add_text(slide, 9.87, 2.12, 2.1, 0.35, "PARCOURS VIDÉO", size=10.5, color="#BFEEDC", bold=True)
    demo_steps = [
        ("00:00", "Créer une entreprise"),
        ("00:35", "Déposer un rapport"),
        ("01:05", "Contrôler les preuves"),
        ("02:05", "Valider et publier"),
        ("02:40", "Comparer et analyser"),
    ]
    y = 2.7
    for timecode, label in demo_steps:
        add_circle_label(slide, 9.9, y, 0.42, "✓", fill=GREEN, size=8)
        add_text(slide, 10.45, y - 0.02, 0.55, 0.24, timecode, size=8.5, color="#91A4B5", bold=True)
        add_text(slide, 11.05, y - 0.03, 0.98, 0.46, label, size=9.8, color=WHITE, bold=True)
        y += 0.68
    add_text(slide, 9.88, 6.03, 2.05, 0.25, "Insérer : demo_greenfinance.mp4", size=8.5, color="#91A4B5", italic=True)
    add_footer(slide, 12, dark=True)
    add_note(
        slide,
        """
        Durée cible : 3 minutes 30.

        La vidéo suit un seul fil narratif : l’administrateur crée une entreprise, le rapport est déposé et analysé, l’auditeur contrôle les preuves, l’administrateur valide et publie, puis l’investisseur compare les résultats. La démonstration se termine par un aperçu des espaces Chercheur et Institution. Les captures d’écran servent de solution de secours si la vidéo ne démarre pas.

        Transition : Après le parcours fonctionnel, voici les résultats de l’évaluation.
        """,
    )
    return "12", "Démonstration", "3:30"


def slide_13(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs)
    add_header(slide, "PARTIE 05", "ÉVALUATION — Résultats obtenus", "Couverture fonctionnelle et résultats du corpus pilote.", title_size=24)
    kpis = [
        ("3", "rapports structurés", GREEN, MINT),
        ("343", "pages traitées", BLUE, "#EAF0F5"),
        ("267", "tableaux détectés", TEAL, TEAL_LIGHT),
        ("11/15", "recall@8 · 73,3 %", AMBER, AMBER_LIGHT),
    ]
    x = 0.72
    for value, label, accent, fill in kpis:
        add_box(slide, x, 1.82, 2.88, 1.28, fill=WHITE, line=LINE, radius=True)
        add_text(slide, x + 0.24, 2.04, 1.3, 0.46, value, size=25, color=accent, bold=True, font=FONT_HEAD)
        add_text(slide, x + 0.24, 2.58, 2.36, 0.28, label, size=10, color=SLATE, bold=True)
        x += 3.07

    # Retrieval bars.
    add_box(slide, 0.72, 3.48, 7.65, 2.65, fill=WHITE, line=LINE, radius=True)
    add_text(slide, 1.0, 3.76, 3.4, 0.3, "RECHERCHE SÉMANTIQUE · TOP 8", size=10, color=NAVY, bold=True)
    companies = [
        ("Microsoft", 0.0, "0/4 · page attendue au rang 10", AMBER),
        ("Ørsted", 1.0, "7/7", GREEN),
        ("Ingka Group", 1.0, "4/4", GREEN),
    ]
    y = 4.32
    for name, ratio, detail, accent in companies:
        add_text(slide, 1.0, y, 1.45, 0.25, name, size=10.5, color=NAVY, bold=True)
        add_box(slide, 2.55, y + 0.02, 3.55, 0.18, fill="#E9EFEC", line=None, radius=True)
        if ratio > 0:
            add_box(slide, 2.55, y + 0.02, 3.55 * ratio, 0.18, fill=accent, line=None, radius=True)
        else:
            add_box(slide, 2.55, y + 0.02, 0.16, 0.18, fill=accent, line=None, radius=True)
        add_text(slide, 6.27, y - 0.02, 1.65, 0.3, detail, size=9.5, color=accent, bold=True, align=PP_ALIGN.RIGHT)
        y += 0.55

    add_box(slide, 8.72, 3.48, 3.9, 2.65, fill=NAVY, line=None, radius=True)
    add_text(slide, 9.02, 3.78, 2.7, 0.3, "COUVERTURE DU PIPELINE", size=10, color="#BFEEDC", bold=True)
    statuses = [
        ("4.2", "Structuration", "OPÉRATIONNEL", GREEN),
        ("4.3", "Recherche", "OPÉRATIONNEL", TEAL),
        ("4.4–4.6", "Extraction + contrôle", "OPÉRATIONNEL", AMBER),
    ]
    y = 4.28
    for step, label, status, accent in statuses:
        add_text(slide, 9.02, y, 0.62, 0.28, step, size=10, color="#91A4B5", bold=True)
        add_text(slide, 9.7, y, 1.35, 0.28, label, size=10, color=WHITE, bold=True)
        add_badge(slide, 10.95, y - 0.02, status, fill="#173A56", color=accent, width=1.35)
        y += 0.56
    add_text(slide, 8.98, 5.89, 3.05, 0.22, "73,3 % mesure le retrieval, pas la précision d’extraction.", size=7.8, color="#C7D4DF", italic=True)
    add_footer(
        slide,
        13,
        source="Sources internes : prompt_4_2_structuration.json · prompt_4_3_indexation.json",
    )
    add_note(
        slide,
        """
        Durée cible : 2 minutes.

        Le corpus pilote contient Microsoft, Ørsted et Ingka Group : 343 pages et 267 tableaux ont été structurés. Le benchmark de recherche retrouve 11 indicateurs sur 15 dans les huit meilleures pages. Ørsted et Ingka atteignent 100 % sur ce test ; pour Microsoft, la page attendue arrive au rang 10. Ce résultat mesure la récupération documentaire et sert à orienter l’amélioration continue du classement sémantique. L’ensemble du pipeline est intégré au workflow de la plateforme.

        Transition : Ces résultats conduisent aux recommandations et aux perspectives d’évolution.
        """,
    )
    return "13", "Résultats obtenus", "2:00"


def slide_14(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, WHITE)
    add_header(slide, "PARTIE 05", "ÉVALUATION — Limites, recommandations et perspectives", "Axes d’amélioration d’une plateforme déjà opérationnelle.", title_size=22)
    columns = [
        (
            0.72,
            "LIMITES STRUCTURELLES",
            AMBER,
            AMBER_LIGHT,
            [
                ("Sources hétérogènes", "Formats, langues et périmètres variables"),
                ("Qualité documentaire", "Précision dépendante des rapports publiés"),
                ("Référentiels évolutifs", "Normes ESG et climat en transformation"),
            ],
        ),
        (
            4.77,
            "RECOMMANDATIONS",
            GREEN,
            MINT,
            [
                ("Benchmark continu", "Tester régulièrement secteurs et formats"),
                ("Contrôle ciblé", "Maintenir une validation humaine des cas critiques"),
                ("Gouvernance des modèles", "Versionner règles, modèles et résultats"),
            ],
        ),
        (
            8.82,
            "PERSPECTIVES",
            PURPLE,
            PURPLE_LIGHT,
            [
                ("Nouvelles sources", "Données réglementaires et financières externes"),
                ("IA avancée", "Analyse multilingue, contextuelle et multimodale"),
                ("Industrialisation", "Scalabilité et interopérabilité financière"),
            ],
        ),
    ]
    for x, heading, accent, fill, items in columns:
        add_box(slide, x, 1.9, 3.8, 0.48, fill=accent, line=None, radius=True)
        add_text(slide, x + 0.16, 2.01, 3.48, 0.24, heading, size=9.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        y = 2.62
        for idx, (title, body) in enumerate(items):
            add_box(slide, x, y, 3.8, 0.92, fill=WHITE, line=LINE, radius=True)
            add_circle_label(slide, x + 0.18, y + 0.2, 0.5, str(idx + 1), fill=accent, size=8.5)
            add_text(slide, x + 0.86, y + 0.14, 2.65, 0.26, title, size=10.5, color=NAVY, bold=True)
            add_text(slide, x + 0.86, y + 0.48, 2.64, 0.28, body, size=8.9, color=SLATE)
            y += 1.08

    add_box(slide, 0.72, 6.1, 11.9, 0.68, fill=NAVY, line=None, radius=True)
    add_text(slide, 0.98, 6.2, 11.38, 0.42, "Axes futurs : extension ESG · automatisation avancée · précision · auditabilité · intégration financière", size=10.8, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_footer(slide, 14)
    add_note(
        slide,
        """
        Durée cible : 1 minute 45.

        Les limites concernent désormais l’environnement d’exploitation : l’hétérogénéité permanente des rapports, la qualité variable des sources et l’évolution des référentiels. Les recommandations sont de maintenir un benchmark continu, une validation humaine ciblée et un versionnement strict des modèles et des règles. Les perspectives portent sur de nouvelles sources ESG et financières, une intelligence multilingue et multimodale, l’automatisation avancée, le traitement distribué et l’interopérabilité avec d’autres systèmes financiers.

        Transition : Ces évolutions prolongent les contributions déjà apportées par le projet.
        """,
    )
    return "14", "Limites, recommandations et perspectives", "1:45"


def slide_15(prs: Presentation) -> tuple[str, str, str]:
    slide = new_slide(prs, NAVY)
    add_header(slide, "PARTIE 06", "CONCLUSION — Synthèse du projet", "Problématique traitée, solution développée et contribution.", dark=True, title_size=25)
    pillars = [
        ("01", "Problématique", "Données dispersées et scores difficiles à auditer", GREEN),
        ("02", "Solution", "Plateforme ESG, carbone et portefeuille multi-acteurs", TEAL),
        ("03", "Contribution", "Résultats sourcés, configurables et explicables", AMBER),
    ]
    x = 0.82
    for num, title, body, accent in pillars:
        add_box(slide, x, 2.45, 3.72, 1.72, fill="#132C43", line="#29475F", radius=True)
        add_circle_label(slide, x + 0.25, 2.77, 0.58, num, fill=accent, size=9)
        add_text(slide, x + 1.08, 2.7, 2.2, 0.35, title, size=16, color=WHITE, bold=True, font=FONT_HEAD)
        add_text(slide, x + 1.08, 3.18, 2.28, 0.62, body, size=10.4, color="#C7D4DF")
        x += 4.05

    add_box(slide, 0.82, 4.82, 11.55, 0.92, fill=GREEN, line=None, radius=True)
    add_text(slide, 1.12, 4.98, 10.95, 0.54, "Résultat : une plateforme intégrée pour analyser, vérifier, calculer et exploiter les données ESG et climat.", size=13.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_text(slide, 0.82, 6.45, 6.0, 0.38, "Merci", size=22, color=WHITE, bold=True, font=FONT_HEAD)
    add_text(slide, 7.7, 6.45, 4.65, 0.38, "Questions ?", size=22, color="#BFEEDC", bold=True, font=FONT_HEAD, align=PP_ALIGN.RIGHT)
    add_note(
        slide,
        """
        Durée cible : 45 secondes.

        GreenFinance Scorer répond à un problème concret : des données ESG dispersées et des scores difficiles à auditer. La plateforme relie chaque résultat à sa source, rend les pondérations configurables, calcule les émissions et l’empreinte financée, puis fournit des analyses adaptées aux différents acteurs. La contribution principale est l’intégration de ces fonctions dans un système ouvert, traçable et explicable.

        Merci. Je suis prêt à répondre à vos questions.
        """,
    )
    return "15", "Conclusion", "0:45"


def write_script(slide_index: list[tuple[str, str, str]], prs: Presentation) -> None:
    lines = [
        "# GreenFinance Scorer — script oral de soutenance",
        "",
        "Durée cible : **environ 23 min 40**, démonstration comprise.",
        "",
        "> Remplacer les champs personnels de la couverture et insérer `demo_greenfinance.mp4` sur la slide 12.",
        "",
    ]
    for (number, title, timing), slide in zip(slide_index, prs.slides, strict=True):
        notes = slide.notes_slide.notes_text_frame.text.strip()
        lines.extend([f"## {number} — {title} ({timing})", "", notes, ""])
    SCRIPT_PATH.write_text("\n".join(lines), encoding="utf-8")


def build() -> None:
    missing = [
        name
        for name in [
            "admin-dashboard.png",
            "company-results.png",
            "investor-compare.png",
            "researcher-analyses.png",
        ]
        if not (ASSET_DIR / name).exists()
    ]
    if missing:
        raise FileNotFoundError(f"Captures manquantes dans {ASSET_DIR}: {missing}")

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    prs.core_properties.title = "GreenFinance Scorer — Soutenance finale"
    prs.core_properties.subject = "Plateforme ESG et climat traçable"
    prs.core_properties.author = "GreenFinance Scorer"
    prs.core_properties.keywords = "ESG, climat, scoring, traçabilité, FastAPI, React, Docling"

    index = [
        slide_01(prs),
        slide_02(prs),
        slide_03(prs),
        slide_04(prs),
        slide_05(prs),
        slide_06(prs),
        slide_07(prs),
        slide_08(prs),
        slide_09(prs),
        slide_10(prs),
        slide_11(prs),
        slide_12(prs),
        slide_13(prs),
        slide_14(prs),
        slide_15(prs),
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prs.save(PPTX_PATH)
    write_script(index, prs)
    print(f"PowerPoint : {PPTX_PATH}")
    print(f"Script oral : {SCRIPT_PATH}")
    print(f"Slides : {len(prs.slides)}")


if __name__ == "__main__":
    build()
