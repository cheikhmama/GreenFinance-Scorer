"""Moteur de calcul du score ESG (Phase 5 §9, tâche 3.1).

Point d'entrée : calculer_score(session, rapport_id). Lit les ESGMetric déjà persistés pour ce
rapport, les regroupe par pilier, normalise chaque valeur selon la configuration de référence et
persiste un Score avec sa couverture.

Configuration verrouillée (tâche 3.1, docs/ARCHITECTURE.md §5.3) : le calcul relit toujours le
YAML STOCKÉ sur la ligne scoring_configs (content_yaml), jamais le fichier sur disque. Le fichier
(config/weights/default.yaml) ne sert qu'à enregistrer la référence courante, identifiée par
l'empreinte de son contenu : le modifier — même sans changer son numéro de version — enregistre
une nouvelle configuration au prochain calcul, et les scores anciens gardent la leur.

Donnée manquante (Phase 5 §9) : un indicateur absent est retiré du calcul de son pilier, dont le
poids se répartit sur les indicateurs présents — jamais compté comme 0. Un pilier sans indicateur
présent reste NULL et sort du score global. La part pondérée de ce qui était présent est la
couverture (coverage_rate), stockée et affichée avec le score ; sous le seuil min_coverage de la
configuration, le score n'est pas publiable (couverture_insuffisante).

Transactions (tâche 1.6) : aucune fonction de ce module n'appelle session.commit() — l'appelant
possède la limite de transaction. Les lectures (score_officiel, score_public, apercu_score)
n'écrivent jamais rien.
"""

import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import Pillar
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import ESGMetric, ESGReport
from app.scoring.config_schema import (
    ConfigurationScoring,
    PilierConfig,
    charger_configuration,
    empreinte_configuration,
)
from app.scoring.models import Score, ScoringConfig
from app.scoring.normalization import normaliser
from app.scoring.schemas import ScoreESGPublic


@lru_cache
def _schema_depuis_contenu(contenu_yaml: str) -> ConfigurationScoring:
    """Un même contenu se parse toujours à l'identique — mis en cache par contenu, jamais par
    chemin : c'est le contenu qui fait foi."""
    return charger_configuration(contenu_yaml)


def _contenu_reference() -> str:
    return Path(get_settings().default_scoring_config).read_text(encoding="utf-8")


def schema_configuration(configuration: ScoringConfig) -> ConfigurationScoring:
    if configuration.content_yaml is None:
        raise ValidationError(
            "Le contenu de cette configuration de pondération n'a pas été conservé (antérieure "
            "à la tâche 3.1) : aucun calcul n'est possible sous elle.",
            code="configuration_sans_contenu",
        )
    return _schema_depuis_contenu(configuration.content_yaml)


def _trouver_par_empreinte(
    session: Session, empreinte: str, proprietaire_id: uuid.UUID | None
) -> ScoringConfig | None:
    proprietaire = (
        col(ScoringConfig.owner_user_id).is_(None)
        if proprietaire_id is None
        else col(ScoringConfig.owner_user_id) == proprietaire_id
    )
    return session.exec(
        select(ScoringConfig).where(col(ScoringConfig.content_hash) == empreinte, proprietaire)
    ).first()


