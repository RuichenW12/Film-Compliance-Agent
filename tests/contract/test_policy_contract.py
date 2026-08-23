import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from schemas.policy_snapshot import (
    ImpactNode,
    OutboxStatus,
    PackName,
    PolicyOutbox,
    PolicyPacks,
    PolicyProposal,
    PolicySnapshot,
    PolicyUpdatedEvent,
    ProposalStatus,
    RecalcTierRequest,
    RecalcTierResponse,
)
ROOT = Path(__file__).parents[2]
SEED_PATH = ROOT / "policy" / "seed-snapshot-v1.yaml"
EVENT_FIXTURE = ROOT / "tests" / "fixtures" / "policy" / "policy-updated-v2.json"
NOW = datetime(2026, 8, 23, 12, 0, tzinfo=timezone(timedelta(hours=8)))


def six_inline_packs() -> dict[str, dict]:
    return {pack.value: {} for pack in PackName}


def snapshot_payload(**overrides: object) -> dict:
    payload = {
        "version": "v1",
        "published_at": "2026-08-22T00:05:00+08:00",
        "effective_from": "2026-08-22T00:00:00+08:00",
        "published_by": "admin_seed",
        "packs": six_inline_packs(),
        "diff_from_prev": {"summary": "Initial seed", "impact": ["D1c", "C1-a"]},
        "thresholds_published": False,
    }
    payload.update(overrides)
    return payload


def proposal_payload(**overrides: object) -> dict:
    payload = {
        "created_at": "2026-08-23T10:00:00+08:00",
        "source_diff_uri": "gs://film-agent-assets/policy-diffs/diff-001.json",
        "summary": "Special-subject handling changed",
        "impact": ["D1c"],
        "effective_from": "2026-08-23T11:00:00+08:00",
        "draft_pack_updates": {"p2_subject_rules": {}},
        "status": "pending",
        "published_version": None,
    }
    payload.update(overrides)
    return payload


def event_payload(**overrides: object) -> dict:
    payload = {
        "snapshot_version": "v2",
        "impact": ["D1c"],
        "thresholds_published": True,
        "effective_from": "2026-09-01T00:00:00+08:00",
        "published_at": "2026-09-01T00:05:00+08:00",
        "idempotency_key": "policy.updated:v2",
    }
    payload.update(overrides)
    return payload


def test_snapshot_contract_requires_effective_from_and_all_six_packs() -> None:
    snapshot = PolicySnapshot.model_validate(snapshot_payload())

    assert snapshot.version == "v1"
    assert set(snapshot.packs.model_dump()) == {pack.value for pack in PackName}

    missing_effective = snapshot_payload()
    missing_effective.pop("effective_from")
    with pytest.raises(ValidationError):
        PolicySnapshot.model_validate(missing_effective)

    missing_pack = six_inline_packs()
    missing_pack.pop("p6_legal_clauses")
    with pytest.raises(ValidationError):
        PolicyPacks.model_validate(missing_pack)


@pytest.mark.parametrize("version", ["1", "v0", "v01", "latest", "v2.0"])
def test_version_contract_rejects_invalid_values(version: str) -> None:
    with pytest.raises(ValidationError):
        PolicySnapshot.model_validate(snapshot_payload(version=version))


def test_pack_is_either_inline_or_a_blob_reference() -> None:
    blob_packs = six_inline_packs()
    blob_packs["p1_form_definition"] = {"blob_uri": "gs://policy/packs/v1/p1.json"}
    packs = PolicyPacks.model_validate(blob_packs)
    assert packs.p1_form_definition == {"blob_uri": "gs://policy/packs/v1/p1.json"}

    mixed_packs = six_inline_packs()
    mixed_packs["p1_form_definition"] = {
        "blob_uri": "gs://policy/packs/v1/p1.json",
        "episode_max_minutes_exclusive": 20,
    }
    with pytest.raises(ValidationError):
        PolicyPacks.model_validate(mixed_packs)


def test_snapshot_contract_rejects_naive_datetimes() -> None:
    with pytest.raises(ValidationError):
        PolicySnapshot.model_validate(
            snapshot_payload(effective_from="2026-08-22T00:00:00")
        )


def test_proposal_contract_normalizes_impact_and_enforces_state() -> None:
    proposal = PolicyProposal.model_validate(
        proposal_payload(impact=["D1c", "D1c", "C1-a"])
    )
    assert proposal.impact == [ImpactNode.D1C, ImpactNode.C1A]

    with pytest.raises(ValidationError):
        PolicyProposal.model_validate(proposal_payload(impact=[]))
    with pytest.raises(ValidationError):
        PolicyProposal.model_validate(proposal_payload(draft_pack_updates={}))
    with pytest.raises(ValidationError):
        PolicyProposal.model_validate(proposal_payload(summary=""))
    with pytest.raises(ValidationError):
        PolicyProposal.model_validate(
            proposal_payload(status=ProposalStatus.PUBLISHED, published_version=None)
        )
    with pytest.raises(ValidationError):
        PolicyProposal.model_validate(
            proposal_payload(status=ProposalStatus.PENDING, published_version="v2")
        )


