import uuid

from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import CanalDepot, MethodeDonnee, Pilier, TypeRapport
from app.ingestion.extractor import CODES_AUTO_DECLARES_PAR_PILIER
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
)
from app.ingestion.synthesis_report import (
    _section_carbone,
    _section_declare_par_lentreprise,
    _section_indicateurs,
    _section_score_officiel,
    generer_rapport_synthese,
)
from app.scoring.models import ScoreESG


def _texte(elements: list) -> str:
    """Concatène le texte brut de tout Paragraph d'une liste de flowables -- suffisant pour
    vérifier qu'un message attendu apparaît, sans dépendre du rendu PDF final (fragile/binaire)."""
    return " ".join(getattr(e, "text", "") for e in elements)


def _rapport(session) -> ESGReport:
    entreprise = Company(name=f"Synthese {uuid.uuid4()}", sector="Industrie", country="France")
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        source_file="rapports/test/synthese-dummy.pdf",
        fiscal_year=2025,
        submitted_at=utcnow(),
    )
    session.add(rapport)
    session.flush()
    return rapport


def _preuve(session) -> Evidence:
    preuve = Evidence(
        document_name="rapport-test.pdf",
        year=2025,
        total_pages=1,
        page_start=3,
        page_end=3,
        excerpt_pdf_path="preuves/test/page_3.pdf",
    )
    session.add(preuve)
    session.flush()
    return preuve


def test_section_score_officiel_absent_affiche_en_attente() -> None:
    elements = _section_score_officiel(None)
    assert "En attente de validation" in _texte(elements)


def test_section_score_officiel_present_affiche_les_valeurs() -> None:
    score = ScoreESG(
        rapport_id=uuid.uuid4(),
        configuration_id=uuid.uuid4(),
        valeur_globale=66.45,
        score_environnement=49.91,
        score_social=86.0,
        score_gouvernance=80.0,
    )
    elements = _section_score_officiel(score)
    table = elements[-1]
    valeurs = [str(cellule) for ligne in table._cellvalues for cellule in ligne]
    assert "66.5" in valeurs
    assert "49.9" in valeurs


def test_section_indicateurs_exclut_les_codes_auto_declares(session) -> None:
    rapport = _rapport(session)
    preuve = _preuve(session)
    reel = ESGMetric(
        report_id=rapport.id,
        pillar=Pilier.SOCIAL,
        metric_code="femmes_effectif_pourcentage",
        value=30.0,
        unit="%",
        method=MethodeDonnee.RAPPORTEE,
        proof_id=preuve.id,
    )
    reel.proof = preuve
    declare = ESGMetric(
        report_id=rapport.id,
        pillar=Pilier.SOCIAL,
        metric_code="score_social_declare",
        value=70.0,
        unit="",
        method=MethodeDonnee.RAPPORTEE,
        proof_id=preuve.id,
    )
    declare.proof = preuve

    elements = _section_indicateurs([reel, declare])
    table = elements[-1]
    codes_affiches = {ligne[0] for ligne in table._cellvalues[1:]}
    assert codes_affiches == {"femmes_effectif_pourcentage"}
    assert "score_social_declare" not in codes_affiches


def test_section_declare_par_lentreprise_isole_les_codes_auto_declares(session) -> None:
    rapport = _rapport(session)
    rapport.declared_global_score = 66.0
    preuve = _preuve(session)
    declare = ESGMetric(
        report_id=rapport.id,
        pillar=Pilier.SOCIAL,
        metric_code="score_social_declare",
        value=70.0,
        unit="",
        method=MethodeDonnee.RAPPORTEE,
        proof_id=preuve.id,
    )

    elements = _section_declare_par_lentreprise(rapport, [declare])
    table = elements[-1]
    contenu = {ligne[0] for ligne in table._cellvalues[1:]}
    assert "score_social_declare" in contenu
    assert "Score ESG global déclaré" in contenu
    assert CODES_AUTO_DECLARES_PAR_PILIER == {
        "score_environnement_declare",
        "score_social_declare",
        "score_gouvernance_declare",
    }


def test_section_carbone_signale_explicitement_la_non_integration_au_score(session) -> None:
    preuve = _preuve(session)
    dc = CarbonEmission(
        report_id=uuid.uuid4(),
        scope=1,
        tonnes_co2e=1200.5,
        year=2025,
        method=MethodeDonnee.RAPPORTEE,
        pcaf_data_quality=3,
        proof_id=preuve.id,
    )
    dc.proof = preuve

    elements = _section_carbone([dc])
    assert "non intégrées au score calculé" in _texte(elements)
    table = elements[-1]
    assert any(str(cellule) == "1" for ligne in table._cellvalues[1:] for cellule in ligne)


def test_generer_rapport_synthese_produit_un_pdf_valide(session) -> None:
    rapport = _rapport(session)
    preuve = _preuve(session)
    session.add(
        ESGMetric(
            report_id=rapport.id,
            pillar=Pilier.GOUVERNANCE,
            metric_code="femmes_conseil_pourcentage",
            value=40.0,
            unit="%",
            method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.add(
        CarbonEmission(
            report_id=rapport.id,
            scope=1,
            tonnes_co2e=500.0,
            year=2025,
            method=MethodeDonnee.RAPPORTEE,
            pcaf_data_quality=3,
            proof_id=preuve.id,
        )
    )
    session.commit()

    contenu = generer_rapport_synthese(session, rapport)

    assert contenu.startswith(b"%PDF-")
    assert len(contenu) > 500
