import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.auth.models import User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import Currency, DurationType, Role
from app.investor.models import Portfolio, PortfolioPosition


def _investisseur(session) -> User:
    utilisateur = User(
        email=f"investisseur-{uuid.uuid4()}@example.com",
        password_hash="hash",
        role=Role.INVESTOR,
    )
    session.add(utilisateur)
    session.flush()
    return utilisateur


def _entreprise(session, **kwargs) -> Company:
    # SQLModel ignore silencieusement un kwarg inconnu : jamais un champ de test perdu en route.
    assert set(kwargs) <= set(Company.model_fields), set(kwargs) - set(Company.model_fields)
    entreprise = Company(name="Acme", sector="Industrie", country="MR", **kwargs)
    session.add(entreprise)
    session.flush()
    return entreprise


def _portefeuille(session, investisseur_id: uuid.UUID) -> Portfolio:
    portefeuille = Portfolio(
        user_id=investisseur_id, name="Portefeuille vert", reference_currency=Currency.USD
    )
    session.add(portefeuille)
    session.flush()
    return portefeuille


def _base_position(portefeuille_id: uuid.UUID, entreprise_id: uuid.UUID, **kwargs) -> dict:
    defaults = {
        "portfolio_id": portefeuille_id,
        "company_id": entreprise_id,
        "outstanding_amount": 1000.0,
        "currency": Currency.USD,
        "converted_amount": 1000.0,
        "duration_type": DurationType.OUVERTE,
        "start_date": utcnow(),
    }
    defaults.update(kwargs)
    # model_validate ignore silencieusement une clé inconnue : jamais un champ de test perdu.
    assert set(defaults) <= set(PortfolioPosition.model_fields), set(defaults) - set(
        PortfolioPosition.model_fields
    )
    return defaults


def test_position_sous_le_minimum_requis_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session, minimum_investment_amount=5000.0)
    portefeuille = _portefeuille(session, investisseur.id)

    data = _base_position(portefeuille.id, entreprise.id, outstanding_amount=100.0)

    with pytest.raises(ValidationError):
        PortfolioPosition.model_validate(data, context={"entreprise": entreprise})


def test_position_fixe_date_fin_plus_dun_an_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow() + timedelta(days=1)

    data = _base_position(
        portefeuille.id,
        entreprise.id,
        duration_type=DurationType.FIXE,
        start_date=debut,
        end_date=debut + timedelta(days=400),
    )

    with pytest.raises(ValidationError):
        PortfolioPosition.model_validate(data)


def test_position_fixe_date_debut_dans_le_passe_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow() - timedelta(days=5)

    data = _base_position(
        portefeuille.id,
        entreprise.id,
        duration_type=DurationType.FIXE,
        start_date=debut,
        end_date=debut + timedelta(days=30),
    )

    with pytest.raises(ValidationError):
        PortfolioPosition.model_validate(data)


def test_position_fixe_valide_est_acceptee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow() + timedelta(days=1)

    data = _base_position(
        portefeuille.id,
        entreprise.id,
        duration_type=DurationType.FIXE,
        start_date=debut,
        end_date=debut + timedelta(days=180),
    )

    position = PortfolioPosition.model_validate(data)
    session.add(position)
    session.flush()

    assert position.id is not None


def test_position_ouverte_sans_date_fin_puis_fermeture(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow()

    data = _base_position(portefeuille.id, entreprise.id, start_date=debut)
    position = PortfolioPosition.model_validate(data)
    session.add(position)
    session.flush()

    assert position.end_date is None

    position.end_date = debut + timedelta(days=30)
    session.flush()

    assert position.end_date is not None


def test_position_ouverte_fermeture_avec_date_fin_anterieure_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow()

    data = _base_position(portefeuille.id, entreprise.id, start_date=debut)
    position = PortfolioPosition.model_validate(data)
    session.add(position)
    session.flush()

    with pytest.raises(ValidationError):
        position.end_date = debut - timedelta(days=1)


def test_taux_change_fige_independant_entre_positions(session) -> None:
    """Deux positions créées le même jour, même devise, taux différents
    (simule une fluctuation intra-journalière) : chacune conserve son
    propre taux, aucun recalcul rétroactif de l'une sur l'autre."""
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow()

    position_matin = PortfolioPosition.model_validate(
        _base_position(
            portefeuille.id,
            entreprise.id,
            start_date=debut,
            fx_rate_used=Decimal("36.5"),
            converted_amount=Decimal(36500),
        )
    )
    position_soir = PortfolioPosition.model_validate(
        _base_position(
            portefeuille.id,
            entreprise.id,
            start_date=debut,
            fx_rate_used=Decimal("36.8"),
            converted_amount=Decimal(36800),
        )
    )
    session.add(position_matin)
    session.add(position_soir)
    session.flush()
    session.refresh(position_matin)
    session.refresh(position_soir)

    # Relus depuis la base (numeric) : Decimal exact, jamais 36.799999…
    assert position_matin.fx_rate_used == Decimal("36.5")
    assert position_soir.fx_rate_used == Decimal("36.8")
    assert position_matin.fx_rate_used != position_soir.fx_rate_used


def test_suppression_entreprise_referencee_par_position_echoue(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)

    position = PortfolioPosition.model_validate(
        _base_position(portefeuille.id, entreprise.id)
    )
    session.add(position)
    session.flush()

    session.delete(entreprise)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
