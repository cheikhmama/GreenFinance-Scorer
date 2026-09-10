"""Prompt 3.9 — scénario de bout en bout sur le schéma complet (Étape 3).

Construit un graphe couvrant les 14 entités du diagramme de classes plus les
deux clarifications ajoutées à la révision (configuration de pondération
ouverte à un Chercheur, position en devise étrangère convertie), et vérifie
que chaque relation se résout dans les deux sens — la preuve que le schéma
appliqué par la migration Alembic consolidée (b5f953dddf56) est fidèle aux
modèles SQLModel, pas seulement que chaque table existe isolément.
"""

import uuid
from datetime import timedelta

from app.audit.models import AvisAudit
from app.auth.models import Utilisateur
from app.company.models import Entreprise
from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    DecisionAudit,
    DevisePosition,
    MethodeDonnee,
    Pilier,
    Role,
    TypeDureeInvestissement,
    TypeRapport,
)
from app.core.models import Notification
from app.ingestion.models import (
    DonneeCarbone,
    IndicateurESG,
    PreuveDocumentaire,
    RapportESG,
)
from app.investor.models import Portefeuille, PositionPortefeuille
from app.scoring.models import ConfigurationPonderation, ScoreESG


def _utilisateur(session, role: Role) -> Utilisateur:
    utilisateur = Utilisateur(
        email=f"{role.value.lower()}-{uuid.uuid4()}@example.com",
        mot_de_passe_hache="hash",
        role=role,
    )
    session.add(utilisateur)
    session.flush()
    return utilisateur


