"""Jeu de démonstration — les 6 entreprises synthétiques de data_test/reference_e2e/, parcourues à
travers les vrais services métier (affectation, avis, validation avec calcul du score,
publication, portefeuille, projet de recherche). Sert à explorer l'interface et aux captures
d'écran du README.

Les indicateurs sont ceux que l'extraction produit sur ces PDF (`extraction_attendue` de chaque
scenario.json), chacun avec sa page-preuve découpée dans le vrai PDF : l'étape d'extraction
(Docling + LLM) est la seule court-circuitée. Chiffre d'affaires et valeur d'entreprise, absents
des scénarios, sont des valeurs de démonstration.

Base VIDE uniquement (le script refuse une base qui a déjà des comptes). Aucun job n'est envoyé à
Redis : pas d'e-mail, et la synthèse PDF est générée directement.

    DATABASE_URL=postgresql+psycopg://…/greenfinance_demo STORAGE_PATH=./storage/demo \\
      uv run python scripts/seed_demo.py

Comptes créés (mot de passe commun : MOT_DE_PASSE ci-dessous) : admin@, auditeur@,
investisseur@, institution@, chercheur@ et une adresse par entreprise, tous @greenfinance-demo.com.
"""

import json
import sys
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlmodel import Session, select

import app.main  # noqa: F401  -- enregistre tous les modèles
from app.admin.review_queue import publier_entreprise, valider_rapport
from app.audit.assignment import affecter_auditeur
from app.audit.opinion import soumettre_avis
from app.auth.hashing import hash_password
from app.auth.models import InstitutionProfile, User
from app.carbon.pcaf import qualite_donnee_pcaf
from app.company.models import Company
from app.core import storage
from app.core.audit import auditer
from app.core.database import engine, utcnow
from app.core.enums import (
    AuditDecision,
    CompanyStatus,
    Currency,
    DataMethod,
    DurationType,
    ExtractionStatus,
    MetricCoverageStatus,
    ReportStatus,
    ReportType,
    Role,
    SubmissionChannel,
)
from app.ingestion.extractor import INDICATEURS_CIBLES
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
    MetricCoverage,
)
from app.ingestion.proof_generator import generate_page_proof
from app.ingestion.synthesis_report import regenerer_synthese
from app.institution.chercheurs import inviter_chercheur
from app.institution.projets import (
    affecter_chercheur,
    ajouter_entreprise_perimetre,
    creer_projet,
)
from app.investor.portfolio import ajouter_position, creer_portefeuille
from app.investor.schemas import AjouterPositionRequest
from app.researcher.analyses import creer_analyse, soumettre_analyse
from app.researcher.rattachements import accepter_invitation

MOT_DE_PASSE = "demo-greenfinance-2026"
DOMAINE = "greenfinance-demo.com"
CORPUS = Path(__file__).resolve().parent.parent / "data_test" / "reference_e2e"
CIBLES = {c.code: c for c in INDICATEURS_CIBLES}

# Dossier -> (e-mail du titulaire, étape atteinte, CA et VE de démonstration en M€)
ENTREPRISES = {
    "atlas_industries": ("atlas", "publiee", 820, 1_450),
    "nordwind_energie": ("nordwind", "publiee", 1_900, 5_200),
    "blue_horizon_shipping": ("bluehorizon", "publiee", 640, 1_100),
    "ferrosahel_mining": ("ferrosahel", "publiee", 1_250, 2_300),
    "meridian_mining": ("meridian", "decision", 980, 1_700),
    "verdance_foods": ("verdance", "audit", 530, 760),
}


def _compte(session: Session, email: str, nom: str, role: Role, admin_id=None) -> User:
    utilisateur = User(
        email=f"{email}@{DOMAINE}",
        name=nom,
        role=role,
        password_hash=hash_password(MOT_DE_PASSE),
        activated_at=utcnow(),
    )
    session.add(utilisateur)
    session.flush()
    if role == Role.INSTITUTION:
        session.add(InstitutionProfile(user_id=utilisateur.id, export_quota=10))
    auditer(session, admin_id or utilisateur.id, "account_created", "User", utilisateur.id, "success")
    return utilisateur


