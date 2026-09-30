"""Schémas Pydantic d'entrée/sortie du module Auditeur.

Jamais réutilisés comme modèles de persistance (voir ARCHITECTURE.md §2).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import AuditDecision


class AvisAuditPublic(BaseModel):
    """Sans auditeur_id — non utilisé par une route dans cette passe, gardé pour une future
    vue Entreprise-facing éventuelle. Documente explicitement la forme sans identité auditeur,
    plutôt que de laisser cette contrainte implicite."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    decision: AuditDecision
    comment: str | None
    submitted_at: datetime


class AvisAuditAdmin(AvisAuditPublic):
    """Réservé Administrateur/Auditeur — jamais exposé à un compte Entreprise (voir
    app/audit/models.py::AuditOpinion.auditor_id)."""

    auditor_id: uuid.UUID


class SoumettreAvisRequest(BaseModel):
    decision: AuditDecision
    comment: str | None = None
