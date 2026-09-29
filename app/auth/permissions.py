"""Règles d'autorisation et de contrôle d'accès par rôle.

require_role(*roles) est une fabrique de dépendance FastAPI : une route
déclare Depends(require_role(Role.ADMIN)) et reçoit une
PermissionDeniedError (403) si le rôle de l'utilisateur courant n'est pas
dans la liste autorisée. S'appuie exclusivement sur get_current_user
(app/core/dependencies.py) — jamais de vérification de rôle dupliquée
ailleurs dans une route métier.
"""

from collections.abc import Callable

from fastapi import Depends

from app.auth.models import User
from app.core.dependencies import get_current_user
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError


def require_role(*roles: Role) -> Callable[..., User]:
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedError(
                f"Rôle {current_user.role.value} non autorisé pour cette action."
            )
        return current_user

    return _check
