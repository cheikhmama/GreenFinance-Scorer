"""Render the audited UML class view; read source through AST, never connect to the DB.

Run: .venv/Scripts/python.exe scripts/generate_class_diagram.py
The SVG/PDF share the same manually composed layout. Repeated dashed references
are occurrences of the same UML classifier, not additional entities.
"""
from __future__ import annotations

import ast
import hashlib
import heapq
import html
import json
import math
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "diagrammes"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 3700, 2850
INK, MUTED, LINE = "#173347", "#516878", "#617889"
BG = "#F2F6F7"


def inventory():
    result = {}
    for path in sorted((ROOT / "app").glob("*/models.py")):
        source = path.read_text(encoding="utf-8")
        for cls in ast.parse(source).body:
            if not isinstance(cls, ast.ClassDef) or not any(
                k.arg == "table" and ast.literal_eval(k.value) is True for k in cls.keywords
            ):
                continue
            item = {"name": cls.name, "file": path.relative_to(ROOT).as_posix(),
                    "line": cls.lineno, "sha256": hashlib.sha256(source.encode()).hexdigest(),
                    "bases": [ast.unparse(b) for b in cls.bases], "fields": {}, "methods": [],
                    "constraints_source": ""}
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign):
                    names = [ast.unparse(t) for t in stmt.targets]
                    if "__tablename__" in names:
                        item["table"] = ast.literal_eval(stmt.value)
                    if "__table_args__" in names:
                        item["constraints_source"] = ast.get_source_segment(source, stmt)
                if isinstance(stmt, ast.FunctionDef):
                    item["methods"].append({"name": stmt.name, "line": stmt.lineno,
                                            "signature": ast.unparse(stmt).splitlines()[0]})
                if not isinstance(stmt, ast.AnnAssign):
                    continue
                name = ast.unparse(stmt.target)
                value = stmt.value
                is_rel = isinstance(value, ast.Call) and ast.unparse(value.func) == "Relationship"
                f = {"type": ast.unparse(stmt.annotation), "line": stmt.lineno,
                     "relationship": is_rel, "source": ast.get_source_segment(source, stmt)}
                if isinstance(value, ast.Call):
                    for k in value.keywords:
                        if k.arg in {"foreign_key", "ondelete", "unique", "primary_key"}:
                            f[k.arg] = ast.literal_eval(k.value)
                f["nullable"] = "None" in f["type"] or "Optional[" in f["type"]
                item["fields"][name] = f
            result[cls.name] = item
    by_table = {c["table"]: name for name, c in result.items()}
    for cls in result.values():
        for f in cls["fields"].values():
            if "foreign_key" in f:
                f["target"] = by_table[f["foreign_key"].split(".")[0]]
    return result


