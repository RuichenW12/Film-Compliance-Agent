"""The mock licence check (TDD section 11 non-goal: no real verification).

This module exists to make the demo's honesty structural. It never contacts a
registry, never asserts that an entity holds a licence, and always stamps
`mock=True`. An institution the local registry does not know reports
`institution_not_in_registry` with both sub-checks left `None` — unknown, not
passed.

The criteria are the ones a filing partner would apply in a real check, run
against demo data: capital above the threshold and no foreign investment. They
are shaped like the real thing so the console is worth demoing; they are not
evidence about any real company.
"""

from __future__ import annotations

from schemas.workflow import LicenseCheck, MockInstitution

# The threshold a real check would read from policy. Held here, not in a pack,
# because it governs the mock check only — a real licence check is a non-goal.
MIN_CAPITAL_RMB = 1_000_000


def check_licence(
    institution_id: str, institution: MockInstitution | None
) -> LicenseCheck:
    """Report what the demo registry can and cannot say about an institution."""

    if institution is None:
        return LicenseCheck(
            institution_id=institution_id,
            mock=True,
            reasons=["institution_not_in_registry"],
        )

    reasons: list[str] = []
    capital_ok = institution.registered_capital_rmb >= MIN_CAPITAL_RMB
    if not capital_ok:
        reasons.append("registered_capital_below_threshold")

    no_foreign_ok = not institution.has_foreign
    if not no_foreign_ok:
        reasons.append("foreign_investment")

    return LicenseCheck(
        institution_id=institution.institution_id,
        valid_until=institution.valid_until,
        capital_ok=capital_ok,
        no_foreign_ok=no_foreign_ok,
        mock=True,
        reasons=reasons,
    )
