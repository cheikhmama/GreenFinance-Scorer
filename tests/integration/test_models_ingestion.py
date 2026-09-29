import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    ExtractionStatus,
    MethodeDonnee,
    Pilier,
    ReportStatus,
    TypeRapport,
)
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
)


def _entreprise(session, **kwargs) -> Company:
    # SQLModel ignore silencieusement un kwarg inconnu : jamais un champ de test perdu en route.
    assert set(kwargs) <= set(Company.model_fields), set(kwargs) - set(Company.model_fields)
    entreprise = Company(name="Acme", sector="Industrie", country="MR", **kwargs)
    session.add(entreprise)
    session.flush()
    return entreprise


def _rapport(entreprise_id: uuid.UUID, **kwargs) -> ESGReport:
    defaults = {
        "company_id": entreprise_id,
        "type": TypeRapport.RAPPORT_ESG,
        "channel": CanalDepot.AUTOMATIQUE,
        "source_file": "s3://bucket/rapport.pdf",
        "submitted_at": utcnow(),
    }
    defaults.update(kwargs)
    # SQLModel ignore silencieusement un kwarg inconnu : jamais un champ de test perdu en route.
    assert set(defaults) <= set(ESGReport.model_fields), set(defaults) - set(ESGReport.model_fields)
    return ESGReport(**defaults)


def test_creation_rapport_lie_a_entreprise_statut_par_defaut(session) -> None:
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()

    assert rapport.id is not None
    assert rapport.status == ReportStatus.SUBMITTED
    assert rapport.extraction_status == ExtractionStatus.QUEUED
    assert rapport.auditor_id is None


def test_entreprise_id_obligatoire(session) -> None:
    # SQLModel (table=True) ne valide pas les champs requis à la
    # construction : la contrainte NOT NULL s'applique au flush, côté base.
    rapport = ESGReport(
        company_id=None,  # type: ignore[arg-type]
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.AUTOMATIQUE,
        source_file="x",
        submitted_at=utcnow(),
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


@pytest.mark.parametrize("statut", list(ReportStatus))
def test_sept_statuts_tous_atteignables(session, statut: ReportStatus) -> None:
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id, status=statut)
    session.add(rapport)
    session.flush()

    assert rapport.status == statut


def _preuve(session) -> Evidence:
    preuve = Evidence(
        document_name="rapport-annuel-2025.pdf",
        year=2025,
        total_pages=120,
        page_start=42,
        page_end=44,
        excerpt_pdf_path="s3://bucket/extraits/42-44.pdf",
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

    indicateur = ESGMetric(
        report_id=rapport.id,
        pillar=Pilier.ENVIRONNEMENT,
        metric_code="GHG-SCOPE1",
        value=123.4,
        unit="tCO2e",
        method=MethodeDonnee.RAPPORTEE,
        proof_id=preuve.id,
    )
    donnee_carbone = CarbonEmission(
        report_id=rapport.id,
        scope=1,
        tonnes_co2e=123.4,
        year=2025,
        method=MethodeDonnee.RAPPORTEE,
        pcaf_data_quality=3,
        proof_id=preuve.id,
    )
    session.add(indicateur)
    session.add(donnee_carbone)
    session.flush()

    assert indicateur.report_id == donnee_carbone.report_id == rapport.id
    assert indicateur.report.id == rapport.id
    assert donnee_carbone.report.id == rapport.id
    assert indicateur in rapport.metrics
    assert donnee_carbone in rapport.carbon_data
    assert indicateur in preuve.metrics
    assert donnee_carbone in preuve.carbon_emissions


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
        CarbonEmission.model_validate(
            {
                "report_id": rapport.id,
                "scope": 1,
                "tonnes_co2e": 1.0,
                "year": 2025,
                "method": MethodeDonnee.RAPPORTEE,
                "pcaf_data_quality": score_invalide,
                "proof_id": preuve.id,
            }
        )


@pytest.mark.parametrize("scope_invalide", [0, 4, -1])
def test_scope_hors_bornes_rejete_en_base(session, scope_invalide: int) -> None:
    """Complète test_score_qualite_pcaf_hors_bornes_rejete : ici la construction passe par
    CarbonEmission(**kwargs) directe (comme le fait le code applicatif réel, ex.
    app/ingestion/extractor.py), qui ne déclenche jamais la validation Pydantic — seule la
    contrainte CHECK côté PostgreSQL (Phase 5 §6) protège ce chemin."""
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)

    session.add(
        CarbonEmission(
            report_id=rapport.id,
            scope=scope_invalide,
            tonnes_co2e=1.0,
            year=2025,
            method=MethodeDonnee.RAPPORTEE,
            pcaf_data_quality=3,
            proof_id=preuve.id,
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
        CarbonEmission(
            report_id=rapport.id,
            scope=1,
            tonnes_co2e=-0.01,
            year=2025,
            method=MethodeDonnee.RAPPORTEE,
            pcaf_data_quality=3,
            proof_id=preuve.id,
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
        CarbonEmission(
            report_id=rapport.id,
            scope=1,
            tonnes_co2e=1.0,
            year=2025,
            method=MethodeDonnee.RAPPORTEE,
            pcaf_data_quality=pcaf_invalide,
            proof_id=preuve.id,
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
    """Comportement documenté : rapport_id (ESGMetric, CarbonEmission) ne
    porte pas de cascade de suppression. Supprimer un ESGReport encore
    référencé échoue avec une IntegrityError — jamais de suppression
    silencieuse des indicateurs/données carbone associés."""
    entreprise = _entreprise(session)
    rapport = _rapport(entreprise.id)
    session.add(rapport)
    session.flush()
    preuve = _preuve(session)
    session.add(
        ESGMetric(
            report_id=rapport.id,
            pillar=Pilier.SOCIAL,
            metric_code="EMP-01",
            value=1.0,
            unit="ratio",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.flush()

    session.delete(rapport)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
