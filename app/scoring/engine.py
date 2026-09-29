"""Moteur de calcul du score ESG (Phase 5 §9).

Point d'entrée : calculer_score(session, rapport_id). Lit les ESGMetric déjà persistés pour
ce rapport (jamais de saisie manuelle, jamais de valeur recalculée à partir d'une source hors
plateforme — même garantie que app/ingestion/models.py), les regroupe par pilier, normalise
chaque valeur selon la configuration de pondération de référence (app/scoring/config_schema.py,
config/weights/default.yaml) et persiste un ScoreESG.

Donnée manquante (Phase 5 §9, décision explicite) : un indicateur absent pour ce rapport est
retiré du calcul de son pilier, dont le poids se répartit sur les indicateurs réellement
présents — jamais compté comme 0. Un pilier sans aucun indicateur présent reste NULL (voir
app/scoring/models.py::ScoreESG) et est lui-même retiré du calcul du score global, sur le même
principe. Si aucun pilier n'est calculable, calculer_score refuse de créer un score plutôt que
d'en fabriquer un sans substance (code score_incalculable).

Transactions (tâche 1.6) : aucune fonction de ce module n'appelle session.commit() — l'appelant
(la validation, le recalcul) possède la limite de transaction. La configuration de référence
n'est créée que sur un chemin d'écriture (obtenir_configuration_reference, flush + ON CONFLICT) ;
les lectures (score_officiel, score_public, score_calculable) n'écrivent jamais rien.
"""

import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import Pilier
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import ESGMetric, ESGReport
from app.scoring.config_schema import (
    ConfigurationScoring,
    PilierConfig,
    charger_configuration_depuis_fichier,
)
from app.scoring.models import ConfigurationPonderation, ScoreESG
from app.scoring.normalization import normaliser
from app.scoring.schemas import ScoreESGPublic

_NOM_CONFIGURATION_REFERENCE = "Méthodologie de référence GreenFinance Scorer"


@lru_cache
def _charger_configuration_reference_depuis_disque(chemin: str) -> ConfigurationScoring:
    """Le fichier YAML change rarement pendant qu'un process tourne — mis en cache par chemin,
    comme app/ingestion/extractor.py::_get_embed_model met en cache un modèle coûteux à charger."""
    return charger_configuration_depuis_fichier(Path(chemin))


def _schema_reference() -> tuple[str, ConfigurationScoring]:
    chemin = get_settings().default_scoring_config
    return chemin, _charger_configuration_reference_depuis_disque(chemin)


def trouver_configuration_reference(session: Session) -> ConfigurationPonderation | None:
    """Lecture seule : la ligne de référence (utilisateur_id NULL) de la version décrite par le
    fichier YAML courant, ou None si aucun score n'a encore été calculé sous cette version —
    jamais créée ici (une requête GET ne doit rien écrire)."""
    _chemin, schema = _schema_reference()
    return session.exec(
        select(ConfigurationPonderation).where(
            col(ConfigurationPonderation.utilisateur_id).is_(None),
            col(ConfigurationPonderation.version) == schema.version,
        )
    ).first()


def obtenir_configuration_reference(session: Session) -> ConfigurationPonderation:
    """Chemin d'écriture : renvoie la ligne de référence de la version courante, en la créant si
    besoin. N'appelle jamais commit() — seulement un INSERT ... ON CONFLICT DO NOTHING (unicité
    uq_configuration_ponderation_reference_version), qui reste dans la transaction de l'appelant
    et ne crée jamais de doublon, même sous deux validations concurrentes. Point de vérité unique
    côté fichier (get_settings().default_scoring_config) : la ligne n'est qu'un pointeur versionné
    vers lui."""
    existante = trouver_configuration_reference(session)
    if existante is not None:
        return existante

    chemin, schema = _schema_reference()
    session.execute(
        insert(ConfigurationPonderation)
        .values(
            id=uuid.uuid4(),
            nom=_NOM_CONFIGURATION_REFERENCE,
            version=schema.version,
            fichier_yaml=chemin,
            date_creation=utcnow(),
        )
        .on_conflict_do_nothing(
            index_elements=["version"], index_where=text("utilisateur_id IS NULL")
        )
    )
    configuration = trouver_configuration_reference(session)
    assert configuration is not None  # insérée ci-dessus, ou par une transaction concurrente
    return configuration


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