def enregistrer_configuration(
    session: Session, contenu_yaml: str, proprietaire_id: uuid.UUID | None = None
) -> ScoringConfig:
    """Chemin d'écriture : la ligne de cette méthodologie pour ce propriétaire (nul = référence),
    créée si besoin. Valide le contenu d'abord (ValidationError `configuration_invalide`), ne
    commite jamais — INSERT ... ON CONFLICT DO NOTHING sur l'index d'unicité partiel concerné,
    sans doublon même sous deux validations concurrentes."""
    try:
        schema = _schema_depuis_contenu(contenu_yaml)
    except ValueError as exc:
        raise ValidationError(
            f"Configuration de pondération invalide : {exc}", code="configuration_invalide"
        ) from exc
    empreinte = empreinte_configuration(contenu_yaml)
    existante = _trouver_par_empreinte(session, empreinte, proprietaire_id)
    if existante is not None:
        return existante

    colonnes_conflit, filtre_conflit = (
        (["content_hash"], text("owner_user_id IS NULL"))
        if proprietaire_id is None
        else (["owner_user_id", "content_hash"], text("owner_user_id IS NOT NULL"))
    )
    session.execute(
        insert(ScoringConfig)
        .values(
            id=uuid.uuid4(),
            name=schema.nom,
            version=schema.version,
            content_yaml=contenu_yaml,
            content_hash=empreinte,
            created_at=utcnow(),
            owner_user_id=proprietaire_id,
        )
        .on_conflict_do_nothing(index_elements=colonnes_conflit, index_where=filtre_conflit)
    )
    configuration = _trouver_par_empreinte(session, empreinte, proprietaire_id)
    assert configuration is not None  # insérée ci-dessus, ou par une transaction concurrente
    return configuration


def obtenir_configuration_reference(session: Session) -> ScoringConfig:
    """La référence décrite par le fichier YAML courant, enregistrée si besoin (écriture)."""
    return enregistrer_configuration(session, _contenu_reference())


def _valeur_effective(indicateur: ESGMetric) -> float:
    """La correction de l'Auditeur, quand il y en a une, remplace la valeur extraite — qui reste
    intacte en base pour la traçabilité (docs/WORKFLOWS.md §1.3)."""
    if indicateur.auditor_overridden and indicateur.override_value is not None:
        return indicateur.override_value
    return indicateur.value


def _score_pilier(pilier_config: PilierConfig, valeurs_par_code: dict[str, float]) -> float | None:
    contributions = [
        (
            normaliser(
                valeurs_par_code[code],
                borne_min=config_indicateur.borne_min,
                borne_max=config_indicateur.borne_max,
                plus_haut_est_meilleur=config_indicateur.plus_haut_est_meilleur,
            ),
            config_indicateur.poids,
        )
        for code, config_indicateur in pilier_config.indicateurs.items()
        if code in valeurs_par_code
    ]
    if not contributions:
        return None
    poids_total = sum(poids for _, poids in contributions)
    return sum(sous_note * poids for sous_note, poids in contributions) / poids_total


@dataclass(frozen=True)
class TermeScore:
    """Un indicateur présent dans la forme linéaire du score global : score = Σ poids_effectif ×
    valeur_normalisee. poids_effectif = poids du pilier renormalisé sur les piliers présents ×
    poids de l'indicateur renormalisé sur les indicateurs présents de son pilier ; les poids
    effectifs somment à 1. Base de l'explicabilité exacte (app/explainability/decomposition.py)."""

    pilier: Pillar
    code: str
    valeur: float
    valeur_normalisee: float
    poids_effectif: float


def termes_effectifs(
    schema: ConfigurationScoring, valeurs_par_pilier: dict[Pillar, dict[str, float]]
) -> list[TermeScore]:
    """Même règles que _calculer (indicateur absent retiré, poids renormalisés), jamais une autre
    lecture de la configuration : tests/unit/test_explainability.py vérifie que Σ poids ×
    valeur retombe exactement sur le score global."""
    presents = {
        pilier: {
            code: config_indicateur
            for code, config_indicateur in pilier_config.indicateurs.items()
            if code in valeurs_par_pilier[pilier]
        }
        for pilier, pilier_config in schema.piliers.items()
    }
    poids_piliers = sum(schema.piliers[pilier].poids for pilier, codes in presents.items() if codes)
    termes: list[TermeScore] = []
    for pilier, indicateurs in presents.items():
        if not indicateurs:
            continue
        poids_indicateurs = sum(config.poids for config in indicateurs.values())
        for code, config in indicateurs.items():
            valeur = valeurs_par_pilier[pilier][code]
            termes.append(
                TermeScore(
                    pilier=pilier,
                    code=code,
                    valeur=valeur,
                    valeur_normalisee=normaliser(
                        valeur,
                        borne_min=config.borne_min,
                        borne_max=config.borne_max,
                        plus_haut_est_meilleur=config.plus_haut_est_meilleur,
                    ),
                    poids_effectif=schema.piliers[pilier].poids
                    / poids_piliers
                    * config.poids
                    / poids_indicateurs,
                )
            )
    return termes


