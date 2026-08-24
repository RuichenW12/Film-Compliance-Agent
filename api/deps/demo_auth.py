"""Demo authentication.

Locked decision 2: there is no real auth. A role switcher in the top bar sets a
header and the API trusts it. Everything auth-shaped lives in this file so a
real identity provider can replace it without touching routers.

The API contract names the header `X-Mock-Role`; the web shell historically used
`X-Demo-Role`. Both are accepted, contract name first.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

from core.errors import ForbiddenError
from schemas.enums import Role

ROLE_HEADERS = ("X-Mock-Role", "X-Demo-Role")
DEFAULT_ROLE = Role.CREATOR
DEFAULT_USER_ID = "u_demo"


@dataclass(frozen=True)
class Principal:
    role: Role
    user_id: str

    def require(self, *roles: Role) -> None:
        if self.role not in roles:
            raise ForbiddenError(
                f"role {self.role.value} may not use this route",
                {"required": [role.value for role in roles]},
            )


def get_principal(
    x_mock_role: str | None = Header(default=None, alias="X-Mock-Role"),
    x_demo_role: str | None = Header(default=None, alias="X-Demo-Role"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> Principal:
    raw_role = (x_mock_role or x_demo_role or DEFAULT_ROLE.value).strip().lower()
    try:
        role = Role(raw_role)
    except ValueError as exc:
        raise ForbiddenError(f"unknown role: {raw_role}") from exc
    return Principal(role=role, user_id=(x_user_id or DEFAULT_USER_ID).strip())


def require_internal_token(
    expected: str,
    x_internal_token: str | None,
) -> None:
    """Guard for `/v1/internal/*`, the only routes the policy loop calls."""

    if not expected:
        raise ForbiddenError("internal routes are disabled: INTERNAL_TOKEN is unset")
    if x_internal_token != expected:
        raise ForbiddenError("invalid internal token")
