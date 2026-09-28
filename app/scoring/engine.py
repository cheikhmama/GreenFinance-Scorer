"""Moteur de calcul du score ESG (Phase 5 §9).

Point d'entrée : calculer_score(session, rapport_id). Lit les IndicateurESG déjà persistés pour
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
"""

import uuid
from functools import lru_cache
from pathlib import Path

from sqlmodel import Session, col, select

from app.core.config import get_settings
from app.core.enums import Pilier
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import IndicateurESG, RapportESG
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


def obtenir_configuration_reference(session: Session) -> ConfigurationPonderation:
    """Renvoie la configuration de référence (utilisateur_id NULL) la plus récente, ou la crée
    si aucune n'existe encore — point de vérité unique côté fichier (get_settings().default_
    scoring_config), la ligne en base n'est qu'un pointeur versionné vers lui."""
    chemin = get_settings().default_scoring_config
    schema = _charger_configuration_reference_depuis_disque(chemin)

    existante = session.exec(
        select(ConfigurationPonderation)
        .where(col(ConfigurationPonderation.utilisateur_id).is_(None))
        .order_by(col(ConfigurationPonderation.version).desc())
    ).first()
    if existante is not None and existante.version == schema.version:
        return existante

    configuration = ConfigurationPonderation(
        nom=_NOM_CONFIGURATION_REFERENCE, version=schema.version, fichier_yaml=chemin
    )
    session.add(configuration)
    session.commit()
    session.refresh(configuration)
    return configuration


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
    """N'appelle jamais session.commit() : appelé comme sous-étape de la transition VALIDE
    (app/admin/review_queue.py::valider_rapport), qui contrôle la limite de la transaction —
    même convention que app/core/notifications.py::notifier."""
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    indicateurs = session.exec(
        select(IndicateurESG).where(IndicateurESG.rapport_id == rapport_id)
    ).all()
    valeurs_par_pilier: dict[Pilier, dict[str, float]] = {pilier: {} for pilier in Pilier}
    for indicateur in indicateurs:
        valeurs_par_pilier[indicateur.pilier][indicateur.code] = indicateur.valeur

    configuration = obtenir_configuration_reference(session)
    schema = _charger_configuration_reference_depuis_disque(configuration.fichier_yaml)

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

    score_esg = ScoreESG(
        rapport_id=rapport_id,
        configuration_id=configuration.id,
        valeur_globale=valeur_globale,
        score_environnement=scores_par_pilier.get(Pilier.ENVIRONNEMENT),
        score_social=scores_par_pilier.get(Pilier.SOCIAL),
        score_gouvernance=scores_par_pilier.get(Pilier.GOUVERNANCE),
    )
    session.add(score_esg)
    return score_esg


def score_calculable(session: Session, rapport_id: uuid.UUID) -> bool:
    """Prévisualise si calculer_score réussirait pour ce rapport, sans rien persister — même
    logique que _score_pilier (un pilier est calculable dès qu'au moins un de ses indicateurs
    cibles y est présent), jamais dupliquée. Utilisé pour avertir l'Admin AVANT qu'il ne clique
    Valider, plutôt que de le laisser découvrir score_incalculable après coup (voir
    app/admin/review_queue.py::valider_rapport)."""
    rapport = session.get(RapportESG, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    codes_par_pilier: dict[Pilier, set[str]] = {pilier: set() for pilier in Pilier}
    for pilier, code in session.exec(
        select(IndicateurESG.pilier, IndicateurESG.code).where(
            IndicateurESG.rapport_id == rapport_id
        )
    ).all():
        codes_par_pilier[Pilier(pilier)].add(code)

    configuration = obtenir_configuration_reference(session)
    schema = _charger_configuration_reference_depuis_disque(configuration.fichier_yaml)
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
    configuration = obtenir_configuration_reference(session)
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
