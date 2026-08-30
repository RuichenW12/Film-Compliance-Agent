"""What each budget band costs, with nothing estimated.

At the idea stage a creator has no budget, so asking for one gets a worse
answer than not asking. The comparison turns the question round: here is what
each level would mean, plan against it.

That is only useful if it is true, and the temptation in a table like this is
to fill every cell. These tests pin the opposite: the boundaries come from the
snapshot, the step counts are counted rather than guessed, and the two classes
whose deadline the regulation does not state say so instead of estimating one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.comparison import budget_comparison
from schemas.snapshot import FileSnapshotService

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "policy" / "seed-snapshot-v2.yaml"


@pytest.fixture
def rows() -> list[dict]:
    return budget_comparison(FileSnapshotService(V2), "v2")


def test_there_is_one_row_per_band_lightest_first(rows) -> None:
    """A budget grows upward, so the table reads in the direction of planning."""

    assert [row["tier"] for row in rows] == ["T3", "T2", "T1"]
    assert [row["amount_bracket"] for row in rows] == [
        "below_lower",
        "between",
        "at_or_above_upper",
    ]


def test_the_boundaries_are_the_published_ai_thresholds(rows) -> None:
    for row in rows:
        assert row["lower_rmb"] == 300_000
        assert row["upper_rmb"] == 800_000


def test_each_band_carries_its_filing_route(rows) -> None:
    by_tier = {row["tier"]: row for row in rows}
    assert by_tier["T3"]["authority"] == "platform"
    assert by_tier["T2"]["authority"] == "provincial"
    assert by_tier["T1"]["authority"] == "nrta_national"
    assert by_tier["T1"]["pre_shoot_filing"] == "required"
    assert by_tier["T3"]["pre_shoot_filing"] == "not_required"
    assert by_tier["T3"]["blocks_release"] is False
    assert by_tier["T1"]["blocks_release"] is True


def test_the_effort_column_is_counted_not_estimated(rows) -> None:
    """Steps whose owner is the creator, straight out of the process template.

    This is the column standing in for "how hard is this", and it is the one a
    reader is most likely to assume was invented. It is not: 5 of 7, 3 of 5 and
    2 of 4 are countable from `p4_process_templates`.
    """

    by_tier = {row["tier"]: row for row in rows}
    assert (by_tier["T1"]["steps_yours"], by_tier["T1"]["steps_total"]) == (5, 7)
    assert (by_tier["T2"]["steps_yours"], by_tier["T2"]["steps_total"]) == (3, 5)
    assert (by_tier["T3"]["steps_yours"], by_tier["T3"]["steps_total"]) == (2, 4)


def test_only_the_class_with_a_stated_deadline_has_one(rows) -> None:
    """Article 20 gives twenty days for a one-class decision. Only that one.

    Two-class has no deadline in the regulation and three-class is platform
    self-review rather than an administrative approval, so both are None. An
    estimate in those cells would be a number a creator plans a schedule
    around, and we have nothing to base one on.
    """

    by_tier = {row["tier"]: row for row in rows}
    assert by_tier["T1"]["statutory_deadline_key"] is not None
    assert by_tier["T1"]["deadline_clause"] == "nrta-order-16-article-20"
    assert by_tier["T2"]["statutory_deadline_key"] is None
    assert by_tier["T3"]["statutory_deadline_key"] is None


def test_the_deadline_clause_is_really_in_the_snapshot(rows) -> None:
    """Otherwise the citation is decoration."""

    snapshots = FileSnapshotService(V2)
    clause = snapshots.clause("nrta-order-16-article-20", "v2")
    assert clause is not None
    assert "二十日" in clause.text


def test_every_row_cites_the_clauses_behind_its_route(rows) -> None:
    for row in rows:
        assert row["clause_refs"], row["tier"]


def test_a_snapshot_without_thresholds_yields_nothing(tmp_path) -> None:
    """A partial table would be planned against as readily as a full one."""

    v1 = ROOT / "policy" / "seed-snapshot-v1.yaml"
    result = budget_comparison(FileSnapshotService(v1), "v1")
    assert result is None or all(
        row["lower_rmb"] is not None for row in result
    ), "either no table at all, or one with real boundaries"


def test_an_unknown_version_yields_nothing() -> None:
    assert budget_comparison(FileSnapshotService(V2), "v999") is None
