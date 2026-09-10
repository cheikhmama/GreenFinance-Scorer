import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.company.models import Entreprise
from app.core.enums import CanalDepot, MethodeDonnee, Pilier, StatutRapport, TypeRapport
from app.ingestion.models import (
    DonneeCarbone,
    IndicateurESG,
    PreuveDocumentaire,
    RapportESG,
)


def _entreprise(session, **kwargs) -> Entreprise:
    entreprise = Entreprise(nom="Acme", secteur="Industrie", pays="MR", **kwargs)
    session.add(entreprise)
    session.flush()
    return entreprise


def _rapport(entreprise_id: uuid.UUID, **kwargs) -> RapportESG:
    defaults = {
        "entreprise_id": entreprise_id,
        "type": TypeRapport.RAPPORT_ESG,
        "canal": CanalDepot.AUTOMATIQUE,
        "fichier_source": "s3://bucket/rapport.pdf",
    }
    defaults.update(kwargs)
    return RapportESG(**defaults)


def test_creation_rapport_lie_a_entreprise_statut_par_defaut(session) -> None:
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()

    assert rapport.id is not None
    assert rapport.statut == StatutRapport.ENVOYE
    assert rapport.auditeur_id is None


def test_entreprise_id_obligatoire(session) -> None:
    # SQLModel (table=True) ne valide pas les champs requis à la
    # construction : la contrainte NOT NULL s'applique au flush, côté base.
    rapport = RapportESG(
        entreprise_id=None,  # type: ignore[arg-type]
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.AUTOMATIQUE,
        fichier_source="x",
    )
    session.add(rapport)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_entreprise_id_inexistant_rejete(session) -> None:
    rapport = _rapport(uuid.uuid4())
    session.add(rapport)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize("statut", list(StatutRapport))
def test_sept_statuts_tous_atteignables(session, statut: StatutRapport) -> None:
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id, statut=statut)
    session.add(rapport)
    session.flush()

    assert rapport.statut == statut


def _preuve(session) -> PreuveDocumentaire:
    preuve = PreuveDocumentaire(
        nom_document="rapport-annuel-2025.pdf",
        annee=2025,
        nombre_pages_total=120,
        page_debut=42,
        page_fin=44,
        pdf_extrait_genere="s3://bucket/extraits/42-44.pdf",
    )
    session.add(preuve)
    session.flush()
    return preuve


def test_indicateur_et_donnee_carbone_lies_au_meme_rapport(session) -> None:
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)

    indicateur = IndicateurESG(
        rapport_id=rapport.id,
        pilier=Pilier.ENVIRONNEMENT,
        code="GHG-SCOPE1",
        valeur=123.4,
        unite="tCO2e",
        methode=MethodeDonnee.RAPPORTEE,
        preuve_id=preuve.id,
    )
    donnee_carbone = DonneeCarbone(
        rapport_id=rapport.id,
        scope=1,
        valeur_tonnes_co2e=123.4,
        annee=2025,
        methode=MethodeDonnee.RAPPORTEE,
        score_qualite_pcaf=3,
        preuve_id=preuve.id,
    )
    session.add(indicateur)
    session.add(donnee_carbone)
    session.flush()

    assert indicateur.rapport_id == donnee_carbone.rapport_id == rapport.id
    assert indicateur.rapport.id == rapport.id
    assert donnee_carbone.rapport.id == rapport.id
    assert indicateur in rapport.indicateurs
    assert donnee_carbone in rapport.donnees_carbone
    assert indicateur in preuve.indicateurs
    assert donnee_carbone in preuve.donnees_carbone


@pytest.mark.parametrize("score_invalide", [0, 6, -1])
def test_score_qualite_pcaf_hors_bornes_rejete(session, score_invalide: int) -> None:
    # Note : SQLModel (table=True) ne déclenche PAS la validation Pydantic
    # (ge/le, validators) sur une construction directe Model(**kwargs) — il
    # faut passer par .model_validate() pour l'exercer réellement.
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)

    with pytest.raises(ValidationError):
        DonneeCarbone.model_validate(
            {
                "rapport_id": rapport.id,
                "scope": 1,
                "valeur_tonnes_co2e": 1.0,
                "annee": 2025,
                "methode": MethodeDonnee.RAPPORTEE,
                "score_qualite_pcaf": score_invalide,
                "preuve_id": preuve.id,
            }
        )


