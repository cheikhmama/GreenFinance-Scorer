import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.company.models import Entreprise


def test_creation_sans_montant_minimum_et_sans_compte(session) -> None:
    entreprise = Entreprise(nom="Acme", secteur="Industrie", pays="MR")
    session.add(entreprise)
    session.flush()

    assert entreprise.id is not None
    assert entreprise.montant_minimum_investissement is None
    assert entreprise.utilisateur_id is None


def test_creation_avec_montant_minimum(session) -> None:
    entreprise = Entreprise(
        nom="Acme Green",
        secteur="Energie",
        pays="MR",
        montant_minimum_investissement=1000.0,
    )
    session.add(entreprise)
    session.flush()

    assert entreprise.montant_minimum_investissement == 1000.0


def test_montant_minimum_nul_distinct_de_zero(session) -> None:
    sans_minimum = Entreprise(nom="SansMin", secteur="X", pays="MR")
    avec_minimum_zero = Entreprise(
        nom="MinZero", secteur="X", pays="MR", montant_minimum_investissement=0.0
    )
    session.add(sans_minimum)
    session.add(avec_minimum_zero)
    session.flush()

    assert sans_minimum.montant_minimum_investissement is None
    assert avec_minimum_zero.montant_minimum_investissement == 0.0
    assert (
        sans_minimum.montant_minimum_investissement
        != avec_minimum_zero.montant_minimum_investissement
    )


def test_utilisateur_id_inexistant_rejete(session) -> None:
    entreprise = Entreprise(
        nom="Fantome", secteur="X", pays="MR", utilisateur_id=uuid.uuid4()
    )
    session.add(entreprise)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
