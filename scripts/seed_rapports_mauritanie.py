"""Seed ponctuel — dépose les 5 rapports ESG réels (Mauritanie) fournis par l'utilisateur dans
le pipeline d'extraction réel (Docling + Gemini, pas le mode démo synthétique : GEMINI_API_KEY
n'est pas un placeholder dans .env).

SOMELEC, SMH, SMCRR, SNM : comptes Entreprise créés (n'existaient pas). SNDE : réutilise la fiche
déjà active en base (celle qui a déjà un rapport en cours d'audit), pas de nouveau compte — choix
confirmé par l'utilisateur pour traiter le doublon existant.

Script à usage unique, pas un outil réutilisable — à supprimer une fois le dépôt confirmé.
Usage : uv run python scripts/seed_rapports_mauritanie.py
"""

import asyncio
import uuid
from pathlib import Path

from fastapi import BackgroundTasks
from sqlmodel import Session, select

import app.main  # noqa: F401  -- enregistre tous les modèles pour SQLAlchemy avant toute requête
from app.admin.utilisateurs import creer_utilisateur
from app.auth.models import Utilisateur
from app.company.models import Company
from app.company.rapports import deposer_rapport
from app.core.database import engine
from app.core.enums import Role, TypeRapport
from app.core.exceptions import ValidationError

SOURCE_DIR = Path(__file__).resolve().parent.parent / "storage" / "seed_data" / "rapports_esg_mauritanie"
# Compte ADMINISTRATEUR actif existant, utilisé comme acteur de création pour la traçabilité
# (app/core/audit.py) — pas un choix arbitraire, juste le seul admin actif trouvé en base.
ACTEUR_ADMIN_ID = uuid.UUID("f348434f-c3d2-4ad8-9ad0-56e7ddfa9a74")
ANNEE_REPORTING = 2025

# Nom, secteur, pays extraits directement de la page de garde de chaque PDF — jamais devinés.
NOUVELLES_ENTREPRISES = [
    # SOMELEC déjà déposé et extrait avec succès (compte somelec@example.com, rapport
    # 23b0f64e-8d0f-4632-a2c0-7934abfc506c) — retiré de cette liste pour ne pas créer un second
    # rapport en double (deposer_rapport n'est pas idempotent, aucune vérification "déjà déposé").
    {
        "acronyme": "SMH",
        "nom": "Société Mauritanienne des Hydrocarbures",
        "secteur": "Hydrocarbures / Énergie",
        "pays": "Mauritanie",
        "email": "smh@example.com",
        "fichier": "SMH_rapport_ESG_2025.pdf",
    },
    {
        "acronyme": "SMCRR",
        "nom": "Société Mauritanienne de Construction, Restauration et Réhabilitation",
        "secteur": "BTP / Construction",
        "pays": "Mauritanie",
        "email": "smcrr@example.com",
        "fichier": "SMCRR_rapport_ESG_2025.pdf",
    },
    {
        "acronyme": "SNM",
        "nom": "Société Mauritanienne de Navigation",
        "secteur": "Transport maritime",
        "pays": "Mauritanie",
        "email": "snm@example.com",
        "fichier": "SNM_rapport_ESG_2025.pdf",
    },
]

# Fiche SNDE déjà existante et active (1 rapport déjà AFFECTE_AUDITEUR) — le nouveau PDF est
# déposé comme rapport indépendant supplémentaire sur cette même entreprise.
SNDE_ENTREPRISE_ID = uuid.UUID("2ecdb961-3c6a-409a-879e-e4482989fb24")
SNDE_FICHIER = "SNDE_rapport_ESG_2025.pdf"


async def _deposer(session: Session, entreprise_id: uuid.UUID, contenu: bytes, label: str) -> None:
    tasks = BackgroundTasks()
    rapport = deposer_rapport(
        session, tasks, entreprise_id, contenu, TypeRapport.RAPPORT_ESG, ANNEE_REPORTING
    )
    print(f"[{label}] rapport {rapport.id} deposé (statut={rapport.status}) — extraction en cours...")
    await tasks()
    session.refresh(rapport)
    print(f"[{label}] extraction terminée — statut={rapport.status} erreur={rapport.extraction_error}")


async def main() -> None:
    with Session(engine) as session:
        for spec in NOUVELLES_ENTREPRISES:
            utilisateur = session.exec(
                select(Utilisateur).where(Utilisateur.email == spec["email"])
            ).first()
            if utilisateur is not None:
                print(f"[{spec['acronyme']}] compte {spec['email']} déjà existant, réutilisation.")
            else:
                try:
                    utilisateur, mot_de_passe = creer_utilisateur(
                        session,
                        ACTEUR_ADMIN_ID,
                        spec["email"],
                        None,
                        Role.ENTREPRISE,
                        nom_entreprise=spec["nom"],
                        secteur=spec["secteur"],
                        pays=spec["pays"],
                    )
                    print(
                        f"[{spec['acronyme']}] compte créé : {utilisateur.email} "
                        f"/ mot de passe temporaire {mot_de_passe}"
                    )
                except ValidationError as exc:
                    print(f"[{spec['acronyme']}] ERREUR création compte : {exc}")
                    continue

            entreprise = session.exec(
                select(Company).where(Company.owner_user_id == utilisateur.id)
            ).first()
            if entreprise is None:
                print(f"[{spec['acronyme']}] ERREUR : aucune fiche Entreprise liée, dépôt impossible.")
                continue

            contenu = (SOURCE_DIR / spec["fichier"]).read_bytes()
            try:
                await _deposer(session, entreprise.id, contenu, spec["acronyme"])
            except ValidationError as exc:
                print(f"[{spec['acronyme']}] ERREUR dépôt : {exc}")

        contenu = (SOURCE_DIR / SNDE_FICHIER).read_bytes()
        try:
            await _deposer(session, SNDE_ENTREPRISE_ID, contenu, "SNDE")
        except ValidationError as exc:
            print(f"[SNDE] ERREUR dépôt : {exc}")


if __name__ == "__main__":
    asyncio.run(main())