@pytest.mark.parametrize("scope_invalide", [0, 4, -1])
def test_scope_hors_bornes_rejete_en_base(session, scope_invalide: int) -> None:
    """Complète test_score_qualite_pcaf_hors_bornes_rejete : ici la construction passe par
    DonneeCarbone(**kwargs) directe (comme le fait le code applicatif réel, ex.
    app/ingestion/extractor.py), qui ne déclenche jamais la validation Pydantic — seule la
    contrainte CHECK côté PostgreSQL (Phase 5 §6) protège ce chemin."""
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)

    session.add(
        DonneeCarbone(
            rapport_id=rapport.id,
            scope=scope_invalide,
            valeur_tonnes_co2e=1.0,
            annee=2025,
            methode=MethodeDonnee.RAPPORTEE,
            score_qualite_pcaf=3,
            preuve_id=preuve.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_valeur_tonnes_co2e_negative_rejetee_en_base(session) -> None:
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)

    session.add(
        DonneeCarbone(
            rapport_id=rapport.id,
            scope=1,
            valeur_tonnes_co2e=-0.01,
            annee=2025,
            methode=MethodeDonnee.RAPPORTEE,
            score_qualite_pcaf=3,
            preuve_id=preuve.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize("pcaf_invalide", [0, 6])
def test_score_qualite_pcaf_hors_bornes_rejete_en_base(session, pcaf_invalide: int) -> None:
    """Pendant DB de test_score_qualite_pcaf_hors_bornes_rejete (validation Pydantic) : ici
    construction directe, seule la contrainte CHECK protège."""
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)

    session.add(
        DonneeCarbone(
            rapport_id=rapport.id,
            scope=1,
            valeur_tonnes_co2e=1.0,
            annee=2025,
            methode=MethodeDonnee.RAPPORTEE,
            score_qualite_pcaf=pcaf_invalide,
            preuve_id=preuve.id,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_doublon_checksum_meme_entreprise_rejete_en_base(session) -> None:
    """Anti-doublon applicatif (app/company/rapports.py::_verifier_doublon) complété par une
    contrainte UNIQUE (Phase 5 §6) : un SELECT-puis-INSERT sans verrou laisse une fenêtre de
    course entre deux dépôts concurrents du même fichier, que seule la base peut fermer."""
    entreprise = _entreprise(session)
    session.add(_rapport(entreprise.id, checksum_sha256="a" * 64))
    session.flush()

    session.add(_rapport(entreprise.id, checksum_sha256="a" * 64))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_checksum_nul_plusieurs_fois_autorise_meme_entreprise(session) -> None:
    """Les rapports déposés avant l'introduction du checksum ont checksum_sha256=NULL —
    PostgreSQL ne compare jamais deux NULL comme égaux dans une contrainte UNIQUE, donc
    plusieurs rapports sans checksum pour la même entreprise restent valides."""
    entreprise = _entreprise(session)
    session.add(_rapport(entreprise.id, checksum_sha256=None))
    session.add(_rapport(entreprise.id, checksum_sha256=None))
    session.flush()


def test_suppression_rapport_reference_echoue_proprement(session) -> None:
    """Comportement documenté : rapport_id (IndicateurESG, DonneeCarbone) ne
    porte pas de cascade de suppression. Supprimer un RapportESG encore
    référencé échoue avec une IntegrityError — jamais de suppression
    silencieuse des indicateurs/données carbone associés."""
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)
    session.add(
        IndicateurESG(
            rapport_id=rapport.id,
            pilier=Pilier.SOCIAL,
            code="EMP-01",
            valeur=1.0,
            unite="ratio",
            methode=MethodeDonnee.RAPPORTEE,
            preuve_id=preuve.id,
        )
    )
    session.flush()

    session.delete(rapport)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
