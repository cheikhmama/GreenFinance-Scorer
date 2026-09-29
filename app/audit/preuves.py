"""Accès de l'Auditeur à la preuve documentaire d'un indicateur ou d'une donnée carbone.

Distinct de app/investor/entreprises.py::fichier_preuve : l'Auditeur consulte des rapports non
publiés (parfois jamais publiés), l'appartenance se vérifie donc via ESGReport.auditor_id, pas
via Company.published_at. Module séparé de app/audit/opinion.py pour garder ce dernier
focalisé sur la soumission d'avis (voir ARCHITECTURE.md §1).
"""

import uuid

from sqlmodel import Session, select

from app.core.exceptions import NotFoundError
from app.ingestion.models import (
    CarbonEmission,
    ESGMetric,
    ESGReport,
    Evidence,
)


def fichier_preuve(session: Session, rapport_id: uuid.UUID, preuve_id: uuid.UUID, auditeur_id: uuid.UUID) -> str:
    """Chemin de stockage du mini-PDF (une page) prouvant un indicateur ou une donnée carbone d'un
    dossier affecté à CET auditeur — même 404 générique anti-divulgation que
    app/audit/opinion.py::soumettre_avis (jamais de 403 qui confirmerait l'existence d'un rapport
    affecté à quelqu'un d'autre)."""
    rapport = session.get(ESGReport, rapport_id)
    if rapport is None or rapport.auditor_id != auditeur_id:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    appartient_au_rapport = (
        session.exec(
            select(ESGMetric.id).where(
                ESGMetric.proof_id == preuve_id, ESGMetric.report_id == rapport_id
            )
        ).first()
        is not None
        or session.exec(
            select(CarbonEmission.id).where(
                CarbonEmission.proof_id == preuve_id, CarbonEmission.report_id == rapport_id
            )
        ).first()
        is not None
    )
    if not appartient_au_rapport:
        raise NotFoundError("Preuve introuvable.", code="preuve_introuvable")

    preuve = session.get(Evidence, preuve_id)
    assert preuve is not None  # invariant : la requête ci-dessus vient de la trouver par FK
    return preuve.excerpt_pdf_path
