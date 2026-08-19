import uuid

import pytest

from app.auth.permissions import require_role
from app.core.enums import Role
from app.core.exceptions import PermissionDeniedError


class _FakeUtilisateur:
    def __init__(self, role: Role) -> None:
        self.id = uuid.uuid4()
        self.role = role


def test_require_role_accepts_a_user_with_an_authorized_role() -> None:
    user = _FakeUtilisateur(Role.ADMINISTRATEUR)
    check = require_role(Role.ADMINISTRATEUR)

    assert check(current_user=user) is user  # type: ignore[arg-type]


def test_require_role_rejects_a_user_with_an_unauthorized_role() -> None:
    user = _FakeUtilisateur(Role.ENTREPRISE)
    check = require_role(Role.ADMINISTRATEUR, Role.AUDITEUR)

    with pytest.raises(PermissionDeniedError, match="ENTREPRISE"):
        check(current_user=user)  # type: ignore[arg-type]


def test_require_role_accepts_any_of_several_authorized_roles() -> None:
    for role in (Role.ADMINISTRATEUR, Role.AUDITEUR):
        user = _FakeUtilisateur(role)
        check = require_role(Role.ADMINISTRATEUR, Role.AUDITEUR)

        assert check(current_user=user) is user  # type: ignore[arg-type]
