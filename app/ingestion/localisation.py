"""Où une valeur extraite se lit sur sa page (tâche 5.5) : les boîtes englobantes du texte cité,
retrouvées dans la sortie Docling du rapport, pour que l'espace Auditeur les surligne sur le PDF.

Deux indices, dans cet ordre :
1. la citation verbatim renvoyée par le LLM (`citation_source`) : les blocs de texte de la page
   qui la contiennent (ou qu'elle contient, quand elle court sur plusieurs blocs) ;
2. à défaut, la valeur elle-même : les cellules de tableau, ou les courts blocs de texte, qui
   contiennent ce nombre (« 143,510 », « 143 510 », « 12 500.0 » et « 12 500,0 » sont lus comme
   des nombres, séparateurs de milliers et décimale compris).

Mieux vaut aucune boîte qu'une fausse : une valeur qui ressemble à une année, ou trouvée à plus de
MAX_CORRESPONDANCES endroits de la page, n'est pas localisée — la page entière reste la preuve.

Coordonnées rendues en fractions de la page (0 à 1), origine en haut à gauche : indépendantes de
l'échelle d'affichage du PDF. Module pur, sans base ni modèle lourd : testé directement sur des
sorties Docling réelles (data_test/docling_json/).
"""

import math
import re
import unicodedata
from dataclasses import asdict, dataclass

from docling_core.types.doc import BoundingBox, DoclingDocument, TableItem, TextItem

LONGUEUR_MIN_CITATION = 8
LONGUEUR_MIN_BLOC_CONTENU = 15
LONGUEUR_MAX_BLOC_VALEUR = 60
MAX_CORRESPONDANCES = 3
# Une valeur entière de cet intervalle se confond avec les années des en-têtes de colonnes.
ANNEES = range(1900, 2101)

# Un nombre écrit : chiffres, éventuellement séparés par des espaces (y compris insécables), des
# virgules ou des points.
_NOMBRE = re.compile(r"\d(?:[\d\u00a0\u202f ,.]*\d)?")


@dataclass(frozen=True)
class Boite:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    def en_dict(self) -> dict[str, float | int]:
        return asdict(self)


def _normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKC", texte).casefold()
    # Espaces insécables, fines, etc. : un seul espace.
    return re.sub(r"\s+", " ", texte).strip()


def lire_nombre(ecrit: str) -> float | None:
    """« 12 500.0 », « 143,510 », « 1.234.567,8 », « 22,5 » -> nombre ; None si illisible.
    Le dernier séparateur suivi d'exactement trois chiffres est un séparateur de milliers, sauf
    s'il est le seul de son espèce et précédé d'un autre (« 1,234.5 ») ; sinon il est décimal."""
    compact = re.sub(r"[\s\u00a0\u202f]", "", ecrit)
    separateurs = [c for c in compact if c in ",."]
    if not separateurs:
        return float(compact) if compact.isdigit() else None
    dernier = max(compact.rfind(","), compact.rfind("."))
    apres = compact[dernier + 1:]
    autres = set(separateurs[:-1])
    if len(apres) == 3 and (not autres or autres == {compact[dernier]}):
        entier = re.sub(r"[,.]", "", compact)
        return float(entier) if entier.isdigit() else None
    entier, decimales = re.sub(r"[,.]", "", compact[:dernier]), apres
    if not entier.isdigit() or not decimales.isdigit():
        return None
    return float(f"{entier}.{decimales}")


def _nombres(texte: str) -> list[float]:
    return [n for n in (lire_nombre(m.group()) for m in _NOMBRE.finditer(texte)) if n is not None]


def _blocs_de_la_page(document: DoclingDocument, page: int) -> tuple[list[tuple[str, BoundingBox]], list[tuple[str, BoundingBox]]]:
    """(blocs de texte, cellules de tableau) de la page, chacun avec sa boîte."""
    textes: list[tuple[str, BoundingBox]] = []
    cellules: list[tuple[str, BoundingBox]] = []
    for element, _niveau in document.iterate_items(page_no=page):
        if isinstance(element, TableItem):
            for cellule in element.data.table_cells:
                if cellule.bbox is not None and cellule.text.strip():
                    cellules.append((cellule.text, cellule.bbox))
        elif isinstance(element, TextItem) and element.text.strip():
            for provenance in element.prov:
                if provenance.page_no == page:
                    textes.append((element.text, provenance.bbox))
    return textes, cellules


def _vers_boite(bbox: BoundingBox, page: int, document: DoclingDocument) -> Boite:
    taille = document.pages[page].size
    normalisee = bbox.to_top_left_origin(page_height=taille.height).normalized(taille)

    def borne(v: float) -> float:
        return round(min(max(v, 0.0), 1.0), 4)

    return Boite(
        page=page,
        x0=borne(min(normalisee.l, normalisee.r)),
        y0=borne(min(normalisee.t, normalisee.b)),
        x1=borne(max(normalisee.l, normalisee.r)),
        y1=borne(max(normalisee.t, normalisee.b)),
    )


def _par_citation(citation: str, textes: list[tuple[str, BoundingBox]]) -> list[BoundingBox]:
    cible = _normaliser(citation)
    if len(cible) < LONGUEUR_MIN_CITATION:
        return []
    trouvees = []
    for texte, bbox in textes:
        bloc = _normaliser(texte)
        if cible in bloc or (len(bloc) >= LONGUEUR_MIN_BLOC_CONTENU and bloc in cible):
            trouvees.append(bbox)
    return trouvees


def _valeur_cherchee(valeur_brute: str | None, valeur: float | None) -> float | None:
    if valeur is not None:
        return float(valeur)
    nombres = _nombres(valeur_brute) if valeur_brute else []
    return nombres[0] if len(nombres) == 1 else None


def _par_valeur(
    cible: float | None,
    textes: list[tuple[str, BoundingBox]],
    cellules: list[tuple[str, BoundingBox]],
) -> list[BoundingBox]:
    if cible is None or (cible.is_integer() and int(cible) in ANNEES):
        return []
    candidats = cellules + [(t, b) for t, b in textes if len(t) <= LONGUEUR_MAX_BLOC_VALEUR]
    return [
        bbox
        for texte, bbox in candidats
        if any(math.isclose(n, cible, rel_tol=1e-9, abs_tol=1e-9) for n in _nombres(texte))
    ]


def localiser(
    document: DoclingDocument,
    page: int,
    *,
    citation: str | None,
    valeur_brute: str | None,
    valeur: float | None,
) -> list[Boite]:
    if page not in document.pages:
        return []
    textes, cellules = _blocs_de_la_page(document, page)
    trouvees = _par_citation(citation, textes) if citation else []
    if not trouvees:
        trouvees = _par_valeur(_valeur_cherchee(valeur_brute, valeur), textes, cellules)
    if not trouvees or len(trouvees) > MAX_CORRESPONDANCES:
        return []
    return [_vers_boite(bbox, page, document) for bbox in trouvees]