def test_scenario_complet_schema_pivot_relations_bidirectionnelles(session) -> None:
    # --- Entreprise avec montant minimum d'investissement renseigné -------
    entreprise = Entreprise(
        nom="Acme Verte",
        secteur="Industrie",
        pays="MR",
        montant_minimum_investissement=500.0,
    )
    session.add(entreprise)
    session.flush()

    # --- RapportESG -------------------------------------------------------
    rapport = RapportESG(
        entreprise_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        canal=CanalDepot.AUTOMATIQUE,
        fichier_source="s3://bucket/rapport.pdf",
    )
    session.add(rapport)
    session.flush()

    assert rapport in entreprise.rapports
    assert rapport.entreprise.id == entreprise.id

    # --- PreuveDocumentaire + IndicateurESG + DonneeCarbone ---------------
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

    assert indicateur.rapport.id == rapport.id
    assert indicateur in rapport.indicateurs
    assert donnee_carbone.rapport.id == rapport.id
    assert donnee_carbone in rapport.donnees_carbone
    assert indicateur.preuve.id == preuve.id
    assert indicateur in preuve.indicateurs
    assert donnee_carbone.preuve.id == preuve.id
    assert donnee_carbone in preuve.donnees_carbone

    # --- ConfigurationPonderation de référence ET personnalisée (Chercheur)
    chercheur = _utilisateur(session, Role.CHERCHEUR)
    config_reference = ConfigurationPonderation(
        nom="reference", version=1, fichier_yaml="scoring/reference.yaml"
    )
    config_chercheur = ConfigurationPonderation(
        nom="config-chercheur",
        version=1,
        fichier_yaml="scoring/chercheur.yaml",
        utilisateur_id=chercheur.id,
    )
    session.add(config_reference)
    session.add(config_chercheur)
    session.flush()

    assert config_chercheur.utilisateur.id == chercheur.id
    assert config_chercheur in chercheur.configurations_ponderation

    # --- ScoreESG (un par configuration, sur le même RapportESG) ----------
    score_reference = ScoreESG(
        rapport_id=rapport.id,
        configuration_id=config_reference.id,
        valeur_globale=72.0,
        score_environnement=70.0,
        score_social=75.0,
        score_gouvernance=71.0,
    )
    score_chercheur = ScoreESG(
        rapport_id=rapport.id,
        configuration_id=config_chercheur.id,
        valeur_globale=68.0,
        score_environnement=65.0,
        score_social=70.0,
        score_gouvernance=69.0,
    )
    session.add(score_reference)
    session.add(score_chercheur)
    session.flush()

    assert {s.id for s in rapport.scores} == {score_reference.id, score_chercheur.id}
    assert score_reference.rapport.id == rapport.id
    assert score_reference.configuration.id == config_reference.id
    assert score_reference in config_reference.scores
    assert score_chercheur.configuration.id == config_chercheur.id
    assert score_chercheur in config_chercheur.scores

    # --- Portefeuille + positions (USD converti, FIXE, OUVERTE) -----------
    investisseur = _utilisateur(session, Role.INVESTISSEUR)
    portefeuille = Portefeuille(
        investisseur_id=investisseur.id, nom="Portefeuille vert", devise_reference=DevisePosition.USD
    )
    session.add(portefeuille)
    session.flush()

    assert portefeuille.investisseur.id == investisseur.id
    assert portefeuille in investisseur.portefeuilles

    debut_fixe = utcnow() + timedelta(days=1)
    position_usd = PositionPortefeuille.model_validate(
        {
            "portefeuille_id": portefeuille.id,
            "entreprise_id": entreprise.id,
            "montant_investi": 1000.0,
            "devise": DevisePosition.USD,
            "taux_change_utilise": 0.92,
            "montant_converti": 920.0,
            "type_duree": TypeDureeInvestissement.OUVERTE,
            "date_debut": utcnow(),
        }
    )
    position_fixe = PositionPortefeuille.model_validate(
        {
            "portefeuille_id": portefeuille.id,
            "entreprise_id": entreprise.id,
            "montant_investi": 2000.0,
            "devise": DevisePosition.MRU,
            "montant_converti": 52.0,
            "type_duree": TypeDureeInvestissement.FIXE,
            "date_debut": debut_fixe,
            "date_fin": debut_fixe + timedelta(days=180),
        }
    )
    position_ouverte = PositionPortefeuille.model_validate(
        {
            "portefeuille_id": portefeuille.id,
            "entreprise_id": entreprise.id,
            "montant_investi": 750.0,
            "devise": DevisePosition.EUR,
            "montant_converti": 750.0,
            "type_duree": TypeDureeInvestissement.OUVERTE,
            "date_debut": utcnow(),
        }
    )
    session.add(position_usd)
    session.add(position_fixe)
    session.add(position_ouverte)
    session.flush()

    assert position_usd.taux_change_utilise == 0.92
    assert position_usd.montant_converti == 920.0
    assert position_fixe.date_fin is not None
    assert position_ouverte.date_fin is None
    assert {position_usd.id, position_fixe.id, position_ouverte.id} == {
        p.id for p in portefeuille.positions
    }
    for position in (position_usd, position_fixe, position_ouverte):
        assert position.portefeuille.id == portefeuille.id
        assert position.entreprise.id == entreprise.id
        assert position in entreprise.positions

    # --- AvisAudit ----------------------------------------------------
    auditeur = _utilisateur(session, Role.AUDITEUR)
    avis = AvisAudit(
        rapport_id=rapport.id,
        auditeur_id=auditeur.id,
        decision=DecisionAudit.RECOMMANDE_VALIDATION,
        commentaire="Données cohérentes avec le rapport annuel.",
    )
    session.add(avis)
    session.flush()

    assert avis.rapport.id == rapport.id
    assert avis in rapport.avis_audit
    assert avis.auditeur.id == auditeur.id
    assert avis in auditeur.avis_rendus

    # --- Notification (entité transverse, hors diagramme de classes) ------
    notification = Notification(
        utilisateur_id=investisseur.id,
        message="Un nouveau rapport est disponible pour une entreprise de votre portefeuille.",
        type="RAPPORT_DISPONIBLE",
    )
    session.add(notification)
    session.flush()

    assert notification in investisseur.notifications
    assert notification.utilisateur.id == investisseur.id