def valeurs_des_rapports(
    session: Session, rapport_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[Pillar, dict[str, float]]]:
    """Valeurs effectives (correction de l'Auditeur incluse) de plusieurs rapports, en une
    requête — pour comparer un rapport à ses pairs."""
    valeurs: dict[uuid.UUID, dict[Pillar, dict[str, float]]] = {
        rapport_id: {pilier: {} for pilier in Pillar} for rapport_id in rapport_ids
    }
    if rapport_ids:
        for indicateur in session.exec(
            select(ESGMetric).where(col(ESGMetric.report_id).in_(rapport_ids))
        ).all():
            valeurs[indicateur.report_id][indicateur.pillar][indicateur.metric_code] = (
                _valeur_effective(indicateur)
            )
    return valeurs


def couverture(schema: ConfigurationScoring, codes_par_pilier: dict[Pillar, set[str]]) -> float:
    """Part pondérée des indicateurs de la configuration présents dans le rapport, entre 0 et 1 :
    Σ poids du pilier × Σ poids des indicateurs présents dans ce pilier (les deux niveaux de poids
    somment à 1, config_schema.py l'impose)."""
    return sum(
        pilier_config.poids
        * sum(
            config_indicateur.poids
            for code, config_indicateur in pilier_config.indicateurs.items()
            if code in codes_par_pilier[pilier]
        )
        for pilier, pilier_config in schema.piliers.items()
    )


@dataclass(frozen=True)
class ResultatScore:
    global_score: float
    scores_par_pilier: dict[Pillar, float]
    coverage_rate: float


def _valeurs_du_rapport(session: Session, rapport_id: uuid.UUID) -> dict[Pillar, dict[str, float]]:
    if session.get(ESGReport, rapport_id) is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")
    return valeurs_des_rapports(session, [rapport_id])[rapport_id]


def _calculer(
    schema: ConfigurationScoring, valeurs_par_pilier: dict[Pillar, dict[str, float]]
) -> ResultatScore | None:
    """None si aucun pilier n'est calculable — jamais un score sans substance."""
    scores_par_pilier: dict[Pillar, float] = {}
    for pilier, pilier_config in schema.piliers.items():
        score_pilier = _score_pilier(pilier_config, valeurs_par_pilier[pilier])
        if score_pilier is not None:
            scores_par_pilier[pilier] = score_pilier
    if not scores_par_pilier:
        return None
    poids_total = sum(schema.piliers[pilier].poids for pilier in scores_par_pilier)
    return ResultatScore(
        global_score=sum(
            scores_par_pilier[pilier] * schema.piliers[pilier].poids for pilier in scores_par_pilier
        )
        / poids_total,
        scores_par_pilier=scores_par_pilier,
        coverage_rate=couverture(
            schema, {pilier: set(valeurs) for pilier, valeurs in valeurs_par_pilier.items()}
        ),
    )


