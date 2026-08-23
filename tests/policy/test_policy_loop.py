import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from schemas.policy_snapshot import OutboxStatus, PackName, ProposalStatus
from workers.policy.adapters.memory_projects import ProjectPolicyState
from workers.policy.local_demo import build_local_policy_loop
from workers.policy.models import PolicySource, ProposalDraft


ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "policy"
NOW = datetime(2026, 8, 23, 19, 0, tzinfo=timezone(timedelta(hours=8)))


def test_offline_policy_loop_completes_twelve_step_acceptance(tmp_path: Path) -> None:
    loop = build_local_policy_loop(
        source=PolicySource(
            source_id="nrta_micro_drama",
            url="https://www.nrta.gov.cn/example",
            content_selector="#zoom",
            enabled=True,
        ),
        fixture_path=FIXTURES / "source-v1.html",
        blob_root=tmp_path / "blobs",
        seed_path=ROOT / "policy" / "seed-snapshot-v1.yaml",
        proposal_draft=ProposalDraft(
            summary="分类标准正式公布",
            impact=["D1c"],
            effective_from=NOW,
            draft_pack_updates={
                PackName.P3_TIER_THRESHOLDS: {"thresholds_published": True}
            },
        ),
        now=NOW,
        recalculated_tier="T2",
    )
    assert loop.policy.get_snapshot("v1").thresholds_published is False

    loop.projects.add_project(
        ProjectPolicyState(
            project_id="project_provisional",
            policy_snapshot_version="v1",
            impact_nodes=["D1c"],
            has_classification=True,
            has_review=False,
            tier="T3",
            tier_provisional=True,
            workflow_status="DRAFT",
            policy_stale=False,
            frozen_form_hash=None,
            submitted_materials=[],
            registration_number=None,
        )
    )
    loop.projects.add_project(
        ProjectPolicyState(
            project_id="project_frozen",
            policy_snapshot_version="v1",
            impact_nodes=["D1c"],
            has_classification=True,
            has_review=True,
            tier="T1",
            tier_provisional=False,
            workflow_status="FILED",
            policy_stale=False,
            frozen_form_hash="sha256:immutable-form",
            submitted_materials=["materials/filed.pdf"],
            registration_number="REG-FILED-001",
        )
    )
    frozen_before = loop.projects.get_project("project_frozen")

    loop.policy.create_run("run_001", "nrta_micro_drama", NOW)
    baseline = asyncio.run(loop.refresh.run("run_001", "nrta_micro_drama", NOW))
    assert baseline.status == "no_change"

    loop.fetcher.set_path("nrta_micro_drama", FIXTURES / "source-v2.html")
    loop.policy.create_run("run_002", "nrta_micro_drama", NOW)
    changed = asyncio.run(loop.refresh.run("run_002", "nrta_micro_drama", NOW))
    proposal = loop.policy.get_proposal(changed.proposal_id)
    assert changed.status == "proposal_created"
    assert proposal.status is ProposalStatus.PENDING
    assert proposal.summary == "分类标准正式公布"
    assert proposal.effective_from == NOW

    published = loop.publisher.publish(changed.proposal_id, "admin_richard", NOW)
    pending = loop.policy.get_outbox(published.outbox_id)
    assert published.snapshot_version == "v2"
    assert pending.status is OutboxStatus.PENDING

    dispatched = loop.dispatcher.dispatch()
    assert dispatched.sent == 1
    assert loop.policy.get_outbox(published.outbox_id).status is OutboxStatus.SENT
    delivered_event = loop.event_publisher.published[0]

    consumed = asyncio.run(loop.consumer.handle(delivered_event))
    provisional = loop.projects.get_project("project_provisional")
    frozen_after = loop.projects.get_project("project_frozen")
    assert consumed.recalculated == 1
    assert provisional.tier == "T2"
    assert provisional.tier_provisional is False
    assert (
        "policy.updated:v2:project_provisional:tier_recalculated"
        in loop.projects.notifications
    )
    assert frozen_after.policy_stale is True
    assert (
        "policy.updated:v2:project_frozen:policy_stale"
        in loop.projects.notifications
    )
    assert frozen_after.frozen_form_hash == frozen_before.frozen_form_hash
    assert frozen_after.submitted_materials == frozen_before.submitted_materials
    assert frozen_after.registration_number == frozen_before.registration_number

    notification_count = len(loop.projects.notifications)
    timeline_count = len(loop.projects.timeline)
    replay = asyncio.run(loop.consumer.handle(delivered_event))
    assert replay.already_processed is True
    assert len(loop.projects.notifications) == notification_count
    assert len(loop.projects.timeline) == timeline_count
    assert loop.recalc.calls == [("project_provisional", "v2")]
