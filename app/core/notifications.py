"""Création et consultation des notifications transverses (app/core/models.py::Notification).

Petit utilitaire partagé plutôt que dupliqué dans chaque module métier qui déclenche une
notification (Étape 10/11 : affectation, décision d'audit, publication). Écriture (notifier) et
lecture (lister_mes_notifications, marquer_lue) vivent dans le même fichier : Notification n'a
pas d'espace acteur propre, ce sont les deux faces de la même entité transverse (Phase 5 §10).
"""

import uuid

from sqlmodel import Session, col, func, select

from app.core.exceptions import NotFoundError
from app.core.models import Notification


def notifier(session: Session, utilisateur_id: uuid.UUID, type_: str, message: str) -> Notification:
    """Construit et ajoute une Notification à la session — ne commit jamais : l'appelant
    contrôle la limite de la transaction (même convention que le reste du projet)."""
    notification = Notification(utilisateur_id=utilisateur_id, type=type_, message=message)
    session.add(notification)
    return notification


def lister_mes_notifications(
    session: Session,
    utilisateur_id: uuid.UUID,
    *,
    non_lues_seulement: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notification], int]:
    """Page des notifications d'un utilisateur, plus récentes d'abord — jamais celles d'un
    autre : le filtre sur utilisateur_id n'est pas optionnel, contrairement aux listes
    Administrateur qui parcourent tout le monde."""
    filtres = [col(Notification.utilisateur_id) == utilisateur_id]
    if non_lues_seulement:
        filtres.append(col(Notification.lu).is_(False))

    total = session.exec(select(func.count()).select_from(Notification).where(*filtres)).one()
    items = list(
        session.exec(
            select(Notification)
            .where(*filtres)
            .order_by(col(Notification.date_envoi).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def marquer_lue(session: Session, utilisateur_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    """Idempotent : marquer une notification déjà lue comme lue n'est pas une erreur. Même code
    d'erreur que la notification n'existe pas ou appartienne à un autre utilisateur — jamais de
    403 ici, pour ne pas confirmer l'existence d'un notification_id d'autrui (même principe que
    app/company/router.py::consulter_rapport)."""
    notification = session.get(Notification, notification_id)
    if notification is None or notification.utilisateur_id != utilisateur_id:
        raise NotFoundError("Notification introuvable.", code="notification_introuvable")

    notification.lu = True
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification
