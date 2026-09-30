"""Charge tous les modèles SQLModel d'un coup (tâche 4.1).

Les relations entre modules se résolvent par nom ("Company", "Portfolio"...) au premier usage d'un
mapper : toutes les classes doivent alors être déclarées. L'API les charge indirectement via ses
routers ; un process qui n'importe pas l'API — le worker ARQ, un script — importe ce module.
Même liste que alembic/env.py.
"""

from app.audit import models as _audit  # noqa: F401
from app.auth import models as _auth  # noqa: F401
from app.company import models as _company  # noqa: F401
from app.core import models as _core  # noqa: F401
from app.ingestion import models as _ingestion  # noqa: F401
from app.institution import models as _institution  # noqa: F401
from app.investor import models as _investor  # noqa: F401
from app.researcher import models as _researcher  # noqa: F401
from app.scoring import models as _scoring  # noqa: F401