MODELS = inventory()
FIELDS = {
    "User": "email name role active",
    "Company": "name sector country status isin lei published_at",
    "ESGReport": "type channel fiscal_year status version submitted_at source_file official_score revenue enterprise_value",
    "Score": "global_score environmental_score social_score governance_score coverage_rate computed_at",
    "ScoringConfig": "name version content_yaml content_hash",
    "ExtractionRun": "status started_at finished_at llm_model prompt_version",
    "MetricCoverage": "metric_code status pages_examined",
    "ESGMetric": "pillar metric_code value unit method review_status audited_value",
    "CarbonEmission": "scope tonnes_co2e year method pcaf_data_quality review_status audited_value",
    "Evidence": "document_name year page_start page_end excerpt_pdf_path",
    "AuditOpinion": "decision comment submitted_at",
    "MetricReview": "decision original_value new_value reason created_at",
    "Portfolio": "name reference_currency archived created_at",
    "PortfolioPosition": "outstanding_amount currency converted_amount weight match_status duration_type start_date end_date",
    "Project": "name objective status deadline closed_at",
    "ProjectAssignment": "assigned_at",
    "ProjectCompany": "added_at",
    "ProjectDocument": "added_at",
    "Analysis": "title content status version submitted_at institution_comment",
    "AnalysisCompany": "report_id score_id",
    "ResearcherAffiliation": "status invited_at responded_at collaboration_terms",
    "ReferenceDataset": "name source_url licence scale_min scale_max higher_is_better",
    "ReferenceDatasetRow": "line_number isin lei environmental_score social_score governance_score total_score",
}
NOTES = {
    "User": "role : 6 valeurs, aucune sous-classe métier",
    "Company": "published_at distinct de status",
    "ESGReport": "version précédente : 0..1 ; suivantes : 0..*",
    "Score": "{unique(report_id, config_id)}",
    "ScoringConfig": "owner nul = configuration de référence",
    "ESGMetric": "{unique(report_id, metric_code)}",
    "MetricCoverage": "{unique(report_id, metric_code)}",
    "CarbonEmission": "{scope ∈ 1..3 ; tonnes_co2e ≥ 0}",
    "Evidence": "preuve réutilisable ; aucun report_id",
    "MetricReview": "{metric_id XOR emission_id} ; journal immuable",
    "PortfolioPosition": "{company_id présent ⇔ MATCHED}",
    "ProjectAssignment": "{unique(project_id, researcher_id)}",
    "ProjectCompany": "{unique(project_id, company_id)}",
    "ProjectDocument": "{unique(project_id, report_id)}",
    "Analysis": "version précédente : 0..1 ; suivantes : 0..*",
    "AnalysisCompany": "{unique(analysis_id, company_id)} ; sources figées",
    "ResearcherAffiliation": "{unique(researcher_id, institution_id)}",
    "ReferenceDataset": "{scale_max > scale_min}",
    "ReferenceDatasetRow": "{isin ou lei obligatoire}",
}
COLORS = {"a": "#137866", "b": "#21698B", "c": "#80599B", "d": "#A36C28", "e": "#4B6296", "f": "#427D70"}


def short_type(value):
    return value.replace("uuid.UUID", "UUID").replace(" | None", "?")


def height(cls):
    return 97 + 25 * (len(FIELDS[cls].split()) + 1) + (33 if cls in NOTES else 0)


NODES, PANELS, EDGES = {}, [], []


def panel(key, title, desc, x, y, w, h):
    PANELS.append(dict(key=key, title=title, desc=desc, x=x, y=y, w=w, h=h))


def node(key, cls, domain, x, y, w=440, ref=False, role=""):
    assert cls in MODELS
    NODES[key] = dict(key=key, cls=cls, domain=domain, x=x, y=y, w=w,
                      h=64 if ref else height(cls), ref=ref, role=role)


def edge(child, parent, fk, label=None, composition=False):
    c, p = NODES[child], NODES[parent]
    field = MODELS[c["cls"]]["fields"][fk]
    assert field["target"] == p["cls"], (child, parent, fk)
    assert c["domain"] == p["domain"]
    EDGES.append(dict(child=child, parent=parent, fk=fk, label=label or fk,
                      domain=c["domain"], cm="0..1" if field.get("unique") else "0..*",
                      pm="0..1" if field["nullable"] else "1", composition=composition,
                      file=MODELS[c["cls"]]["file"], line=field["line"]))


# A — principal chain; aliases keep long transverse associations local.
panel("a", "01  Identité, rapports et notation", "Le rapport relie l’entreprise à une notation reproductible.", 40, 165, 1170, 1275)
node("user", "User", "a", 80, 265, 420)
node("company", "Company", "a", 700, 265, 465)
node("report", "ESGReport", "a", 80, 750, 510)
node("config", "ScoringConfig", "a", 700, 690, 465)
node("score", "Score", "a", 700, 1050, 465)
node("assigned", "User", "a", 80, 620, 240, True, "auditeur affecté")
node("declared_proof", "Evidence", "a", 80, 1280, 310, True, "score déclaré")
edge("company", "user", "owner_user_id", "titulaire")
edge("company", "user", "onboarded_by_id", "inscription validée par")
edge("report", "company", "company_id", "entreprise")
edge("report", "assigned", "auditor_id", "affectation")
edge("report", "report", "previous_report_id", "précédent")
edge("report", "declared_proof", "declared_global_score_proof_id", "preuve du score déclaré")
edge("score", "report", "report_id", "rapport noté")
edge("score", "config", "config_id", "méthodologie")
edge("config", "user", "owner_user_id", "propriétaire")