def _rapport_extrait(session: Session, entreprise: Company, dossier: Path, scenario: dict) -> ESGReport:
    """Rapport déposé puis extrait : PDF copié dans le stockage, indicateurs et données carbone
    avec page-preuve, couverture par code — ce que le pipeline aurait persisté."""
    meta = scenario["rapport"]
    annee = meta["annee_reporting"]
    source = dossier / meta["fichier"]
    nom_fichier = f"{dossier.name}_rapport_{annee}.pdf"
    rapport_id = uuid.uuid4()
    depose_le = utcnow() - timedelta(days=12)
    rapport = ESGReport(
        id=rapport_id,
        company_id=entreprise.id,
        source_file=storage.save_bytes(f"rapports/{rapport_id}.pdf", source.read_bytes()),
        created_at=depose_le,
        type=ReportType(meta["type"]),
        channel=SubmissionChannel.ENTREPRISE,
        submitted_at=depose_le,
        status=ReportStatus.SUBMITTED,
        extraction_status=ExtractionStatus.DONE,
        extraction_finished_at=depose_le,
        original_filename=nom_fichier,
        fiscal_year=annee,
    )
    session.add(rapport)
    session.flush()

    import pymupdf

    with pymupdf.open(source) as pdf:
        pages = pdf.page_count
    preuves: dict[int, Evidence] = {}
    trouves = set()
    for attendu in scenario["extraction_attendue"]["indicateurs"]:
        cible = CIBLES[attendu["code"]]
        page = attendu["page_attendue"]
        if page not in preuves:
            preuves[page] = generate_page_proof(
                source_pdf_path=source,
                nom_document=nom_fichier,
                annee=annee,
                nombre_pages_total=pages,
                page=page,
                rapport_id=rapport.id,
            )
            session.add(preuves[page])
            session.flush()
        preuve = preuves[page]
        commun = {
            "report_id": rapport.id,
            "method": DataMethod.RAPPORTEE,
            "proof_id": preuve.id,
            "raw_value": f"{attendu['valeur_attendue']:g} {attendu['unite']}",
            "value_year": annee,
        }
        if cible.cible == "donnee_carbone":
            session.add(
                CarbonEmission(
                    scope=cible.scope,
                    ghg_category=cible.categorie_ges,
                    tonnes_co2e=attendu["valeur_attendue"],
                    year=annee,
                    pcaf_data_quality=qualite_donnee_pcaf(DataMethod.RAPPORTEE),
                    **commun,
                )
            )
        elif cible.cible == "rapport_score_global":
            rapport.declared_global_score = attendu["valeur_attendue"]
            rapport.declared_global_score_proof_id = preuve.id
        else:
            session.add(
                ESGMetric(
                    pillar=cible.pilier,
                    metric_code=attendu["code"],
                    value=attendu["valeur_attendue"],
                    unit=attendu["unite"],
                    **commun,
                )
            )
        trouves.add(attendu["code"])
    for code in CIBLES:
        statut = MetricCoverageStatus.TROUVE if code in trouves else MetricCoverageStatus.NON_TROUVE
        session.add(
            MetricCoverage(report_id=rapport.id, metric_code=code, status=statut, pages_examined=pages)
        )
    session.commit()
    return rapport


