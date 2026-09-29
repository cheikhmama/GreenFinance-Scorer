import uuid
from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.auth.models import Utilisateur
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import DevisePosition, Role, TypeDureeInvestissement
from app.investor.models import Portefeuille, PositionPortefeuille


def _investisseur(session) -> Utilisateur:
    utilisateur = Utilisateur(
        email=f"investisseur-{uuid.uuid4()}@example.com",
        mot_de_passe_hache="hash",
        role=Role.INVESTISSEUR,
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


def _portefeuille(session, investisseur_id: uuid.UUID) -> Portefeuille:
    portefeuille = Portefeuille(
        investisseur_id=investisseur_id, nom="Portefeuille vert", devise_reference=DevisePosition.USD
    )
    session.add(portefeuille)
    session.flush()
    return portefeuille


def _base_position(portefeuille_id: uuid.UUID, entreprise_id: uuid.UUID, **kwargs) -> dict:
    defaults = {
        "portefeuille_id": portefeuille_id,
        "entreprise_id": entreprise_id,
        "montant_investi": 1000.0,
        "devise": DevisePosition.USD,
        "montant_converti": 1000.0,
        "type_duree": TypeDureeInvestissement.OUVERTE,
        "date_debut": utcnow(),
    }
    defaults.update(kwargs)
    return defaults


def test_position_sous_le_minimum_requis_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session, minimum_investment_amount=5000.0)
    portefeuille = _portefeuille(session, investisseur.id)

    data = _base_position(portefeuille.id, entreprise.id, montant_investi=100.0)

    with pytest.raises(ValidationError):
        PositionPortefeuille.model_validate(data, context={"entreprise": entreprise})


def test_position_fixe_date_fin_plus_dun_an_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow() + timedelta(days=1)

    data = _base_position(
        portefeuille.id,
        entreprise.id,
        type_duree=TypeDureeInvestissement.FIXE,
        date_debut=debut,
        date_fin=debut + timedelta(days=400),
    )

    with pytest.raises(ValidationError):
        PositionPortefeuille.model_validate(data)


def test_position_fixe_date_debut_dans_le_passe_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow() - timedelta(days=5)

    data = _base_position(
        portefeuille.id,
        entreprise.id,
        type_duree=TypeDureeInvestissement.FIXE,
        date_debut=debut,
        date_fin=debut + timedelta(days=30),
    )

    with pytest.raises(ValidationError):
        PositionPortefeuille.model_validate(data)


def test_position_fixe_valide_est_acceptee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow() + timedelta(days=1)

    data = _base_position(
        portefeuille.id,
        entreprise.id,
        type_duree=TypeDureeInvestissement.FIXE,
        date_debut=debut,
        date_fin=debut + timedelta(days=180),
    )

    position = PositionPortefeuille.model_validate(data)
    session.add(position)
    session.flush()

    assert position.id is not None


def test_position_ouverte_sans_date_fin_puis_fermeture(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow()

    data = _base_position(portefeuille.id, entreprise.id, date_debut=debut)
    position = PositionPortefeuille.model_validate(data)
    session.add(position)
    session.flush()

    assert position.date_fin is None

    position.date_fin = debut + timedelta(days=30)
    session.flush()

    assert position.date_fin is not None


def test_position_ouverte_fermeture_avec_date_fin_anterieure_rejetee(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow()

    data = _base_position(portefeuille.id, entreprise.id, date_debut=debut)
    position = PositionPortefeuille.model_validate(data)
    session.add(position)
    session.flush()

    with pytest.raises(ValidationError):
        position.date_fin = debut - timedelta(days=1)


def test_taux_change_fige_independant_entre_positions(session) -> None:
    """Deux positions créées le même jour, même devise, taux différents
    (simule une fluctuation intra-journalière) : chacune conserve son
    propre taux, aucun recalcul rétroactif de l'une sur l'autre."""
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)
    debut = utcnow()

    position_matin = PositionPortefeuille.model_validate(
        _base_position(
            portefeuille.id,
            entreprise.id,
            date_debut=debut,
            taux_change_utilise=36.5,
            montant_converti=36500.0,
        )
    )
    position_soir = PositionPortefeuille.model_validate(
        _base_position(
            portefeuille.id,
            entreprise.id,
            date_debut=debut,
            taux_change_utilise=36.8,
            montant_converti=36800.0,
        )
    )
    session.add(position_matin)
    session.add(position_soir)
    session.flush()

    assert position_matin.taux_change_utilise == 36.5
    assert position_soir.taux_change_utilise == 36.8
    assert position_matin.taux_change_utilise != position_soir.taux_change_utilise


def test_suppression_entreprise_referencee_par_position_echoue(session) -> None:
    investisseur = _investisseur(session)
    entreprise = _entreprise(session)
    portefeuille = _portefeuille(session, investisseur.id)

    position = PositionPortefeuille.model_validate(
        _base_position(portefeuille.id, entreprise.id)
    )
    session.add(position)
    session.flush()

    session.delete(entreprise)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