# B — provenance and measured values.
panel("b", "02  Extraction et preuves", "Chaque valeur possède une preuve documentaire obligatoire.", 1240, 165, 1170, 1275)
node("b_report", "ESGReport", "b", 1630, 265, 380, True)
node("run", "ExtractionRun", "b", 1280, 430, 460)
node("coverage", "MetricCoverage", "b", 1900, 430, 465)
node("metric", "ESGMetric", "b", 1280, 745, 460)
node("carbon", "CarbonEmission", "b", 1900, 745, 465)
node("evidence", "Evidence", "b", 1580, 1150, 510)
edge("run", "b_report", "report_id", "tentatives")
edge("coverage", "b_report", "report_id", "complétude")
edge("metric", "b_report", "report_id", "rapport")
edge("carbon", "b_report", "report_id", "rapport")
edge("metric", "run", "extraction_run_id", "exécution")
edge("carbon", "run", "extraction_run_id", "exécution")
edge("metric", "evidence", "proof_id", "preuve")
edge("carbon", "evidence", "proof_id", "preuve")

# C — repeated role references are explicitly occurrences of User.
panel("c", "03  Audit des rapports et des valeurs", "L’avis et la revue des valeurs ont des traces distinctes.", 2440, 165, 1220, 605)
node("c_user", "User", "c", 2480, 270, 230, True, "auditeur")
node("c_report", "ESGReport", "c", 2790, 270, 270, True)
node("c_metric", "ESGMetric", "c", 3130, 270, 220, True)
node("c_carbon", "CarbonEmission", "c", 3400, 270, 220, True)
node("opinion", "AuditOpinion", "c", 2480, 465, 440)
node("review", "MetricReview", "c", 3130, 445, 490)
edge("opinion", "c_user", "auditor_id", "auteur")
edge("opinion", "c_report", "report_id", "rapport")
edge("review", "c_user", "auditor_id", "auteur")
edge("review", "c_report", "report_id", "rapport")
edge("review", "c_metric", "metric_id", "cible ESG")
edge("review", "c_carbon", "emission_id", "cible carbone")

# D — monetary fields are Decimal, no fictitious persisted PCAF class.
panel("d", "04  Investissement", "Une position importée peut rester sans entreprise rapprochée.", 2440, 800, 1220, 640)
node("d_user", "User", "d", 2480, 900, 320, True, "investisseur")
node("d_company", "Company", "d", 3210, 900, 410, True)
node("portfolio", "Portfolio", "d", 2480, 1110, 440)
node("position", "PortfolioPosition", "d", 3130, 1025, 490)
edge("portfolio", "d_user", "user_id", "titulaire")
edge("position", "portfolio", "portfolio_id", "portefeuille")
edge("position", "d_company", "company_id", "rapprochement")

# E — actual link entities are retained, including the frozen report and score.
panel("e", "05  Projets et analyses de recherche", "L’institution définit le périmètre ; le chercheur remet une analyse versionnée.", 40, 1470, 2370, 1040)
node("e_institution", "User", "e", 80, 1580, 320, True, "institution")
node("e_researcher", "User", "e", 610, 1580, 340, True, "chercheur")
node("e_company", "Company", "e", 1260, 1580, 340, True)
node("e_report", "ESGReport", "e", 1700, 1580, 330, True)
node("e_score", "Score", "e", 2120, 1580, 250, True)
node("project", "Project", "e", 80, 1830, 445)
node("assignment", "ProjectAssignment", "e", 675, 1820, 450)
node("project_company", "ProjectCompany", "e", 1280, 1820, 450)
node("project_document", "ProjectDocument", "e", 1920, 1820, 450)
node("analysis", "Analysis", "e", 675, 2180, 520)
node("analysis_company", "AnalysisCompany", "e", 1730, 2210, 640)
edge("project", "e_institution", "institution_id", "institution")
edge("assignment", "project", "project_id", "projet")
edge("assignment", "e_researcher", "researcher_id", "chercheur")
edge("project_company", "project", "project_id", "projet")
edge("project_company", "e_company", "company_id", "périmètre")
edge("project_document", "project", "project_id", "projet")
edge("project_document", "e_report", "report_id", "document")
edge("analysis", "project", "project_id", "projet")
edge("analysis", "e_researcher", "researcher_id", "auteur")
edge("analysis", "analysis", "previous_analysis_id", "précédente")
edge("analysis_company", "analysis", "analysis_id", "analyse")
edge("analysis_company", "e_company", "company_id", "entreprise")
edge("analysis_company", "e_report", "report_id", "rapport figé")
edge("analysis_company", "e_score", "score_id", "score figé")

