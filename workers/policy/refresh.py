"""Policy source refresh orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from schemas.policy_snapshot import PolicyProposal, ProposalStatus

from .models import (
    BlobRef,
    FetchedSource,
    PolicyDiff,
    PolicySource,
    ProposalDraft,
    ProposalRequest,
    RefreshResult,
    SourceState,
)
from .normalize import create_policy_diff, normalize_html
from .repository import InMemoryPolicyRepository


class SourceFetcher(Protocol):
    async def fetch(self, source: PolicySource) -> FetchedSource: ...


class BlobStore(Protocol):
    def put_raw(
        self, source_id: str, content: bytes, fetched_at: datetime
    ) -> BlobRef: ...

    def put_normalized(
        self, source_id: str, text: str, fetched_at: datetime
    ) -> BlobRef: ...

    def put_diff(
        self, source_id: str, diff: PolicyDiff, created_at: datetime
    ) -> BlobRef: ...

    def read_text(self, uri: str) -> str: ...


class ProposalModel(Protocol):
    async def draft(self, request: ProposalRequest) -> ProposalDraft: ...


class PolicyRefreshError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class PolicyRefreshModule:
    def __init__(
        self,
        *,
        sources: dict[str, PolicySource],
        fetcher: SourceFetcher,
        blob_store: BlobStore,
        proposal_model: ProposalModel,
        repository: InMemoryPolicyRepository,
    ) -> None:
        self._sources = dict(sources)
        self._fetcher = fetcher
        self._blob_store = blob_store
        self._proposal_model = proposal_model
        self._repository = repository

    async def run(
        self, run_id: str, source_id: str, now: datetime
    ) -> RefreshResult:
        try:
            source = self._sources[source_id]
            if not source.enabled:
                raise KeyError(source_id)
            fetched = await self._fetcher.fetch(source)
            raw_ref = self._blob_store.put_raw(source_id, fetched.content, now)
            normalized = normalize_html(fetched.content, source.content_selector)
            normalized_ref = self._blob_store.put_normalized(
                source_id, normalized, now
            )
            previous_state = self._repository.get_source_state(source_id)

            if previous_state is None:
                return self._complete_no_change(
                    run_id, source_id, now, raw_ref.uri, normalized_ref, None
                )
            if previous_state.normalized_sha256 == normalized_ref.sha256:
                return self._complete_no_change(
                    run_id,
                    source_id,
                    now,
                    raw_ref.uri,
                    normalized_ref,
                    previous_state.normalized_sha256,
                )

            previous_text = self._blob_store.read_text(
                previous_state.normalized_uri
            )
            diff = create_policy_diff(source_id, previous_text, normalized)
            diff_ref = self._blob_store.put_diff(source_id, diff, now)
            draft = await self._proposal_model.draft(
                ProposalRequest(
                    source_url=fetched.source_url,
                    previous_sha256=diff.previous_sha256,
                    current_sha256=diff.current_sha256,
                    unified_diff=diff.unified_diff,
                )
            )
            proposal = PolicyProposal(
                created_at=now,
                source_diff_uri=diff_ref.uri,
                summary=draft.summary,
                impact=draft.impact,
                effective_from=draft.effective_from,
                draft_pack_updates=draft.draft_pack_updates,
                status=ProposalStatus.PENDING,
                published_version=None,
            )
            proposal_id = self._repository.commit_refresh_proposal(
                run_id=run_id,
                source_id=source_id,
                proposal=proposal,
                source_state=SourceState(
                    last_success_at=now,
                    raw_uri=raw_ref.uri,
                    normalized_uri=normalized_ref.uri,
                    normalized_sha256=normalized_ref.sha256,
                ),
                finished_at=now,
                previous_sha256=previous_state.normalized_sha256,
                current_sha256=normalized_ref.sha256,
            )
            return RefreshResult(
                run_id=run_id,
                status="proposal_created",
                proposal_id=proposal_id,
                previous_sha256=previous_state.normalized_sha256,
                current_sha256=normalized_ref.sha256,
            )
        except Exception as exc:
            code = getattr(exc, "code", "POLICY_REFRESH_FAILED")
            self._repository.fail_run(run_id, f"{code}: {exc}", now)
            raise PolicyRefreshError(code, str(exc)) from exc

    def _complete_no_change(
        self,
        run_id: str,
        source_id: str,
        now: datetime,
        raw_uri: str,
        normalized_ref: BlobRef,
        previous_sha256: str | None,
    ) -> RefreshResult:
        self._repository.commit_refresh_no_change(
            run_id=run_id,
            source_id=source_id,
            source_state=SourceState(
                last_success_at=now,
                raw_uri=raw_uri,
                normalized_uri=normalized_ref.uri,
                normalized_sha256=normalized_ref.sha256,
            ),
            finished_at=now,
            previous_sha256=previous_sha256,
            current_sha256=normalized_ref.sha256,
        )
        return RefreshResult(
            run_id=run_id,
            status="no_change",
            proposal_id=None,
            previous_sha256=previous_sha256,
            current_sha256=normalized_ref.sha256,
        )
