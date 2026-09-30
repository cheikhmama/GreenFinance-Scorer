"""Validation croisée des scores de la plateforme contre un jeu de données public (tâche 3.3,
docs/WORKFLOWS.md §3.4).

Un Chercheur importe un fichier CSV (Kaggle, CDP, GRI...) dans une zone de préparation qui lui est
propre (app/researcher/models.py::ReferenceDataset), puis obtient, pilier par pilier, la
corrélation de rang (Spearman) et l'écart absolu moyen entre ces scores et les scores officiels de
la plateforme. Rien ici n'écrit dans les données de la plateforme.

Import — format tolérant, parce qu'un jeu public est rarement propre :
- CSV (`,`, `;` ou tabulation ; virgule décimale avec `;`), au plus 5 Mo / 20 000 lignes.
- Colonnes reconnues (casse ignorée) : `isin`, `lei`, `name` / `company_name`, et au moins une de
  `environmental`, `social`, `governance`, `total`. Les autres colonnes sont ignorées.
- Une ligne sans identifiant valide (chiffre de contrôle ISIN/LEI vérifié), sans score, ou dont un
  score est illisible ou hors de l'échelle déclarée est écartée avec son motif — le reste est
  importé. Aucune ligne importable : rien n'est enregistré.

Rapprochement : par ISIN, puis par LEI — jamais par nom seul — avec les entreprises publiées du
périmètre de projets du Chercheur (même règle que toutes ses autres vues : aucune entreprise
hors périmètre n'est révélée, une ligne non rapprochée ne dit jamais pourquoi au-delà de
« inconnue »). Le score comparé est le score officiel du dernier rapport validé.

Échelles : chaque valeur du jeu est ramenée sur 0-100 (inversée si « plus bas = meilleur ») avant
l'écart absolu moyen ; la corrélation de Spearman, elle, ne dépend pas de l'échelle.
"""

import csv
import io
import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session, col, func, select

from app.auth.models import User
from app.company.identifiers import isin_valide, lei_valide
from app.company.models import Company
from app.core.enums import ComparedScore, UnmatchedReason
from app.core.exceptions import NotFoundError, ValidationError
from app.investor.entreprises import dernier_rapport_valide
from app.researcher.models import ReferenceDataset, ReferenceDatasetRow
from app.researcher.projets import entreprises_perimetre_chercheur
from app.researcher.schemas import (
    CrossValidationMatch,
    CrossValidationReport,
    ReferenceDatasetImportResult,
    ReferenceDatasetRequest,
    ReferenceDatasetSummary,
    ScoreAgreement,
    SkippedLine,
    UnmatchedLine,
)
from app.scoring.engine import score_officiel
from app.scoring.models import Score

TAILLE_MAX_OCTETS = 5 * 1024 * 1024
LIGNES_MAX = 20_000
LIGNES_ECARTEES_AFFICHEES = 100
MIN_PAIRES_SPEARMAN = 3

# Colonne du fichier -> attribut de ReferenceDatasetRow / score comparé de la plateforme.
_COLONNES_SCORE: dict[str, tuple[str, ComparedScore]] = {
    "environmental": ("environmental_score", ComparedScore.ENVIRONMENTAL),
    "social": ("social_score", ComparedScore.SOCIAL),
    "governance": ("governance_score", ComparedScore.GOVERNANCE),
    "total": ("total_score", ComparedScore.GLOBAL),
}
_SCORE_PLATEFORME: dict[ComparedScore, str] = {
    ComparedScore.ENVIRONMENTAL: "environmental_score",
    ComparedScore.SOCIAL: "social_score",
    ComparedScore.GOVERNANCE: "governance_score",
    ComparedScore.GLOBAL: "global_score",
}


# --- statistiques (pures) ---------------------------------------------------------------------


def rangs_moyens(valeurs: list[float]) -> list[float]:
    """Rang (1 = plus petit) de chaque valeur ; les ex æquo reçoivent la moyenne de leurs rangs."""
    ordre = sorted(range(len(valeurs)), key=lambda i: valeurs[i])
    rangs = [0.0] * len(valeurs)
    debut = 0
    while debut < len(ordre):
        fin = debut
        while fin + 1 < len(ordre) and valeurs[ordre[fin + 1]] == valeurs[ordre[debut]]:
            fin += 1
        rang = (debut + fin) / 2 + 1
        for position in range(debut, fin + 1):
            rangs[ordre[position]] = rang
        debut = fin + 1
    return rangs