def test_policy_updated_contract_is_shared_by_producer_and_consumer() -> None:
    raw = EVENT_FIXTURE.read_text(encoding="utf-8")

    producer_event = PolicyUpdatedEvent.model_validate_json(raw)
    consumer_event = PolicyUpdatedEvent.model_validate(json.loads(raw))

    assert producer_event == consumer_event
    assert producer_event.idempotency_key == "policy.updated:v2"


@pytest.mark.parametrize(
    "overrides",
    [
        {"snapshot_version": "2", "idempotency_key": "policy.updated:2"},
        {"impact": ["P9"]},
        {"idempotency_key": "policy.updated:v3"},
    ],
)
def test_policy_updated_contract_rejects_invalid_messages(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        PolicyUpdatedEvent.model_validate(event_payload(**overrides))


def test_outbox_contract_enforces_pending_and_sent_fields() -> None:
    pending = PolicyOutbox.model_validate(
        {
            "topic": "policy.updated",
            "payload": event_payload(),
            "status": OutboxStatus.PENDING,
            "created_at": "2026-09-01T00:05:00+08:00",
            "sent_at": None,
            "pubsub_message_id": None,
        }
    )
    assert pending.sent_at is None

    with pytest.raises(ValidationError):
        PolicyOutbox.model_validate(
            {
                **pending.model_dump(),
                "status": OutboxStatus.SENT,
                "sent_at": None,
                "pubsub_message_id": None,
            }
        )


def test_recalc_tier_request_and_response_shapes_are_fixed() -> None:
    request = RecalcTierRequest.model_validate({"snapshot_version": "v2"})
    response = RecalcTierResponse.model_validate(
        {"tier": "T2", "tier_provisional": False, "changed": True}
    )

    assert request.model_dump() == {"snapshot_version": "v2"}
    assert response.model_dump() == {
        "tier": "T2",
        "tier_provisional": False,
        "changed": True,
    }

    with pytest.raises(ValidationError):
        RecalcTierRequest.model_validate({"snapshot_version": "v2", "project_id": "p1"})
    with pytest.raises(ValidationError):
        RecalcTierResponse.model_validate(
            {"tier": "T9", "tier_provisional": False, "changed": True}
        )


def test_file_snapshot_service_reads_seed_and_strict_subject_rule() -> None:
    from schemas.snapshot import FileSnapshotService

    service = FileSnapshotService(SEED_PATH)

    assert service.latest_version(as_of=NOW) == "v1"
    assert service.get_pack(PackName.P1_FORM_DEFINITION)[
        "episode_max_minutes_exclusive"
    ] == 20
    p2 = service.get_pack(PackName.P2_SUBJECT_RULES, version="v1")
    assert p2["special_subject"]["operational_basis"] == "partner_strict_rule"
    assert p2["special_subject"]["clear_hit_outcome"] == {
        "tier": "T1",
        "co_review_required": True,
    }


def test_file_snapshot_service_exposes_all_packs_and_clause() -> None:
    from schemas.snapshot import FileSnapshotService

    service = FileSnapshotService(SEED_PATH)

    for pack_name in PackName:
        assert isinstance(service.get_pack(pack_name, version="v1"), dict)

    clause = service.clause("nrta-order-16-article-5", version="v1")
    assert clause.source_url.startswith("https://www.nrta.gov.cn/")
    assert clause.title == "第五条"
    article_19 = service.clause("nrta-order-16-article-19", version="v1")
    assert "广播电视行政主管部门" in article_19.text
    assert "认为确有必要" in article_19.text


def test_returned_pack_cannot_mutate_the_versioned_snapshot() -> None:
    from schemas.snapshot import FileSnapshotService

    service = FileSnapshotService(SEED_PATH)
    returned_pack = service.get_pack(PackName.P2_SUBJECT_RULES, version="v1")

    returned_pack["special_subject"]["clear_hit_outcome"]["tier"] = "T3"

    fresh_read = service.get_pack(PackName.P2_SUBJECT_RULES, version="v1")
    assert fresh_read["special_subject"]["clear_hit_outcome"]["tier"] == "T1"


def test_future_effective_snapshot_is_not_selected(tmp_path: Path) -> None:
    from schemas.snapshot import FileSnapshotService, SnapshotNotFoundError

    future_snapshot = snapshot_payload(
        published_at="2026-09-01T00:05:00+08:00",
        effective_from="2026-09-01T00:00:00+08:00",
    )
    future_path = tmp_path / "future.yaml"
    future_path.write_text(
        yaml.safe_dump(future_snapshot, allow_unicode=True), encoding="utf-8"
    )
    service = FileSnapshotService(future_path)

    with pytest.raises(SnapshotNotFoundError, match="SNAPSHOT_NOT_FOUND"):
        service.latest_version(as_of=NOW)

    assert service.latest_version(
        as_of=datetime(2026, 9, 1, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    ) == "v1"