def calculer_score(session: Session, rapport_id: uuid.UUID) -> Score:
    """Score officiel d'un rapport, sous la configuration de référence courante. N'appelle jamais
    session.commit() : sous-étape de la transition VALIDATED (app/admin/review_queue.py::
    valider_rapport), qui contrôle la transaction. Dénormalise official_score, coverage_rate et
    config_hash sur le rapport dans la même transaction (docs/ARCHITECTURE.md §3.2)."""
    valeurs = _valeurs_du_rapport(session, rapport_id)
    configuration = obtenir_configuration_reference(session)
    schema = schema_configuration(configuration)
    resultat = _calculer(schema, valeurs)
    if resultat is None:
        raise ValidationError(
            "Aucun indicateur exploitable n'a été trouvé pour ce rapport : impossible de "
            "calculer un score.",
            code="score_incalculable",
        )
    if schema.min_coverage is not None and resultat.coverage_rate < schema.min_coverage:
        raise ValidationError(
            f"Couverture des indicateurs de {resultat.coverage_rate:.0%}, sous le minimum de "
            f"{schema.min_coverage:.0%} exigé par la méthodologie : score non publiable.",
            code="couverture_insuffisante",
        )

    score = Score(
        report_id=rapport_id,
        config_id=configuration.id,
        global_score=resultat.global_score,
        environmental_score=resultat.scores_par_pilier.get(Pillar.ENVIRONNEMENT),
        social_score=resultat.scores_par_pilier.get(Pillar.SOCIAL),
        governance_score=resultat.scores_par_pilier.get(Pillar.GOUVERNANCE),
        coverage_rate=resultat.coverage_rate,
    )
    session.add(score)
    rapport = session.get(ESGReport, rapport_id)
    assert rapport is not None  # vérifié par _valeurs_du_rapport
    rapport.official_score = resultat.global_score
    rapport.coverage_rate = resultat.coverage_rate
    rapport.config_hash = configuration.content_hash
    session.add(rapport)
    return score


@dataclass(frozen=True)
class ApercuScore:
    calculable: bool
    coverage_rate: float | None
    min_coverage: float | None


def apercu_score(session: Session, rapport_id: uuid.UUID) -> ApercuScore:
    """Prévisualise, sans rien écrire, si calculer_score réussirait — même calcul (_calculer),
    jamais dupliqué. Sous la référence décrite par le fichier courant, même si elle n'est pas
    encore enregistrée. Montré à l'Admin AVANT qu'il ne clique Valider."""
    schema = _schema_depuis_contenu(_contenu_reference())
    resultat = _calculer(schema, _valeurs_du_rapport(session, rapport_id))
    if resultat is None:
        return ApercuScore(calculable=False, coverage_rate=None, min_coverage=schema.min_coverage)
    return ApercuScore(
        calculable=schema.min_coverage is None or resultat.coverage_rate >= schema.min_coverage,
        coverage_rate=resultat.coverage_rate,
        min_coverage=schema.min_coverage,
    )


def score_officiel(session: Session, rapport_id: uuid.UUID) -> Score | None:
    """Le score officiel d'un rapport : le plus récent calculé sous une configuration de
    RÉFÉRENCE (jamais une pondération personnalisée). Un changement de méthodologie ne fait donc
    jamais disparaître le score déjà publié d'un rapport — il reste celui que la validation a
    produit, avec la configuration qui l'a produit, tant qu'aucun recalcul délibéré ne le
    remplace."""
    return session.exec(
        select(Score)
        .join(ScoringConfig, col(ScoringConfig.id) == col(Score.config_id))
        .where(col(Score.report_id) == rapport_id, col(ScoringConfig.owner_user_id).is_(None))
        .order_by(col(Score.computed_at).desc())
    ).first()


def score_public(session: Session, rapport_id: uuid.UUID) -> ScoreESGPublic | None:
    """Forme de présentation partagée du score officiel (app/scoring/schemas.py::ScoreESGPublic)
    -- None si le rapport n'a pas encore de score officiel (avant validation), jamais un score
    fabriqué."""
    score = score_officiel(session, rapport_id)
    if score is None:
        return None
    configuration = session.get(ScoringConfig, score.config_id)
    assert configuration is not None  # FK NOT NULL
    return ScoreESGPublic(
        global_score=score.global_score,
        environmental_score=score.environmental_score,
        social_score=score.social_score,
        governance_score=score.governance_score,
        coverage_rate=score.coverage_rate,
        config_version=configuration.version,
    )