def spearman(x: list[float], y: list[float]) -> float | None:
    """Corrélation de Pearson des rangs moyens (définition générale, exacte avec ex æquo). None
    sous MIN_PAIRES_SPEARMAN paires ou si une série est constante — jamais un 0 trompeur."""
    if len(x) != len(y) or len(x) < MIN_PAIRES_SPEARMAN:
        return None
    rx, ry = rangs_moyens(x), rangs_moyens(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    covariance = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    variance_x = sum((a - mx) ** 2 for a in rx)
    variance_y = sum((b - my) ** 2 for b in ry)
    if variance_x == 0 or variance_y == 0:
        return None
    return covariance / math.sqrt(variance_x * variance_y)


def sur_cent(valeur: float, minimum: float, maximum: float, plus_haut_est_meilleur: bool) -> float:
    """Ramène une valeur de l'échelle du jeu de données sur 0-100, « plus haut = meilleur »."""
    fraction = (valeur - minimum) / (maximum - minimum)
    return (fraction if plus_haut_est_meilleur else 1 - fraction) * 100


# --- import -----------------------------------------------------------------------------------


@dataclass
class _LigneLue:
    numero: int
    valeurs: dict[str, str]


def _lire_csv(contenu: bytes) -> tuple[list[_LigneLue], bool]:
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ValidationError("Le fichier dépasse 5 Mo.", code="import_trop_volumineux")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("Le fichier doit être encodé en UTF-8.", code="import_illisible") from exc
    premiere = texte.splitlines()[0] if texte.strip() else ""
    separateur = max((",", ";", "\t"), key=premiere.count)
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=separateur)
    colonnes = {(c or "").strip().lower() for c in lecteur.fieldnames or []}
    if not colonnes & {"isin", "lei"} or not colonnes & set(_COLONNES_SCORE):
        raise ValidationError(
            "En-tête CSV attendu avec une colonne isin ou lei et au moins une colonne de score "
            "(environmental, social, governance, total).",
            code="import_illisible",
        )
    lignes = [
        _LigneLue(numero + 2, {(k or "").strip().lower(): (v or "").strip() for k, v in ligne.items()})
        for numero, ligne in enumerate(lecteur)
        if any((v or "").strip() for v in ligne.values() if isinstance(v, str))
    ]
    if len(lignes) > LIGNES_MAX:
        raise ValidationError(f"Au plus {LIGNES_MAX} lignes par import.", code="import_trop_volumineux")
    return lignes, separateur == ";"


def _identifiant(brut: str, valide: Callable[[str], bool]) -> str | None:
    valeur = brut.replace(" ", "").upper()
    return valeur if valeur and valide(valeur) else None


def _ligne_importee(
    ligne: _LigneLue, decimale_virgule: bool, requete: ReferenceDatasetRequest
) -> ReferenceDatasetRow:
    """ValueError avec le motif si la ligne doit être écartée."""
    isin = _identifiant(ligne.valeurs.get("isin", ""), isin_valide)
    lei = _identifiant(ligne.valeurs.get("lei", ""), lei_valide)
    if isin is None and lei is None:
        raise ValueError("aucun ISIN ni LEI valide")
    scores: dict[str, float] = {}
    for colonne, (attribut, _compare) in _COLONNES_SCORE.items():
        brut = ligne.valeurs.get(colonne, "")
        if not brut:
            continue
        texte = brut.replace(",", ".") if decimale_virgule else brut
        try:
            valeur = float(texte)
        except ValueError as exc:
            raise ValueError(f"{colonne} illisible : {brut}") from exc
        if not math.isfinite(valeur) or not requete.scale_min <= valeur <= requete.scale_max:
            raise ValueError(f"{colonne} hors de l'échelle déclarée : {brut}")
        scores[attribut] = valeur
    if not scores:
        raise ValueError("aucun score")
    nom = ligne.valeurs.get("name") or ligne.valeurs.get("company_name") or None
    return ReferenceDatasetRow(
        line_number=ligne.numero,
        isin=isin,
        lei=lei,
        company_name=nom[:200] if nom else None,
        **scores,
    )


def resume(session: Session, dataset: ReferenceDataset) -> ReferenceDatasetSummary:
    nombre = session.exec(
        select(func.count())
        .select_from(ReferenceDatasetRow)
        .where(col(ReferenceDatasetRow.dataset_id) == dataset.id)
    ).one()
    return ReferenceDatasetSummary(
        id=dataset.id,
        name=dataset.name,
        source_url=dataset.source_url,
        licence=dataset.licence,
        scale_min=dataset.scale_min,
        scale_max=dataset.scale_max,
        higher_is_better=dataset.higher_is_better,
        created_at=dataset.created_at,
        row_count=nombre,
    )


def importer(
    session: Session, chercheur: User, requete: ReferenceDatasetRequest, contenu: bytes
) -> ReferenceDatasetImportResult:
    lignes, decimale_virgule = _lire_csv(contenu)
    importees: list[ReferenceDatasetRow] = []
    ecartees: list[SkippedLine] = []
    for ligne in lignes:
        try:
            importees.append(_ligne_importee(ligne, decimale_virgule, requete))
        except ValueError as exc:
            ecartees.append(SkippedLine(line=ligne.numero, reason=str(exc)))
    if not importees:
        raise ValidationError(
            "Aucune ligne importable : rien n'a été enregistré.",
            code="import_vide",
            fields={f"line_{e.line}": e.reason for e in ecartees[:LIGNES_ECARTEES_AFFICHEES]},
        )

    dataset = ReferenceDataset(owner_user_id=chercheur.id, **requete.model_dump())
    session.add(dataset)
    session.flush()
    for ligne_importee in importees:
        ligne_importee.dataset_id = dataset.id
    session.add_all(importees)
    session.commit()
    session.refresh(dataset)
    return ReferenceDatasetImportResult(
        dataset=resume(session, dataset),
        imported=len(importees),
        skipped=len(ecartees),
        skipped_lines=ecartees[:LIGNES_ECARTEES_AFFICHEES],
    )


