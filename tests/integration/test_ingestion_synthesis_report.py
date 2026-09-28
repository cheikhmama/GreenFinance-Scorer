import uuid

from app.company.models import Entreprise
from app.core.enums import CanalDepot, MethodeDonnee, Pilier, TypeRapport
from app.ingestion.extractor import CODES_AUTO_DECLARES_PAR_PILIER
from app.ingestion.models import (
    DonneeCarbone,
    IndicateurESG,
    PreuveDocumentaire,
    RapportESG,
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


def _rapport(session) -> RapportESG:
    entreprise = Entreprise(nom=f"Synthese {uuid.uuid4()}", secteur="Industrie", pays="France")
    session.add(entreprise)
    session.flush()
    rapport = RapportESG(
        entreprise_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.ENTREPRISE,
        fichier_source="rapports/test/synthese-dummy.pdf",
        annee_reporting=2025,
    )
    session.add(rapport)
    session.flush()
    return rapport


def _preuve(session) -> PreuveDocumentaire:
    preuve = PreuveDocumentaire(
        nom_document="rapport-test.pdf",
        annee=2025,
        nombre_pages_total=1,
        page_debut=3,
        page_fin=3,
        pdf_extrait_genere="preuves/test/page_3.pdf",
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
    reel = IndicateurESG(
        rapport_id=rapport.id,
        pilier=Pilier.SOCIAL,
        code="femmes_effectif_pourcentage",
        valeur=30.0,
        unite="%",
        methode=MethodeDonnee.RAPPORTEE,
        preuve_id=preuve.id,
    )
    reel.preuve = preuve
    declare = IndicateurESG(
        rapport_id=rapport.id,
        pilier=Pilier.SOCIAL,
        code="score_social_declare",
        valeur=70.0,
        unite="",
        methode=MethodeDonnee.RAPPORTEE,
        preuve_id=preuve.id,
    )
    declare.preuve = preuve

    elements = _section_indicateurs([reel, declare])
    table = elements[-1]
    codes_affiches = {ligne[0] for ligne in table._cellvalues[1:]}
    assert codes_affiches == {"femmes_effectif_pourcentage"}
    assert "score_social_declare" not in codes_affiches


def test_section_declare_par_lentreprise_isole_les_codes_auto_declares(session) -> None:
    rapport = _rapport(session)
    rapport.score_global_declare = 66.0
    preuve = _preuve(session)
    declare = IndicateurESG(
        rapport_id=rapport.id,
        pilier=Pilier.SOCIAL,
        code="score_social_declare",
        valeur=70.0,
        unite="",
        methode=MethodeDonnee.RAPPORTEE,
        preuve_id=preuve.id,
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
    dc = DonneeCarbone(
        rapport_id=uuid.uuid4(),
        scope=1,
        valeur_tonnes_co2e=1200.5,
        annee=2025,
        methode=MethodeDonnee.RAPPORTEE,
        score_qualite_pcaf=3,
        preuve_id=preuve.id,
    )
    dc.preuve = preuve

    elements = _section_carbone([dc])
    assert "non intégrées au score calculé" in _texte(elements)
    table = elements[-1]
    assert any(str(cellule) == "1" for ligne in table._cellvalues[1:] for cellule in ligne)


def test_generer_rapport_synthese_produit_un_pdf_valide(session) -> None:
    rapport = _rapport(session)
    preuve = _preuve(session)
    session.add(
        IndicateurESG(
            rapport_id=rapport.id,
            pilier=Pilier.GOUVERNANCE,
            code="femmes_conseil_pourcentage",
            valeur=40.0,
            unite="%",
            methode=MethodeDonnee.RAPPORTEE,
            preuve_id=preuve.id,
        )
    )
    session.add(
        DonneeCarbone(
            rapport_id=rapport.id,
            scope=1,
            valeur_tonnes_co2e=500.0,
            annee=2025,
            methode=MethodeDonnee.RAPPORTEE,
            score_qualite_pcaf=3,
            preuve_id=preuve.id,
        )
    )
    session.commit()

    contenu = generer_rapport_synthese(session, rapport)

    assert contenu.startswith(b"%PDF-")
    assert len(contenu) > 500
