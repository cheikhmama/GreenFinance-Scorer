"""Modification par l'Entreprise de sa propre fiche (description, site officiel, montant minimum
d'investissement) — tâche post-Phase-0 : cette modification appartenait jusqu'ici à l'Administrateur
seul (app/admin/review_queue.py::modifier_entreprise_admin) ; nom, secteur et pays y restent, seuls
ces trois champs basculent ici. L'Administrateur conserve une consultation en lecture seule depuis
la fiche Admin."""

import uuid
from decimal import Decimal

import structlog
from sqlmodel import Session

from app.company.models import Company
from app.core.enums import Currency
from app.core.exceptions import NotFoundError

logger = structlog.get_logger(__name__)


def modifier_profil_entreprise(
    session: Session,
    entreprise_id: uuid.UUID,
    *,
    description: str | None,
    website: str | None,
    minimum_investment_amount: Decimal | None,
    minimum_investment_currency: Currency | None,
) -> Company:
    entreprise = session.get(Company, entreprise_id)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")

    entreprise.description = description
    entreprise.website = website
    entreprise.minimum_investment_amount = minimum_investment_amount
    entreprise.minimum_investment_currency = minimum_investment_currency
    session.add(entreprise)
    session.commit()
    session.refresh(entreprise)
    logger.info("entreprise_profil_modifie", entreprise_id=str(entreprise_id))
    return entreprise