# F — the only composition drawn has explicit ORM delete-orphan semantics.
panel("f", "06  Collaboration et validation croisée", "Rattachements et jeux de référence propres au chercheur.", 2440, 1470, 1220, 1040)
node("f_institution", "User", "f", 2480, 1580, 320, True, "institution")
node("f_researcher", "User", "f", 3260, 1580, 360, True, "chercheur")
node("affiliation", "ResearcherAffiliation", "f", 2480, 1760, 505)
node("dataset", "ReferenceDataset", "f", 3110, 1760, 510)
node("dataset_row", "ReferenceDatasetRow", "f", 3110, 2180, 510)
edge("affiliation", "f_institution", "institution_id", "institution")
edge("affiliation", "f_researcher", "researcher_id", "chercheur")
edge("dataset", "f_researcher", "owner_user_id", "auteur")
edge("dataset_row", "dataset", "dataset_id", "lignes", composition=True)


class Drawing:
    def __init__(self):
        for name, file in [("Body", "segoeui.ttf"), ("Bold", "segoeuib.ttf"), ("Mono", "consola.ttf")]:
            pdfmetrics.registerFont(TTFont(name, f"C:/Windows/Fonts/{file}"))
        # A1 landscape; identical vector geometry in PDF and SVG.
        self.pdf = canvas.Canvas(str(OUT / "GreenFinance_Diagramme_Classes.pdf"), pagesize=(2383.94, 1683.78))
        self.pdf.setTitle("GreenFinance Scorer — Diagramme de classes UML")
        self.pdf.setAuthor("GreenFinance Scorer")
        self.scale = min(2383.94 / W, 1683.78 / H)
        self.pdf.translate((2383.94 - W*self.scale)/2, 0)
        self.pdf.scale(self.scale, self.scale)
        self.svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
                    '<title id="title">GreenFinance Scorer — diagramme de classes UML</title>',
                    '<desc id="desc">23 classes persistantes. Noms et attributs issus du code SQLModel ; associations fondées sur les clés étrangères. Références répétées dans les cadres pointillés.</desc>']

    def rect(self, x, y, w, h, fill="white", stroke=None, radius=0, dash=False, width=1.5):
        p = self.pdf
        p.setFillColor(HexColor(fill))
        p.setStrokeColor(HexColor(stroke or fill))
        p.setLineWidth(width)
        p.setDash([6, 4] if dash else [])
        p.roundRect(x, H-y-h, w, h, radius, fill=1, stroke=bool(stroke))
        ds = ' stroke-dasharray="6 4"' if dash else ""
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke or fill}" stroke-width="{width}"{ds}/>')

    def text(self, x, y, s, size=20, color=INK, font="Body", anchor="start", max_width=None):
        if max_width:
            size = min(size, max_width / max(pdfmetrics.stringWidth(s, font, size), 1) * size)
        self.pdf.setFillColor(HexColor(color))
        self.pdf.setFont(font, size)
        if anchor == "middle":
            self.pdf.drawCentredString(x, H-y, s)
        elif anchor == "end":
            self.pdf.drawRightString(x, H-y, s)
        else:
            self.pdf.drawString(x, H-y, s)
        family = "Consolas,monospace" if font == "Mono" else "Segoe UI,Arial,sans-serif"
        weight = "700" if font == "Bold" else "400"
        self.svg.append(f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{family}" font-weight="{weight}" font-size="{size:.2f}" fill="{color}">{html.escape(s)}</text>')

    def path(self, points, color=LINE, width=2, fill="none", close=False):
        p = self.pdf
        p.setDash([])
        p.setStrokeColor(HexColor(color))
        p.setLineWidth(width)
        if fill != "none":
            p.setFillColor(HexColor(fill))
        q = p.beginPath()
        q.moveTo(points[0][0], H-points[0][1])
        for x, y in points[1:]:
            q.lineTo(x, H-y)
        if close:
            q.close()
        p.drawPath(q, stroke=1, fill=fill != "none")
        points_text = " ".join(f"{x},{y}" for x,y in points)
        self.svg.append(f'<{"polygon" if close else "polyline"} points="{points_text}" fill="{fill}" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')

    def pill(self, x, y, s, size=17, color=INK):
        tw = pdfmetrics.stringWidth(s, "Body", size)
        self.rect(x-tw/2-5, y-size+1, tw+10, size+7, "#FFFFFF", radius=3)
        self.text(x, y, s, size, color, anchor="middle")

    def save(self):
        self.pdf.showPage()
        self.pdf.save()
        self.svg.append("</svg>")
        (OUT / "GreenFinance_Diagramme_Classes.svg").write_text("\n".join(self.svg), encoding="utf-8")


def draw_node(d, n):
    x, y, w, h = (n[k] for k in ("x", "y", "w", "h"))
    color = COLORS[n["domain"]]
    if n["ref"]:
        d.rect(x, y, w, h, "#F8FAFB", color, 5, True)
        d.text(x+13, y+22, "« référence »" + (f" · {n['role']}" if n["role"] else ""), 16, MUTED, max_width=w-26)
        d.text(x+13, y+48, n["cls"], 24, color, "Bold", max_width=w-26)
        return
    d.rect(x, y, w, h, "#FFFFFF", "#CDDADF", 5)
    d.rect(x, y, 5, h, color)
    d.text(x+18, y+25, "« entity »", 16, color)
    d.text(x+18, y+57, n["cls"], 28, INK, "Bold", max_width=w-36)
    d.path([(x+1, y+72), (x+w-1, y+72)], "#CDDADF", 1)
    cls = MODELS[n["cls"]]
    for i, key in enumerate(["id"] + FIELDS[n["cls"]].split()):
        f = cls["fields"][key]
        suffix = " {PK}" if key == "id" else (" {FK}" if "foreign_key" in f else "")
        d.text(x+18, y+100+i*25, f"{key} : {short_type(f['type'])}{suffix}", 20, INK, "Mono", max_width=w-36)
    if n["cls"] in NOTES:
        d.path([(x+1, y+h-38), (x+w-1, y+h-38)], "#E0E9ED", 1)
        d.text(x+18, y+h-14, NOTES[n["cls"]], 16, color, max_width=w-36)


def ports(n):
    x, y, w, h = (n[k] for k in ("x", "y", "w", "h"))
    ans = []
    for f in (.25, .5, .75):
        for boundary, outer in [((x+w*f,y),(x+w*f,y-25)), ((x+w*f,y+h),(x+w*f,y+h+25)),
                                ((x,y+h*f),(x-25,y+h*f)), ((x+w,y+h*f),(x+w+25,y+h*f))]:
            ans.append((boundary, (round(outer[0]/10), round(outer[1]/10))))
    return ans


def route(panel, edges):
    """Orthogonal grid routing around cards. Costs discourage shared/crossed lines."""
    domain_nodes = [n for n in NODES.values() if n["domain"] == panel["key"]]
    blocked = set()
    for n in domain_nodes:
        for x in range(math.floor((n["x"]-10)/10), math.ceil((n["x"]+n["w"]+10)/10)+1):
            for y in range(math.floor((n["y"]-10)/10), math.ceil((n["y"]+n["h"]+10)/10)+1):
                blocked.add((x,y))
    xmin, xmax = math.ceil((panel["x"]+15)/10), math.floor((panel["x"]+panel["w"]-15)/10)
    ymin, ymax = math.ceil((panel["y"]+85)/10), math.floor((panel["y"]+panel["h"]-15)/10)
    used = set()
    used_ports = set()
    output = []
    for e in edges:
        start_ports, end_ports = ports(NODES[e["child"]]), ports(NODES[e["parent"]])
        if e["child"] == e["parent"]:
            # A loop must leave and return through different sides.
            start_ports = [p for p in start_ports if p[0][0] == NODES[e["child"]]["x"]]
            end_ports = [p for p in end_ports if p[0][1] == NODES[e["child"]]["y"]]
        starts = {grid: b for b,grid in start_ports if grid not in blocked and xmin<=grid[0]<=xmax and ymin<=grid[1]<=ymax}
        ends = {grid: b for b,grid in end_ports if grid not in blocked and xmin<=grid[0]<=xmax and ymin<=grid[1]<=ymax}
        assert starts and ends, (e, "No free ports")
        dist, prev, pq = {}, {}, []
        for grid in starts:
            state = (*grid, 4)
            cost = 150 if grid in used_ports else 0
            dist[state] = cost
            heapq.heappush(pq, (cost, state))
        final = None
        while pq:
            cost, state = heapq.heappop(pq)
            if cost != dist[state]:
                continue
            x,y,direction = state
            if (x,y) in ends:
                final = state
                break
            for dr,(dx,dy) in enumerate(((1,0),(-1,0),(0,1),(0,-1))):
                new = x+dx,y+dy
                if not (xmin<=new[0]<=xmax and ymin<=new[1]<=ymax) or new in blocked:
                    continue
                nxt = (*new,dr)
                penalty = 1 + (10 if direction not in (4,dr) else 0) + (45 if new in used else 0)
                if new in ends and new in used_ports:
                    penalty += 150
                nc = cost+penalty
                if nc < dist.get(nxt,float("inf")):
                    dist[nxt] = nc
                    prev[nxt] = state
                    heapq.heappush(pq,(nc,nxt))
        if final is None:
            raise RuntimeError(f"Cannot route {e}")
        states = [final]
        while states[-1] in prev:
            states.append(prev[states[-1]])
        states.reverse()
        grid_path = [(s[0],s[1]) for s in states]
        used.update(grid_path)
        used_ports.update((grid_path[0],grid_path[-1]))
        start, end = starts[grid_path[0]], ends[grid_path[-1]]
        points = [start] + [(x*10,y*10) for x,y in grid_path] + [end]
        # Remove collinear intermediate points; retain the short port connectors.
        compact = [points[0]]
        for i in range(1,len(points)-1):
            a,b,c = compact[-1],points[i],points[i+1]
            if (a[0]==b[0]==c[0]) or (a[1]==b[1]==c[1]):
                continue
            compact.append(b)
        compact.append(points[-1])
        e["path"] = compact
        output.append(e)
    return output


def draw_edge(d, e):
    points = e["path"]
    color = COLORS[e["domain"]]
    d.path(points,color,2)
    for endpoint, neighbor, mult in [(points[0],points[1],e["cm"]),(points[-1],points[-2],e["pm"])]:
        dx,dy = neighbor[0]-endpoint[0],neighbor[1]-endpoint[1]
        norm = math.hypot(dx,dy)
        ux,uy=dx/norm,dy/norm
        d.pill(endpoint[0]+ux*28-uy*16,endpoint[1]+uy*28+ux*16+5,mult,17,color)
    if e["composition"]:
        end, prev = points[-1],points[-2]
        dx,dy=prev[0]-end[0],prev[1]-end[1]
        ln=math.hypot(dx,dy)
        ux,uy=dx/ln,dy/ln
        diamond=[end,(end[0]+ux*10-uy*6,end[1]+uy*10+ux*6),(end[0]+ux*20,end[1]+uy*20),(end[0]+ux*10+uy*6,end[1]+uy*10-ux*6)]
        d.path(diamond,color,1.5,color,True)
    segments = sorted(zip(points,points[1:]),key=lambda ab: abs(ab[0][0]-ab[1][0])+abs(ab[0][1]-ab[1][1]),reverse=True)
    a,b = segments[0]
    # Name belongs to the association; source/FK mapping is in the ledger.
    d.pill((a[0]+b[0])/2,(a[1]+b[1])/2-8,e["label"],16,color)


def write_sources():
    selected = set(FIELDS)
    visual_relations = {(NODES[e["child"]]["cls"],e["fk"]) for e in EDGES}
    expected = {(name,key) for name in selected for key,f in MODELS[name]["fields"].items()
                if f.get("target") in selected}
    assert expected == visual_relations, ("Missing/extra relations", expected-visual_relations,visual_relations-expected)
    assert len([n for n in NODES.values() if not n["ref"]]) == len(selected) == 23
    for n in NODES.values():
        p = next(p for p in PANELS if p["key"] == n["domain"])
        assert n["x"]>=p["x"] and n["y"]>=p["y"] and n["x"]+n["w"]<=p["x"]+p["w"] and n["y"]+n["h"]<=p["y"]+p["h"], ("Node outside panel",n)
    for i,a in enumerate(NODES.values()):
        for b in list(NODES.values())[i+1:]:
            assert not (a["x"]<b["x"]+b["w"] and b["x"]<a["x"]+a["w"] and a["y"]<b["y"]+b["h"] and b["y"]<a["y"]+a["h"]), ("Overlapping nodes",a["key"],b["key"])
    (OUT/"inventaire_modele.json").write_text(json.dumps({"date":"2026-10-06","classes":MODELS,"selected":sorted(selected),"visual_relations":EDGES},ensure_ascii=False,indent=2),encoding="utf-8")
    text = ["@startuml", "' Semantic editable source. SVG/PDF layout is generated separately.", "hide empty methods", "skinparam classAttributeIconSize 0", "skinparam linetype ortho", "skinparam defaultFontName Segoe UI", "skinparam shadowing false", "title GreenFinance Scorer — Classes UML (code courant, 06/10/2026)"]
    for p in PANELS:
        text.append(f'package "{p["title"]}" {{')
        for n in NODES.values():
            if n["ref"] or n["domain"]!=p["key"]:
                continue
            name=n["cls"]
            text.append(f'class {name} <<entity>> {{')
            for key in ["id"]+FIELDS[name].split():
                text.append(f'  {key} : {short_type(MODELS[name]["fields"][key]["type"])}')
            text.append("}")
            if name in NOTES:
                text.append(f'note bottom of {name} : {NOTES[name]}')
        text.append("}")
    for e in EDGES:
        a,b=NODES[e["child"]]["cls"],NODES[e["parent"]]["cls"]
        arrow="--*" if e["composition"] else "--"
        text.append(f'{a} "{e["cm"]}" {arrow} "{e["pm"]}" {b} : {e["fk"]}')
    text += ["legend bottom", "? = nullable ; toutes les classes dérivent de SQLModel.", "Rôles : ADMIN, ENTERPRISE, AUDITOR, INVESTOR, RESEARCHER, INSTITUTION.", "Cardinalités du schéma ; classes complémentaires et règles de service dans l’audit.", "endlegend", "@enduml"]
    (OUT/"GreenFinance_Diagramme_Classes.puml").write_text("\n".join(text)+"\n",encoding="utf-8")
    ledger=["# Traçabilité du diagramme de classes", "", "Généré depuis l’AST des modèles. Aucun accès à une base en exécution.", "", "## Classes et attributs affichés", "", "| Classe | Source | Attributs affichés |", "|---|---|---|"]
    for name in FIELDS:
        c=MODELS[name]
        ledger.append(f'| `{name}` | [{c["file"]}:{c["line"]}](../../{c["file"]}#L{c["line"]}) | '+", ".join(f'`{k}` (L{c["fields"][k]["line"]})' for k in ["id"]+FIELDS[name].split())+" |")
    ledger += ["", "## Associations affichées", "", "Lecture : pour une instance de la classe source, la cible est obligatoire (1) ou optionnelle (0..1). La colonne inverse indique combien de sources une cible peut référencer.", "", "| Source et FK réelle | Cible | Multiplicité cible | Inverse | Suppression SQL | Preuve |", "|---|---|---|---|---|---|"]
    for e in EDGES:
        name=NODES[e["child"]]["cls"]
        f=MODELS[name]["fields"][e["fk"]]
        ledger.append(f'| `{name}.{e["fk"]}` | `{f["target"]}` | {e["pm"]} | {e["cm"]} | {f["ondelete"]} | [{e["file"]}:{e["line"]}](../../{e["file"]}#L{e["line"]}) |')
    ledger += ["", "## Classes non développées dans la vue de synthèse", "", "Ces classes existent réellement. Leur omission est graphique ; l’inventaire JSON conserve leurs attributs, FK, méthodes et contraintes.", "", "| Classe | Source |", "|---|---|"]
    for name in sorted(set(MODELS)-selected):
        c=MODELS[name]
        ledger.append(f'| `{name}` | [{c["file"]}:{c["line"]}](../../{c["file"]}#L{c["line"]}) |')
    (OUT/"03_tracabilite_classes.md").write_text("\n".join(ledger)+"\n",encoding="utf-8")


def main():
    write_sources()
    d=Drawing()
    d.rect(0,0,W,H,BG)
    d.text(45,65,"GREENFINANCE SCORER",22,"#137866","Bold")
    d.text(45,120,"Diagramme de classes UML",46,INK,"Bold")
    d.text(W-45,72,"23 CLASSES PRINCIPALES  /  6 DOMAINES",22,MUTED,anchor="end")
    d.text(W-45,115,"État du code • 6 octobre 2026",21,MUTED,anchor="end")
    for p in PANELS:
        d.rect(p["x"],p["y"],p["w"],p["h"],"#FFFFFF","#D4E0E5",12)
        d.text(p["x"]+24,p["y"]+37,p["title"],29,COLORS[p["key"]],"Bold")
        d.text(p["x"]+24,p["y"]+67,p["desc"],19,MUTED,max_width=p["w"]-48)
        print("Routing",p["key"],flush=True)
        for e in route(p,[e for e in EDGES if e["domain"]==p["key"]]):
            draw_edge(d,e)
    for n in NODES.values():
        draw_node(d,n)
    # One diagram, explicit scope and UML legend.
    d.rect(40,2545,3620,255,"#E6EEF1",radius=10)
    d.text(65,2585,"CONVENTIONS DE LECTURE",21,INK,"Bold")
    lines=[
        "Trait plein : association. Multiplicités à chaque extrémité : 1 obligatoire · 0..1 optionnel · 0..* multiple. Losange plein : composition (lignes d’un jeu de référence).",
        "Cadre pointillé « référence » : même classe répétée pour garder des liens courts ; aucune nouvelle classe. Les six cadres sont des regroupements de lecture.",
        "Attributs : noms et types réels ; ? = nullable ; {PK} = identifiant ; {FK} = clé étrangère. Les autres FK sont matérialisées par les associations (table complète dans la traçabilité).",
        "Toutes les entités héritent de SQLModel ; aucun héritage métier. Les opérations de dépôt, audit et calcul sont des fonctions de services, pas des méthodes de ces entités.",
        "Cardinalités du schéma déclaré : Company.owner_user_id non unique (malgré User.company scalaire). Analysis exige ≥ 1 entreprise à la création via le service.",
        "Vue de synthèse : 23 / 31 classes persistantes ; 8 classes complémentaires dans l’audit. Source : modèles SQLModel + migrations + services ; base en exécution non inspectée.",
    ]
    for i,s in enumerate(lines):
        d.text(65,2625+i*29,s,20,MUTED,max_width=3560)
    d.text(45,2830,"UML-01  •  Sources, contraintes et écarts : 02_audit_modele_reel.md / 03_tracabilite_classes.md",18,MUTED)
    d.text(W-45,2830,"SVG et PDF vectoriels • agrandir par domaine pour la soutenance",18,MUTED,anchor="end")
    d.save()
    write_sources()
    import fitz
    doc=fitz.open(OUT/"GreenFinance_Diagramme_Classes.pdf")
    for filename,width in [("GreenFinance_Diagramme_Classes.png",3700),("apercu_classes.png",1850)]:
        page=doc[0]
        pix=page.get_pixmap(matrix=fitz.Matrix(width/page.rect.width,width/page.rect.width),alpha=False)
        pix.save(OUT/filename)
    print(json.dumps({"classes_total":len(MODELS),"classes_visual":len(FIELDS),"associations":len(EDGES),"output":str(OUT)},ensure_ascii=False))


if __name__=="__main__":
    main()
