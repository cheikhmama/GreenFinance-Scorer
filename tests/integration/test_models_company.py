import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.company.models import Company


def test_creation_sans_montant_minimum_et_sans_compte(session) -> None:
    entreprise = Company(name="Acme", sector="Industrie", country="MR")
    session.add(entreprise)
    session.flush()

    assert entreprise.id is not None
    assert entreprise.minimum_investment_amount is None
    assert entreprise.owner_user_id is None


def test_creation_avec_montant_minimum(session) -> None:
    entreprise = Company(
        name="Acme Green",
        sector="Energie",
        country="MR",
        minimum_investment_amount=1000.0,
    )
    session.add(entreprise)
    session.flush()

    assert entreprise.minimum_investment_amount == 1000.0


def test_montant_minimum_nul_distinct_de_zero(session) -> None:
    sans_minimum = Company(name="SansMin", sector="X", country="MR")
    avec_minimum_zero = Company(
        name="MinZero", sector="X", country="MR", minimum_investment_amount=0.0
    )
    session.add(sans_minimum)
    session.add(avec_minimum_zero)
    session.flush()

    assert sans_minimum.minimum_investment_amount is None
    assert avec_minimum_zero.minimum_investment_amount == 0.0
    assert (
        sans_minimum.minimum_investment_amount
        != avec_minimum_zero.minimum_investment_amount
    )


def test_utilisateur_id_inexistant_rejete(session) -> None:
    entreprise = Company(
        name="Fantome", sector="X", country="MR", owner_user_id=uuid.uuid4()
    )
    session.add(entreprise)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
