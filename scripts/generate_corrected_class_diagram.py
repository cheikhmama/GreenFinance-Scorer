"""Corrected, French UML document. Reads models through AST; never changes the app.

Run: .venv/Scripts/python.exe scripts/generate_corrected_class_diagram.py
Reuses the existing repository's vector renderer, with a separate output directory.
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET

import pymupdf

import generate_class_diagram as base

OUT = base.ROOT / "docs" / "diagrammes" / "corrige"
OUT.mkdir(parents=True, exist_ok=True)
base.OUT = OUT
STEM = "Diagramme_classes_corrige"

NAMES = {
    "User": "Utilisateur", "Company": "Entreprise", "ESGReport": "RapportESG",
    "Score": "ScoreESG", "ScoringConfig": "ConfigurationScore",
    "ExtractionRun": "ExecutionExtraction", "MetricCoverage": "CouvertureIndicateur",
    "ESGMetric": "MesureESG", "CarbonEmission": "EmissionCarbone", "Evidence": "Preuve",
    "AuditOpinion": "AvisAudit", "MetricReview": "RevueValeur", "Portfolio": "Portefeuille",
    "PortfolioPosition": "PositionPortefeuille", "Project": "Projet",
    "ProjectAssignment": "AffectationChercheur", "ProjectCompany": "EntrepriseProjet",
    "ProjectDocument": "DocumentProjet", "Analysis": "Analyse",
    "AnalysisCompany": "EntrepriseAnalyse", "ResearcherAffiliation": "RattachementChercheur",
    "InstitutionProfile": "ProfilInstitution",
}

# This view deliberately omits the external-reference subsystem, as requested.
base.FIELDS = {k: v for k, v in base.FIELDS.items() if k in NAMES}
base.FIELDS.update({
    "User": "email name password_hash role active created_at",
    "Company": "name sector country status tax_id isin lei published_at",
    "ESGReport": "type fiscal_year status version source_file submitted_at assigned_at revenue revenue_currency enterprise_value enterprise_value_currency",
    "InstitutionProfile": "export_quota",
})
base.NOTES = {k: v for k, v in base.NOTES.items() if k in NAMES}
base.NOTES.update({
    "User": "Un seul rôle par compte ; pas de sous-classes métier",
    "Company": "Propriétaire facultatif ; publication distincte du statut",
    "ESGReport": "Brouillon possible ; correction = nouvelle version",
    "Evidence": "Preuve réutilisable ; pas de lien direct au rapport",
    "AuditOpinion": "Schéma : 0..* avis ; parcours courant : au plus 1 par version",
    "MetricReview": "{cible ESG XOR cible carbone} ; historique immuable",
    "InstitutionProfile": "{user_id unique} ; compte de rôle INSTITUTION",
})
base.NODES = {k: n for k, n in base.NODES.items() if n["cls"] in NAMES}
base.EDGES = [e for e in base.EDGES if e["child"] in base.NODES and e["parent"] in base.NODES]
for n in base.NODES.values():
    if not n["ref"]:
        n["h"] = base.height(n["cls"])
base.NODES["opinion"]["y"] = 440
base.NODES["company"]["w"] = 465
base.node("institution_profile", "InstitutionProfile", "f", 3110, 2110, 510)
base.edge("institution_profile", "f_institution", "user_id", "profil institutionnel")
# Reserve enough space for a multiplicity even when routing chooses a panel-facing side.
for n in base.NODES.values():
    p = next(p for p in base.PANELS if p["key"] == n["domain"])
    if n["x"] - p["x"] < 65:
        n["x"] += 25
        n["w"] -= 25
    if p["x"]+p["w"] - (n["x"]+n["w"]) < 65:
        n["w"] -= 25
for p in base.PANELS:
    if p["key"] == "f":
        p["title"] = "06  Rattachements et profil institutionnel"
        p["desc"] = "Une invitation acceptée précède l’affectation à un projet."
for e in base.EDGES:
    if e["fk"] == "owner_user_id" and base.NODES[e["child"]]["cls"] == "Company":
        e["label"] = "propriétaire"
        assert (e["cm"], e["pm"]) == ("0..*", "0..1")


def validate():
    selected = set(base.FIELDS)
    expected = {(name, key) for name in selected for key, f in base.MODELS[name]["fields"].items()
                if f.get("target") in selected}
    actual = {(base.NODES[e["child"]]["cls"], e["fk"]) for e in base.EDGES}
    assert expected == actual, ("Missing or extra associations", expected - actual, actual - expected)
    assert len(selected) == len([n for n in base.NODES.values() if not n["ref"]]) == 22
    for name, fields in base.FIELDS.items():
        assert all(f in base.MODELS[name]["fields"] for f in fields.split())
    for n in base.NODES.values():
        p = next(p for p in base.PANELS if p["key"] == n["domain"])
        assert p["x"] <= n["x"] and p["y"] <= n["y"]
        assert n["x"] + n["w"] <= p["x"] + p["w"]
        assert n["y"] + n["h"] <= p["y"] + p["h"], ("Outside panel", n)
    nodes = list(base.NODES.values())
    for i, a in enumerate(nodes):
        for b in nodes[i+1:]:
            assert not (a["x"] < b["x"]+b["w"] and b["x"] < a["x"]+a["w"] and
                        a["y"] < b["y"]+b["h"] and b["y"] < a["y"]+a["h"]), (a["key"], b["key"])


def draw_node(d, n):
    x, y, w, h = (n[k] for k in ("x", "y", "w", "h"))
    color, name = base.COLORS[n["domain"]], NAMES[n["cls"]]
    if n["ref"]:
        d.rect(x, y, w, h, "#F8FAFB", color, 5, True)
        d.text(x+13, y+22, "« référence »" + (f" · {n['role']}" if n["role"] else ""), 16, base.MUTED, max_width=w-26)
        d.text(x+13, y+48, name, 24, color, "Bold", max_width=w-26)
        return
    d.rect(x, y, w, h, "#FFFFFF", "#CDDADF", 5)
    d.rect(x, y, 5, h, color)
    d.text(x+18, y+25, f"« entité » · {n['cls']}", 16, color, max_width=w-36)
    d.text(x+18, y+57, name, 28, base.INK, "Bold", max_width=w-36)
    d.path([(x+1, y+72), (x+w-1, y+72)], "#CDDADF", 1)
    cls = base.MODELS[n["cls"]]
    for i, key in enumerate(["id"] + base.FIELDS[n["cls"]].split()):
        f = cls["fields"][key]
        suffix = " {PK}" if key == "id" else (" {FK}" if "foreign_key" in f else "")
        d.text(x+18, y+100+i*25, f"{key} : {base.short_type(f['type'])}{suffix}", 20,
               base.INK, "Mono", max_width=w-36)
    if n["cls"] in base.NOTES:
        d.path([(x+1, y+h-38), (x+w-1, y+h-38)], "#E0E9ED", 1)
        d.text(x+18, y+h-14, base.NOTES[n["cls"]], 16, color, max_width=w-36)


def annotations(d, panel, edges):
    """Place multiplicities first, then names, without hiding either under class boxes."""
    obstacles = [(n["x"]-3, n["y"]-3, n["x"]+n["w"]+3, n["y"]+n["h"]+3)
                 for n in base.NODES.values() if n["domain"] == panel["key"]]
    if panel["key"] == "f":
        obstacles.append((2480, 2160, 2990, 2470))
    placed = []
    area = (panel["x"]+5, panel["y"]+87, panel["x"]+panel["w"]-5, panel["y"]+panel["h"]-5)

    def box(cx, baseline, text, size):
        width = base.pdfmetrics.stringWidth(text, "Body", size)+12
        return (cx-width/2, baseline-size, cx+width/2, baseline+8)

    def hits(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    def place(text, candidates, size):
        for cx, baseline in candidates:
            rect = box(cx, baseline, text, size)
            if rect[0] < area[0] or rect[1] < area[1] or rect[2] > area[2] or rect[3] > area[3]:
                continue
            if any(hits(rect, other) for other in obstacles+placed):
                continue
            placed.append(rect)
            d.pill(cx, baseline, text, size, base.COLORS[panel["key"]])
            return
        raise RuntimeError(f"No non-overlapping label placement: {panel['key']} {text}")

    for e in edges:
        for endpoint, key, mult in ((e["path"][0], e["child"], e["cm"]),
                                    (e["path"][-1], e["parent"], e["pm"])):
            n = base.NODES[key]
            x, y = endpoint
            if x == n["x"]:
                nx, ny = -1, 0
            elif x == n["x"]+n["w"]:
                nx, ny = 1, 0
            elif y == n["y"]:
                nx, ny = 0, -1
            else:
                nx, ny = 0, 1
            candidates = [(x+nx*distance-ny*tangent, y+ny*distance+nx*tangent+5)
                          for distance in (29, 40, 52, 65, 80)
                          for tangent in (16, -16, 33, -33, 0, 50, -50)]
            try:
                place(mult, candidates, 17)
            except RuntimeError as exc:
                raise RuntimeError(f"{exc}; endpoint {key}; field {e['fk']}") from exc
    for e in edges:
        segments = sorted(zip(e["path"], e["path"][1:]),
                          key=lambda ab: math.dist(*ab), reverse=True)
        candidates = []
        for a, b in segments:
            if math.dist(a, b) < 40:
                continue
            for fraction in (.5, .35, .65, .2, .8):
                x, y = a[0]+(b[0]-a[0])*fraction, a[1]+(b[1]-a[1])*fraction
                for dx, dy in ((0, -8), (0, 20), (45, -8), (-45, -8), (0, -32), (0, 42),
                               (75, -8), (-75, -8), (105, -8), (-105, -8),
                               (75, 20), (-75, 20), (0, -52), (0, 62)):
                    candidates.append((x+dx, y+dy))
        place(e["label"], candidates, 16)


def sources():
    lines = ["@startuml", "' Vue corrigée : noms français et classes de code entre parenthèses.",
             "hide empty methods", "skinparam classAttributeIconSize 0", "skinparam linetype ortho",
             "skinparam shadowing false", "skinparam defaultFontName Segoe UI",
             "title GreenFinance-Scorer — Diagramme de classes corrigé"]
    for p in base.PANELS:
        lines.append(f'package "{p["title"]}" {{')
        for n in base.NODES.values():
            if n["ref"] or n["domain"] != p["key"]:
                continue
            name = n["cls"]
            lines.append(f'class "{NAMES[name]}\\n({name})" as {name} <<entity>> {{')
            for key in ["id"] + base.FIELDS[name].split():
                lines.append(f'  {key} : {base.short_type(base.MODELS[name]["fields"][key]["type"])}')
            lines.append("}")
            if name in base.NOTES:
                lines.append(f'note bottom of {name} : {base.NOTES[name]}')
        lines.append("}")
    for e in base.EDGES:
        child, parent = base.NODES[e["child"]]["cls"], base.NODES[e["parent"]]["cls"]
        # Multiplicity written beside the class it counts; no inheritance or dependency arrows.
        lines.append(f'{parent} "{e["pm"]}" -- "{e["cm"]}" {child} : {e["label"]} / {e["fk"]}')
    lines += [
        "enum Role {", "  ADMIN", "  ENTERPRISE", "  AUDITOR", "  INVESTOR", "  RESEARCHER", "  INSTITUTION", "}",
        "User ..> Role : type de role",
        "legend bottom", "? = nullable ; attributs essentiels, avec noms et types réels du code.",
        "Traits pleins = associations ; cardinalités du schéma SQL déclaré.",
        "Les opérations métier résident dans les services, pas sur ces entités.",
        "Propriété : Utilisateur 0..1 -- 0..* Entreprise. Le parcours ORM monoentreprise reste à adapter.",
        "Rôles contrôlés par les services : auteur avis/revue = AUDITOR ; titulaire portefeuille = INVESTOR ;",
        "responsable projet = INSTITUTION ; auteur analyse/affectation = RESEARCHER.",
        "endlegend", "@enduml",
    ]
    source = "\n".join(lines) + "\n"
    assert all(word not in source for word in ("JeuDeDonnees", "ReferenceDataset", "AffectationAudit"))
    (OUT / f"{STEM}.puml").write_text(source, encoding="utf-8")
    ledger = ["# Traçabilité du diagramme corrigé", "", "Lecture statique du code du 6 octobre 2026. Aucun accès à une base en exécution.", "",
              "Les types et attributs gardent leur nom dans le code. Les noms français sont des alias UML.", "",
              "## Classes et attributs", "", "| Classe UML | Classe réelle | Source | Attributs affichés |", "|---|---|---|---|"]
    for name, fields in base.FIELDS.items():
        c = base.MODELS[name]
        ledger.append(f'| {NAMES[name]} | `{name}` | [{c["file"]}:{c["line"]}](../../../{c["file"]}#L{c["line"]}) | '+", ".join(f'`{k}`' for k in ["id"]+fields.split())+" |")
    ledger += ["", "## Associations", "", "La cardinalité cible indique combien de cibles une source peut référencer. L'inverse compte les sources pour une cible.", "",
               "| Source | Clé étrangère | Cible | Cible | Inverse | Source code |", "|---|---|---|---|---|---|"]
    for e in base.EDGES:
        child, parent = base.NODES[e["child"]]["cls"], base.NODES[e["parent"]]["cls"]
        ledger.append(f'| {NAMES[child]} | `{e["fk"]}` | {NAMES[parent]} | {e["pm"]} | {e["cm"]} | [{e["file"]}:{e["line"]}](../../../{e["file"]}#L{e["line"]}) |')
    (OUT / "Tracabilite.md").write_text("\n".join(ledger)+"\n", encoding="utf-8")
    (OUT / "Modele_diagramme.json").write_text(json.dumps({
        "date": "2026-10-06", "classes": {name: {**base.MODELS[name], "uml_name": NAMES[name], "displayed_fields": fields.split()} for name, fields in base.FIELDS.items()},
        "associations": [{**e, "source_class": base.NODES[e["child"]]["cls"], "target_class": base.NODES[e["parent"]]["cls"]} for e in base.EDGES],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def draw():
    d = base.Drawing()
    d.svg[2] = '<desc id="desc">22 classes métier et 1 énumération. Propriétaire facultatif, plusieurs entreprises par utilisateur. Associations vérifiées dans les modèles ; références répétées identifiées.</desc>'
    d.rect(0, 0, base.W, base.H, base.BG)
    d.text(45, 65, "GREENFINANCE SCORER", 22, "#137866", "Bold")
    d.text(45, 120, "Diagramme de classes corrigé", 46, base.INK, "Bold")
    d.text(base.W-45, 72, "22 CLASSES MÉTIER  /  6 DOMAINES", 22, base.MUTED, anchor="end")
    d.text(base.W-45, 115, "Modèles et services vérifiés • 6 octobre 2026", 21, base.MUTED, anchor="end")
    for p in base.PANELS:
        d.rect(p["x"], p["y"], p["w"], p["h"], "#FFFFFF", "#D4E0E5", 12)
        d.text(p["x"]+24, p["y"]+37, p["title"], 29, base.COLORS[p["key"]], "Bold", max_width=p["w"]-48)
        d.text(p["x"]+24, p["y"]+67, p["desc"], 19, base.MUTED, max_width=p["w"]-48)
        print("Routage", p["key"], flush=True)
        for e in base.route(p, [e for e in base.EDGES if e["domain"] == p["key"]]):
            d.path(e["path"], base.COLORS[p["key"]], 2)
    for n in base.NODES.values():
        draw_node(d, n)
    for p in base.PANELS:
        annotations(d, p, [e for e in base.EDGES if e["domain"] == p["key"]])
    # A datatype, not six entity subclasses. Kept in the spare space of panel F.
    d.rect(2480, 2160, 510, 310, "#F3F8F7", "#B4CBC5", 5)
    d.text(2500, 2190, "« enumeration » Role", 23, base.INK, "Bold")
    for i, value in enumerate(("ADMIN", "ENTERPRISE", "AUDITOR", "INVESTOR", "RESEARCHER", "INSTITUTION")):
        d.text(2500, 2228+i*30, value, 21, base.INK, "Mono")
    d.text(2500, 2440, "Type de l’attribut Utilisateur.role", 18, base.MUTED)
    d.rect(40, 2545, 3620, 255, "#E6EEF1", radius=10)
    d.text(65, 2585, "CONVENTIONS ET CONTRAINTES", 21, base.INK, "Bold")
    notes = [
        "Association : trait plein. Cardinalités : 1 obligatoire · 0..1 facultatif · 0..* multiple. Cadre pointillé « référence » : même classe répétée, pas une sous-classe.",
        "Attributs essentiels : noms et types du code ; ? = nullable ; {PK} = identifiant. Les clés étrangères restantes sont représentées par les associations.",
        "Propriété demandée : Utilisateur 0..1 — 0..* Entreprise. Le schéma SQL l’autorise ; User.company et les parcours actuels restent monoentreprise (voir Audit_corrections.md).",
        "Opérations métier : fonctions de services séparées ; aucun héritage métier. Rôles : AUDITOR pour les avis/revues, INVESTOR pour les portefeuilles, INSTITUTION pour les projets.",
        "RESEARCHER pour les analyses/affectations. Une analyse requiert ≥ 1 entreprise à sa création ; affectation autorisée après acceptation du rattachement, dans un projet ouvert.",
        "Cardinalités du schéma ; contraintes de parcours précisées dans l’audit. Les scores et les valeurs corrigées restent traçables ; l’avis d’audit ne contient pas le score.",
    ]
    for i, text in enumerate(notes):
        d.text(65, 2625+i*29, text, 20, base.MUTED, max_width=3560)
    d.text(45, 2830, "UML-02 • Vue métier sélectionnée • Code applicatif inchangé", 18, base.MUTED)
    d.text(base.W-45, 2830, "Sources éditables, cardinalités et vérifications : Tracabilite.md", 18, base.MUTED, anchor="end")
    d.save()
    for ext in ("svg", "pdf"):
        (OUT / f"GreenFinance_Diagramme_Classes.{ext}").replace(OUT / f"{STEM}.{ext}")
    svg_path = OUT / f"{STEM}.svg"
    root = ET.parse(svg_path).getroot()
    visible = " ".join(root.itertext())
    assert all(x not in visible for x in ("JeuDeDonnees", "ReferenceDataset", "AffectationAudit"))
    for name in NAMES.values():
        assert name in visible, name
    doc = pymupdf.open(OUT / f"{STEM}.pdf")
    page = doc[0]
    for suffix, width in (("", 5200), ("_apercu", 1850)):
        page.get_pixmap(matrix=pymupdf.Matrix(width/page.rect.width, width/page.rect.width), alpha=False).save(OUT/f"{STEM}{suffix}.png")
    # Six readable domain pages, vector exports cropped from the same authoritative diagram.
    detail = pymupdf.open()
    scale = min(2383.94/base.W, 1683.78/base.H)
    xoff = (2383.94-base.W*scale)/2
    for p in base.PANELS:
        clip = pymupdf.Rect(xoff+p["x"]*scale, p["y"]*scale, xoff+(p["x"]+p["w"])*scale, (p["y"]+p["h"])*scale)
        target = detail.new_page(width=1190.55, height=841.89)
        target.show_pdf_page(pymupdf.Rect(20, 20, 1170.55, 821.89), doc, 0, clip=clip)
    detail.save(OUT / "Diagramme_classes_par_domaine.pdf")
    summary = {"classes": len(base.FIELDS), "enumerations": 1, "associations": len(base.EDGES),
               "attributes_and_fk_verified": True, "ownership": "Utilisateur 0..1 -- 0..* Entreprise",
               "svg_xml_valid": True, "removed_class_absent": True, "no_entity_overlap": True,
               "review_scope": "static source, no runtime DB", "files": [p.name for p in OUT.iterdir() if p.is_file()]}
    (OUT / "Verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    validate()
    sources()
    draw()
    sources()  # Persist the routed association coordinates for reproducible inspection.