# --- consultation -----------------------------------------------------------------------------


def dataset_du_chercheur(
    session: Session, chercheur: User, dataset_id: uuid.UUID
) -> ReferenceDataset:
    dataset = session.get(ReferenceDataset, dataset_id)
    if dataset is None or dataset.owner_user_id != chercheur.id:
        raise NotFoundError("Jeu de données introuvable.", code="jeu_de_donnees_introuvable")
    return dataset


def lister(session: Session, chercheur: User) -> list[ReferenceDatasetSummary]:
    datasets = session.exec(
        select(ReferenceDataset)
        .where(col(ReferenceDataset.owner_user_id) == chercheur.id)
        .order_by(col(ReferenceDataset.created_at).desc())
    ).all()
    return [resume(session, dataset) for dataset in datasets]


def supprimer(session: Session, chercheur: User, dataset_id: uuid.UUID) -> None:
    session.delete(dataset_du_chercheur(session, chercheur, dataset_id))
    session.commit()


def rapport(session: Session, chercheur: User, dataset_id: uuid.UUID) -> CrossValidationReport:
    dataset = dataset_du_chercheur(session, chercheur, dataset_id)
    perimetre = entreprises_perimetre_chercheur(session, chercheur.id)
    entreprises = (
        session.exec(
            select(Company).where(
                col(Company.id).in_(perimetre), col(Company.published_at).is_not(None)
            )
        ).all()
        if perimetre
        else []
    )
    par_isin = {e.isin: e for e in entreprises if e.isin}
    par_lei = {e.lei: e for e in entreprises if e.lei}
    lignes = session.exec(
        select(ReferenceDatasetRow)
        .where(col(ReferenceDatasetRow.dataset_id) == dataset.id)
        .order_by(col(ReferenceDatasetRow.line_number))
    ).all()

    correspondances: list[CrossValidationMatch] = []
    non_rapprochees: list[UnmatchedLine] = []
    deja_vues: set[uuid.UUID] = set()
    paires: dict[ComparedScore, list[tuple[float, float]]] = {c: [] for c in ComparedScore}
    for ligne in lignes:
        entreprise = (par_isin.get(ligne.isin) if ligne.isin else None) or (
            par_lei.get(ligne.lei) if ligne.lei else None
        )
        motif: UnmatchedReason | None = None
        score: Score | None = None
        if entreprise is None:
            motif = UnmatchedReason.UNKNOWN
        elif entreprise.id in deja_vues:
            motif = UnmatchedReason.DUPLICATE
        else:
            rapport_valide = dernier_rapport_valide(session, entreprise.id)
            score = score_officiel(session, rapport_valide.id) if rapport_valide else None
            if score is None:
                motif = UnmatchedReason.NO_PLATFORM_SCORE
        if motif is not None or entreprise is None or score is None:
            non_rapprochees.append(
                UnmatchedLine(
                    line=ligne.line_number,
                    isin=ligne.isin,
                    lei=ligne.lei,
                    company_name=ligne.company_name,
                    reason=motif or UnmatchedReason.UNKNOWN,
                )
            )
            continue
        deja_vues.add(entreprise.id)

        jeu: dict[ComparedScore, float | None] = {}
        plateforme: dict[ComparedScore, float | None] = {}
        for attribut, compare in _COLONNES_SCORE.values():
            brute = getattr(ligne, attribut)
            jeu[compare] = (
                sur_cent(brute, dataset.scale_min, dataset.scale_max, dataset.higher_is_better)
                if brute is not None
                else None
            )
            plateforme[compare] = getattr(score, _SCORE_PLATEFORME[compare])
            valeur_jeu, valeur_plateforme = jeu[compare], plateforme[compare]
            if valeur_jeu is not None and valeur_plateforme is not None:
                paires[compare].append((valeur_jeu, valeur_plateforme))
        correspondances.append(
            CrossValidationMatch(
                line=ligne.line_number,
                company_id=entreprise.id,
                company_name=entreprise.name,
                dataset_scores=jeu,
                platform_scores=plateforme,
            )
        )

    return CrossValidationReport(
        dataset=resume(session, dataset),
        matched=len(correspondances),
        unmatched=len(non_rapprochees),
        agreement=[
            ScoreAgreement(
                score=compare,
                pairs=len(valeurs),
                spearman=spearman([a for a, _ in valeurs], [b for _, b in valeurs]),
                mean_absolute_difference=(
                    sum(abs(a - b) for a, b in valeurs) / len(valeurs) if valeurs else None
                ),
            )
            for compare, valeurs in paires.items()
        ],
        matches=correspondances,
        unmatched_lines=non_rapprochees,
    )