def calculer_score(session: Session, rapport_id: uuid.UUID) -> ScoreESG:
    """N'appelle jamais session.commit() : appelé comme sous-étape de la transition VALIDATED
    (app/admin/review_queue.py::valider_rapport), qui contrôle la limite de la transaction —
    même convention que app/core/notifications.py::notifier."""
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    indicateurs = session.exec(
        select(ESGMetric).where(ESGMetric.report_id == rapport_id)
    ).all()
    valeurs_par_pilier: dict[Pilier, dict[str, float]] = {pilier: {} for pilier in Pilier}
    for indicateur in indicateurs:
        valeurs_par_pilier[indicateur.pillar][indicateur.metric_code] = _valeur_effective(indicateur)

    _chemin, schema = _schema_reference()

    scores_par_pilier: dict[Pilier, float] = {}
    for pilier, pilier_config in schema.piliers.items():
        score_pilier = _score_pilier(pilier_config, valeurs_par_pilier[pilier])
        if score_pilier is not None:
            scores_par_pilier[pilier] = score_pilier

    if not scores_par_pilier:
        raise ValidationError(
            "Aucun indicateur exploitable n'a été trouvé pour ce rapport : impossible de "
            "calculer un score.",
            code="score_incalculable",
        )

    poids_total = sum(schema.piliers[pilier].poids for pilier in scores_par_pilier)
    valeur_globale = (
        sum(scores_par_pilier[pilier] * schema.piliers[pilier].poids for pilier in scores_par_pilier)
        / poids_total
    )

    # Seulement une fois le score calculable : un échec ne tente même pas l'insertion.
    configuration = obtenir_configuration_reference(session)
    score_esg = ScoreESG(
        rapport_id=rapport_id,
        configuration_id=configuration.id,
        valeur_globale=valeur_globale,
        score_environnement=scores_par_pilier.get(Pilier.ENVIRONNEMENT),
        score_social=scores_par_pilier.get(Pilier.SOCIAL),
        score_gouvernance=scores_par_pilier.get(Pilier.GOUVERNANCE),
    )
    session.add(score_esg)
    # Toujours calculé sous la configuration de référence : c'est le score officiel, dénormalisé
    # sur le rapport dans la même transaction (docs/ARCHITECTURE.md §3.2).
    rapport.official_score = valeur_globale
    session.add(rapport)
    return score_esg


def score_calculable(session: Session, rapport_id: uuid.UUID) -> bool:
    """Prévisualise si calculer_score réussirait pour ce rapport, sans rien persister — même
    logique que _score_pilier (un pilier est calculable dès qu'au moins un de ses indicateurs
    cibles y est présent), jamais dupliquée. Utilisé pour avertir l'Admin AVANT qu'il ne clique
    Valider, plutôt que de le laisser découvrir score_incalculable après coup (voir
    app/admin/review_queue.py::valider_rapport)."""
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    codes_par_pilier: dict[Pilier, set[str]] = {pilier: set() for pilier in Pilier}
    for pilier, code in session.exec(
        select(ESGMetric.pillar, ESGMetric.metric_code).where(
            ESGMetric.report_id == rapport_id
        )
    ).all():
        codes_par_pilier[Pilier(pilier)].add(code)

    _chemin, schema = _schema_reference()
    return any(
        codes_par_pilier[pilier] & set(pilier_config.indicateurs)
        for pilier, pilier_config in schema.piliers.items()
    )


def score_officiel(session: Session, rapport_id: uuid.UUID) -> ScoreESG | None:
    """Le ScoreESG publié/officiel d'un rapport — jamais un simple `WHERE rapport_id = X` non
    ordonné : un même rapport peut porter plusieurs scores (un par ConfigurationPonderation, voir
    uq_score_esg_rapport_configuration), et seul celui calculé sous la configuration de référence
    (jamais une pondération personnalisée) fait foi. Réutilisé pour le score public affiché à
    l'Investisseur (app/investor/entreprises.py::score_public) et pour figer la version exacte
    utilisée par une Analyse Chercheur (app/researcher/analyses.py)."""
    configuration = trouver_configuration_reference(session)
    if configuration is None:
        return None
    return session.exec(
        select(ScoreESG).where(
            col(ScoreESG.rapport_id) == rapport_id,
            col(ScoreESG.configuration_id) == configuration.id,
        )
    ).first()


def score_public(session: Session, rapport_id: uuid.UUID) -> ScoreESGPublic | None:
    """Forme de présentation partagée du score officiel (app/scoring/schemas.py::ScoreESGPublic)
    -- None si le rapport n'a pas encore de score officiel (avant validation Auditeur/Admin),
    jamais un score fabriqué. Point de vérité unique pour tout module qui doit afficher le score
    officiel à un utilisateur, pour ne jamais dupliquer la jointure vers ConfigurationPonderation
    (voir app/investor/entreprises.py::score_public, forme historique antérieure et distincte,
    conservée pour ne pas casser le contrat existant côté Investisseur)."""
    score = score_officiel(session, rapport_id)
    if score is None:
        return None
    configuration = session.get(ConfigurationPonderation, score.configuration_id)
    assert configuration is not None  # FK NOT NULL -- une ligne orpheline serait un bug ailleurs
    return ScoreESGPublic(
        valeur_globale=score.valeur_globale,
        score_environnement=score.score_environnement,
        score_social=score.score_social,
        score_gouvernance=score.score_gouvernance,
        configuration_version=configuration.version,
    )
