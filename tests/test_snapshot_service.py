"""T-A0 acceptance: the product reads policy only through SnapshotService."""

from __future__ import annotations

import pytest

from core.classify.subject_rules import load_subject_rules
from schemas.policy_snapshot import PackName
from schemas.snapshot import SnapshotNotFoundError


def test_seed_snapshot_serves_all_six_packs(snapshots):
    assert snapshots.latest_version() == "v1"
    for pack in PackName:
        assert isinstance(snapshots.get_pack(pack), dict)


def test_clause_lookup_returns_the_cited_text(snapshots):
    clause = snapshots.clause("nrta-order-16-article-5", "v1")
    assert clause.title
    assert clause.source_url.startswith("https://")


def test_unknown_snapshot_version_is_an_error(snapshots):
    with pytest.raises(SnapshotNotFoundError):
        snapshots.get_pack(PackName.P1_FORM_DEFINITION, "v99")


def test_subject_pack_normalizes_into_matchable_rules(snapshots):
    rules = load_subject_rules(snapshots.get_pack(PackName.P2_SUBJECT_RULES))

    assert len(rules) == 9
    assert all(rule.trigger_patterns for rule in rules)
    # Seed rules are AI-drafted placeholders until the partners confirm them.
    assert all(rule.expert_pending for rule in rules)


def test_packs_are_copies_so_callers_cannot_mutate_policy(snapshots):
    pack = snapshots.get_pack(PackName.P1_FORM_DEFINITION)
    pack["episode_max_minutes_exclusive"] = 1
    assert snapshots.get_pack(PackName.P1_FORM_DEFINITION)["episode_max_minutes_exclusive"] == 20
