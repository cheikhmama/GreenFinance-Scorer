"""Script ponctuel -- recalcule le score officiel de tous les ESGReport déjà VALIDE après le
passage de config/weights/default.yaml en version 2 (Phase 5 §9, élargissement de la couverture
du scoring, voir le commentaire du fichier YAML pour la justification méthodologique).

Nécessaire car app/scoring/engine.py::obtenir_configuration_reference crée une nouvelle ligne
ConfigurationPonderation dès que schema.version change, mais ne touche JAMAIS les ScoreESG déjà
calculés sous une version antérieure -- sans ce script, score_officiel() redevient None pour tout
rapport validé avant ce déploiement, jusqu'à ce qu'un Admin le recalcule un par un via l'action
existante (app/admin/review_queue.py::recalculer_score), ce qui laisserait un trou de score visible
côté Investisseur/Entreprise/Chercheur en attendant.

Idempotent : un rapport qui a déjà un score sous la configuration de référence courante (déjà
recalculé, ou jamais scoré sous une version différente) est simplement ignoré -- ce script peut
être relancé sans risque de créer un doublon (score_officiel filtre déjà strictement par
configuration_id, voir engine.py).

Usage : uv run python scripts/recalculer_scores_v2.py
"""

from sqlmodel import Session, col, select

import app.main  # noqa: F401  -- enregistre tous les modèles pour SQLAlchemy avant toute requête
from app.core.database import engine
from app.core.enums import ReportStatus
from app.core.exceptions import ValidationError
from app.ingestion.models import ESGReport
from app.scoring.engine import (
    calculer_score,
    obtenir_configuration_reference,
    score_officiel,
)


def main() -> None:
    with Session(engine) as session:
        reference = obtenir_configuration_reference(session)
        print(f"Configuration de référence courante : version {reference.version} (id={reference.id})")

        rapports = session.exec(
            select(ESGReport).where(col(ESGReport.status) == ReportStatus.VALIDATED)
        ).all()
        print(f"{len(rapports)} rapport(s) VALIDE trouvé(s).")

        recalcules = 0
        deja_a_jour = 0
        echecs = 0
        for rapport in rapports:
            if score_officiel(session, rapport.id) is not None:
                deja_a_jour += 1
                continue
            try:
                calculer_score(session, rapport.id)
                session.commit()
                recalcules += 1
                print(f"  recalculé : {rapport.id}")
            except ValidationError as exc:
                # score_incalculable : aucun indicateur du rapport ne recoupe la config v2 --
                # état réel possible (rapport ancien, très peu d'indicateurs), pas une erreur de
                # script. Journalisé, pas fatal pour les rapports suivants.
                session.rollback()
                echecs += 1
                print(f"  ÉCHEC ({exc.code}) : {rapport.id}")

        print(f"\nTerminé : {recalcules} recalculé(s), {deja_a_jour} déjà à jour, {echecs} échec(s).")


if __name__ == "__main__":
    main()
