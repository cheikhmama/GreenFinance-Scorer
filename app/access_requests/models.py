"""Demandes d'accès des Investisseurs et des Chercheurs (tâche 5.10).

Un Investisseur ou un Chercheur s'inscrit lui-même ; son compte existe dès la demande (rôle fixé,
aucun mot de passe : il ne peut pas se connecter) et l'Administrateur l'approuve — le lien
d'activation part alors, comme pour une entreprise validée — ou la refuse avec un motif.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel

from app.core.database import utcnow
from app.core.enums import (
    AccessRequestStatus,
    InvestorType,
    ResearchDomain,
    Role,
    sa_enum_column,
)


class AccessRequest(SQLModel, table=True):
    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint("role IN ('INVESTOR', 'RESEARCHER')", name="ck_access_requests_role"),
        # Une seule précision, celle du rôle : type d'investisseur ou domaine de recherche.
        CheckConstraint(
            "(role = 'INVESTOR' AND investor_type IS NOT NULL AND research_domain IS NULL)"
            " OR (role = 'RESEARCHER' AND research_domain IS NOT NULL AND investor_type IS NULL)",
            name="ck_access_requests_detail_by_role",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Le compte demandé, créé sans mot de passe ; supprimé avec lui.
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE", unique=True, index=True)
    role: Role = Field(sa_column=sa_enum_column(Role))
    organization: str = Field(max_length=200)
    investor_type: InvestorType | None = Field(
        default=None, sa_column=sa_enum_column(InvestorType, nullable=True)
    )
    research_domain: ResearchDomain | None = Field(
        default=None, sa_column=sa_enum_column(ResearchDomain, nullable=True)
    )
    status: AccessRequestStatus = Field(
        default=AccessRequestStatus.PENDING_APPROVAL,
        sa_column=sa_enum_column(AccessRequestStatus),
    )
    requested_at: datetime = Field(default_factory=utcnow)
    decided_at: datetime | None = None
    decided_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="SET NULL", index=True
    )
    rejection_reason: str | None = Field(default=None, max_length=2000)
