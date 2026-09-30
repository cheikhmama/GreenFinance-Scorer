"""Recherche « contient » : `%` et `_` saisis sont des caractères, jamais des jokers (tâche 4.3)."""

import uuid

import pytest

from app.core.enums import Role
from app.core.recherche import motif_contient
from tests.integration.test_investor_router import (
    _create_utilisateur,
    _entreprise_publiee,
    _login,
)


@pytest.mark.parametrize(
    ("saisie", "attendu"),
    [
        ("acme", "%acme%"),
        ("50%", "%50\\%%"),
        ("a_b", "%a\\_b%"),
        ("c:\\temp", "%c:\\\\temp%"),
    ],
)
def test_motif_echappe(saisie: str, attendu: str) -> None:
    assert motif_contient(saisie) == attendu


def test_joker_saisi_ne_renvoie_que_les_correspondances_litterales(session) -> None:
    marqueur = uuid.uuid4().hex[:8]
    litterale = _entreprise_publiee(session)
    litterale.name = f"Remise 100% {marqueur}_x"
    autre = _entreprise_publiee(session)
    autre.name = f"Remise 1000 {marqueur}ax"
    session.add_all([litterale, autre])
    session.commit()
    investisseur = _login(_create_utilisateur(session, Role.INVESTOR).email)

    def noms(recherche: str) -> set[str]:
        reponse = investisseur.get("/api/v1/investor/entreprises", params={"recherche": recherche})
        assert reponse.status_code == 200
        return {e["name"] for e in reponse.json()["items"]}

    # Sans échappement, « 100% » aurait aussi trouvé « 1000… » et « _x » aurait trouvé « ax ».
    assert noms(f"100% {marqueur}") == {litterale.name}
    assert noms(f"{marqueur}_x") == {litterale.name}
    assert noms(marqueur) == {litterale.name, autre.name}
