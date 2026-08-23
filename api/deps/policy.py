"""Process-scoped deterministic policy administration state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Header, Request

from api.errors import PolicyApiError
from schemas.policy_snapshot import ImpactNode, PackName
from workers.policy.adapters.file_blob import FileBlobStore
from workers.policy.launch import PolicyRunLauncher
from workers.policy.local_demo import build_local_policy_loop
from workers.policy.models import PolicySource, ProposalDraft
from workers.policy.outbox import OutboxDispatcher
from workers.policy.publish import PolicyPublisher
from workers.policy.repository import InMemoryPolicyRepository


ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "policy"
SOURCE_ID = "nrta_micro_drama"
SOURCE = PolicySource(
    source_id=SOURCE_ID,
    url="https://www.nrta.gov.cn/example",
    content_selector="#zoom",
    enabled=True,
)
DEMO_EFFECTIVE_FROM = datetime(
    2026,
    8,
    22,
    0,
    0,
    tzinfo=timezone(timedelta(hours=8)),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PolicyApiState:
    repository: InMemoryPolicyRepository
    launcher: PolicyRunLauncher
    publisher: PolicyPublisher
    dispatcher: OutboxDispatcher
    blob_store: FileBlobStore
    clock: Callable[[], datetime]


async def build_local_policy_api_state(
    blob_root: Path,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> PolicyApiState:
    now = clock()
    loop = build_local_policy_loop(
        source=SOURCE,
        fixture_path=FIXTURES / "source-v1.html",
        blob_root=blob_root,
        seed_path=ROOT / "policy" / "seed-snapshot-v1.yaml",
        proposal_draft=ProposalDraft(
            summary="分类标准正式公布",
            impact=[ImpactNode.D1C],
            effective_from=DEMO_EFFECTIVE_FROM,
            draft_pack_updates={
                PackName.P3_TIER_THRESHOLDS: {
                    "thresholds_published": True
                }
            },
        ),
        now=now,
        recalculated_tier="T2",
    )
    loop.policy.create_run("run_baseline", SOURCE_ID, now)
    await loop.refresh.run("run_baseline", SOURCE_ID, now)
    loop.fetcher.set_path(SOURCE_ID, FIXTURES / "source-v2.html")
    return PolicyApiState(
        repository=loop.policy,
        launcher=PolicyRunLauncher(loop.policy, loop.refresh, {SOURCE_ID}),
        publisher=loop.publisher,
        dispatcher=OutboxDispatcher(
            loop.policy,
            loop.event_publisher,
            clock=clock,
        ),
        blob_store=loop.blob_store,
        clock=clock,
    )


def get_policy_state(request: Request) -> PolicyApiState:
    return request.app.state.policy


def require_admin(x_mock_role: str | None = Header(default=None)) -> None:
    if x_mock_role != "admin":
        raise PolicyApiError(
            403,
            "POLICY_ADMIN_FORBIDDEN",
            "admin role required",
        )
