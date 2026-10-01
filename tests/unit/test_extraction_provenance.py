"""Version du prompt d'extraction (tâche 5.5) : toute modification du gabarit ou de l'outil déclaré
doit changer PROMPT_VERSION, sinon les exécutions enregistrées mentiraient sur ce qui a produit les
valeurs."""

from app.ingestion.extractor import PROMPT_VERSION, construire_prompt, empreinte_prompt

# Empreinte figée pour chaque version publiée. Après une modification volontaire du prompt :
# monter PROMPT_VERSION dans app/ingestion/extractor.py et ajouter sa nouvelle empreinte ici.
EMPREINTES = {
    "2026-10-01": "ee3639e93991a196f3e2f6f35ae29c438fb1f9d9b94c1135a6a4781d8d21d80d",
}


def test_le_prompt_n_a_pas_change_sans_nouvelle_version() -> None:
    assert PROMPT_VERSION in EMPREINTES, "nouvelle version : ajouter son empreinte ici"
    assert empreinte_prompt() == EMPREINTES[PROMPT_VERSION], (
        "le prompt ou l'outil d'extraction a changé : monter PROMPT_VERSION"
    )


def test_le_prompt_porte_les_parties_variables() -> None:
    prompt = construire_prompt(nom_entreprise="Atlas", context="--- Page 3 ---\nScope 1", codes=["scope_1"])

    assert "(Atlas)" in prompt
    assert '["scope_1"]' in prompt
    assert prompt.rstrip().endswith("Scope 1")