def main() -> None:
    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            sys.exit("Base non vide : ce jeu de démonstration ne se charge que dans une base neuve.")

        admin = _compte(session, "admin", "Awa Sall", Role.ADMIN)
        auditeur = _compte(session, "auditeur", "Karim Benali", Role.AUDITOR, admin.id)
        investisseur = _compte(session, "investisseur", "Claire Martin", Role.INVESTOR, admin.id)
        institution = _compte(session, "institution", "Institut Sahel Climat", Role.INSTITUTION, admin.id)
        chercheur = _compte(session, "chercheur", "Moussa Diop", Role.RESEARCHER, admin.id)
        session.commit()

        publiees: list[Company] = []
        for nom_dossier, (email, etape, ca, ve) in ENTREPRISES.items():
            dossier = CORPUS / nom_dossier
            scenario = json.loads((dossier / "scenario.json").read_text(encoding="utf-8"))
            profil = scenario["entreprise"]
            titulaire = _compte(session, email, f"Direction RSE — {profil['nom']}", Role.ENTERPRISE, admin.id)
            entreprise = Company(
                name=profil["nom"],
                sector=profil["secteur"],
                country=profil["pays"],
                description=f"{profil['nom']} — entreprise synthétique du corpus de démonstration.",
                status=CompanyStatus.ACTIVE,
                owner_user_id=titulaire.id,
                onboarded_at=utcnow() - timedelta(days=30),
                onboarded_by_id=admin.id,
                revenue=Decimal(ca) * 1_000_000,
                revenue_currency=Currency.EUR,
                enterprise_value=Decimal(ve) * 1_000_000,
                enterprise_value_currency=Currency.EUR,
                enterprise_value_as_of=(utcnow() - timedelta(days=90)).date(),
            )
            session.add(entreprise)
            session.commit()

            rapport = _rapport_extrait(session, entreprise, dossier, scenario)
            affecter_auditeur(session, rapport.id, auditeur.id)
            if etape == "audit":
                continue
            soumettre_avis(
                session,
                rapport.id,
                auditeur.id,
                AuditDecision.RECOMMANDE_VALIDATION,
                "Indicateurs conformes aux pages citées ; périmètre carbone complet.",
            )
            if etape == "decision":
                continue
            valider_rapport(session, rapport.id, "Rapport validé après revue de l'avis d'audit.")
            regenerer_synthese(session, rapport)
            session.commit()
            publiees.append(publier_entreprise(session, entreprise.id))

        portefeuille = creer_portefeuille(session, investisseur.id, "Transition climat 2026")
        for entreprise, montant in zip(publiees, (4_000_000, 6_500_000, 2_500_000, 3_000_000), strict=True):
            ajouter_position(
                session,
                investisseur.id,
                portefeuille.id,
                AjouterPositionRequest(
                    company_id=entreprise.id,
                    amount=Decimal(montant),
                    currency=Currency.EUR,
                    duration_type=DurationType.OUVERTE,
                    start_date=utcnow(),
                ),
            )

        rattachement = inviter_chercheur(
            session, institution.id, chercheur.id, "Accès en lecture aux rapports validés du périmètre."
        )
        accepter_invitation(session, chercheur.id, rattachement.id)
        projet = creer_projet(
            session,
            institution.id,
            "Intensité carbone des industries lourdes",
            "Comparer les trajectoires carbone des entreprises industrielles et minières.",
            "Identifier les écarts d'intensité Scope 1+2 à secteur comparable.",
            utcnow() - timedelta(days=20),
            utcnow() + timedelta(days=160),
            utcnow() + timedelta(days=60),
        )
        affecter_chercheur(session, institution.id, projet.id, chercheur.id)
        for entreprise in publiees:
            ajouter_entreprise_perimetre(session, institution.id, projet.id, entreprise.id)
        analyse = creer_analyse(
            session,
            chercheur.id,
            projet.id,
            "Mines et industrie : premières comparaisons",
            "Ferrosahel Mining présente l'intensité Scope 1+2 la plus élevée du périmètre ; "
            "Atlas Industries la plus faible. Les écarts de parité au conseil restent modérés.",
            [e.id for e in publiees if e.name in {"Atlas Industries", "Ferrosahel Mining"}],
        )
        soumettre_analyse(session, chercheur.id, analyse.id)

    print(f"Jeu de démonstration chargé — mot de passe commun : {MOT_DE_PASSE}")
    for email in ("admin", "auditeur", "investisseur", "institution", "chercheur", "atlas"):
        print(f"  {email}@{DOMAINE}")


if __name__ == "__main__":
    # Aucun job vers Redis : la démo ne doit jamais remplir la file d'un worker de développement.
    with patch("app.worker.queue._envoyer_a_redis", AsyncMock(return_value=True)):
        main()
