from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.clock import FixedClock
from core.llm import UnavailableLLM
from core.workflow_service import WorkflowService
from schemas.enums import AmountBracket, ClaimedFormType, Tier
from schemas.policy_snapshot import (
    PackName,
    PolicyPacks,
    PolicySnapshot,
    VerificationStatus,
)
from store.memory import InMemoryStores
from workers.policy.adapters.repository_snapshot import RepositorySnapshotService
from workers.policy.repository import InMemoryPolicyRepository


ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)


def test_recalc_uses_the_stored_amount_and_selected_evidence():
    raw = yaml.safe_load(
        (ROOT / "policy" / "seed-snapshot-v1.yaml").read_text(encoding="utf-8")
    )
    seed = PolicySnapshot.model_validate(raw)
    repository = InMemoryPolicyRepository()
    repository.put_snapshot(seed)
    snapshots = RepositorySnapshotService(repository)
    workflow = WorkflowService(
        InMemoryStores(), snapshots, FixedClock(NOW), UnavailableLLM()
    )

    project = workflow.create_project("u_owner", "Exact amount")
    workflow.submit_intent(
        project.project_id,
        {
            "form_type_claimed": ClaimedFormType.MICRO_DRAMA,
            "synopsis": "A general workplace romance.",
            "episode_count": 30,
            "episode_minutes": 2,
            "amount_bracket": AmountBracket.BELOW_LOWER,
            "investment_amount_rmb": 1_500_000,
        },
    )
    project, _ = workflow.run_classification(project.project_id)
    assert project.classification.tier_provisional is True
    assert (
        project.classification.policy_verification_status
        is VerificationStatus.MOCK_VERIFIED
    )

    packs = seed.packs.model_dump(mode="python")
    packs[PackName.P3_TIER_THRESHOLDS.value] = {
        "thresholds_published": True,
        "threshold_sets": {
            "live_action": {
                "effective_from": "2026-01-01T00:00:00+08:00",
                "T1_min_rmb": 3_000_000,
                "T2_min_rmb": 1_000_000,
                "clause_ref": "tier-ai-generated-2026",
            },
            "ai_generated": {
                "effective_from": "2026-07-01T00:00:00+08:00",
                "T1_min_rmb": 800_000,
                "T2_min_rmb": 300_000,
                "clause_ref": "tier-ai-generated-2026",
            },
        },
    }
    legal = dict(packs[PackName.P6_LEGAL_CLAUSES.value])
    legal["clauses"] = [
        *legal.get("clauses", []),
        {
            "clause_id": "tier-ai-generated-2026",
            "title": "2026 live-action micro-drama thresholds",
            "text": "T1 starts at RMB 3,000,000 and T2 starts at RMB 1,000,000.",
            "source_url": "https://whhlyj.baoji.gov.cn/zzzb/xygl/202601/t20260115_1240723.html",
        },
        {
            "clause_id": "tier-ai-generated-2026",
            "title": "2026 AI-generated micro-drama thresholds",
            "text": "T1 starts at RMB 800,000 and T2 starts at RMB 300,000.",
            "source_url": "https://wxb.xzdw.gov.cn/wlcb/cbgz/202606/t20260626_680352.html",
        },
    ]
    packs[PackName.P6_LEGAL_CLAUSES.value] = legal
    data = seed.model_dump(mode="python")
    data.update(
        version="v2",
        published_at=NOW,
        effective_from=NOW,
        published_by="admin_richard",
        packs=PolicyPacks.model_validate(packs),
        thresholds_published=True,
        verification_status=VerificationStatus.HUMAN_VERIFIED,
    )
    repository.put_snapshot(PolicySnapshot.model_validate(data))

    result = workflow.recalc_tier(project.project_id, "v2")
    updated = workflow.get_project(project.project_id)

    # 1,500,000 clears the AI one-class line of 800,000.
    assert result.tier is Tier.T1
    assert result.tier_provisional is False
    assert result.changed is True
    assert updated.classification.policy_snapshot_version == "v2"
    assert (
        updated.classification.policy_verification_status
        is VerificationStatus.HUMAN_VERIFIED
    )
    assert (
        updated.classification.evidence_refs[0].clause_id
        == "tier-ai-generated-2026"
    )
