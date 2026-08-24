"""WorkflowService: the only writer of project state (ground rule 1).

Agents and routers call these methods; they never mutate a project document
directly, and every state change goes through `state_machine.transition()`.
"""

from __future__ import annotations

from dataclasses import dataclass

from schemas.common import AuditEntry, Fact, SourceRef, TimelineEvent
from schemas.enums import (
    Actor,
    BudgetBand,
    FactStatus,
    FindingSeverity,
    ProjectState,
    SourceRefType,
    Tier,
)
from schemas.findings import Finding, Locator
from schemas.policy_snapshot import PackName
from schemas.project import ChannelProfile, IntentProfile, Project, TracksEnabled
from schemas.snapshot import SnapshotService

from .classify import classify
from .classify.chain import ClassificationOutcome
from .classify.d1c import judge_tier
from .clock import Clock
from .errors import NotFoundError, StateInvalidError
from .gate import GateResult, evaluate_gate_d3
from .ids import new_id
from .llm import LLMClient
from .state_machine import GateContext, transition

# States where a recalculation must not touch anything any more.
RECALC_FROZEN_STATES = frozenset(
    {
        ProjectState.FORM_FROZEN,
        ProjectState.INSTITUTION_REVIEW,
        ProjectState.INSTITUTION_RETURNED,
        ProjectState.READY_FOR_EXTERNAL_FILING,
        ProjectState.FILED,
        ProjectState.PRODUCTION,
    }
)


@dataclass
class RecalcResult:
    tier: Tier
    tier_provisional: bool
    changed: bool
    reason: str | None = None


class WorkflowService:
    def __init__(
        self,
        stores,
        snapshots: SnapshotService,
        clock: Clock,
        llm: LLMClient | None = None,
    ) -> None:
        self._stores = stores
        self._snapshots = snapshots
        self._clock = clock
        self._llm = llm

    # ------------------------------------------------------------------ reads

    def get_project(self, project_id: str) -> Project:
        project = self._stores.projects.get(project_id)
        if project is None:
            raise NotFoundError(f"project not found: {project_id}", {"project_id": project_id})
        return project

    def gate_report(self, project_id: str) -> GateResult:
        project = self.get_project(project_id)
        version = (
            project.classification.policy_snapshot_version
            if project.classification
            else self._snapshots.latest_version()
        )
        form_pack = self._snapshots.get_pack(PackName.P5_FORM_TEMPLATES, version)
        return evaluate_gate_d3(
            project,
            self._stores.findings.list(project_id),
            self._stores.facts.list(project_id),
            self._stores.materials.list(project_id),
            form_pack,
        )

    # ----------------------------------------------------------------- writes

    def create_project(self, owner_uid: str, title_working: str | None = None) -> Project:
        now = self._clock.now()
        project = Project(
            project_id=new_id("project"),
            owner_uid=owner_uid,
            title_working=title_working,
            created_at=now,
            updated_at=now,
        )
        self._stores.projects.create(project)
        self._record_event(
            project.project_id, Actor.CREATOR, "project.created", {"owner_uid": owner_uid}
        )
        return project

    def submit_intent(self, project_id: str, patch: dict) -> tuple[Project, list[str]]:
        """S1. Partial submissions are allowed; unknown stays unknown."""

        project = self.get_project(project_id)
        merged = project.intent_profile.model_dump()
        merged.update({key: value for key, value in patch.items() if key in merged})
        intent = IntentProfile.model_validate(merged)

        project = project.model_copy(
            update={"intent_profile": intent, "updated_at": self._clock.now()}
        )
        if project.state is ProjectState.DRAFT:
            project = self._transition(
                project, ProjectState.INTAKE_DONE, Actor.CREATOR, "intent.submitted"
            )
        else:
            self._stores.projects.save(project)
            self._record_event(project_id, Actor.CREATOR, "intent.updated", {})
        return project, intent.missing_fields()

    def submit_channels(self, project_id: str, patch: dict) -> Project:
        """S2. Enabling the US track is a channel fact, not an LLM decision."""

        project = self.get_project(project_id)
        merged = project.channel_profile.model_dump()
        merged.update({key: value for key, value in patch.items() if key in merged})
        channels = ChannelProfile.model_validate(merged)
        channels = channels.model_copy(
            update={
                "tracks_enabled": TracksEnabled(
                    china=True, us=bool(channels.overseas)
                )
            }
        )
        project = project.model_copy(
            update={"channel_profile": channels, "updated_at": self._clock.now()}
        )
        self._stores.projects.save(project)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "channels.updated",
            {"tracks_enabled": channels.tracks_enabled.model_dump()},
        )
        return project

    def run_classification(self, project_id: str) -> tuple[Project, ClassificationOutcome]:
        """S3: D1a -> D1b -> D1c, synchronous, one pinned snapshot version."""

        project = self.get_project(project_id)
        if project.state is ProjectState.DRAFT:
            raise StateInvalidError(
                "intent must be submitted before classification",
                {"state": project.state.value},
            )

        outcome = classify(
            project.intent_profile,
            project.channel_profile,
            self._snapshots,
            llm=self._llm,
            thresholds_published=self._thresholds_published(),
        )

        if outcome.ask_back:
            raise StateInvalidError(
                "classification needs more intent answers",
                {"missing": outcome.ask_back},
            )

        project = self._persist_classification(project, outcome)
        return project, outcome

    def choose_tier(self, project_id: str, budget_band: BudgetBand) -> tuple[Project, ClassificationOutcome]:
        """User picks a budget band -> D1c runs again on the same chain."""

        project, _ = self.submit_intent(project_id, {"budget_band": budget_band})
        return self.run_classification(project.project_id)

    def recalc_tier(self, project_id: str, snapshot_version: str) -> RecalcResult:
        """Internal, called by the policy update consumer.

        Contract: recalculate only provisional tiers, and never touch a frozen
        form, submitted materials, or a registration number.
        """

        project = self.get_project(project_id)
        classification = project.classification

        if classification is None:
            return RecalcResult(Tier.UNDETERMINED, False, False, "not_classified")
        if project.state in RECALC_FROZEN_STATES or project.registration_number:
            return RecalcResult(
                classification.tier, classification.tier_provisional, False, "frozen"
            )
        if not classification.tier_provisional:
            return RecalcResult(
                classification.tier, classification.tier_provisional, False, "not_provisional"
            )

        pack3 = self._snapshots.get_pack(PackName.P3_TIER_THRESHOLDS, snapshot_version)
        decision = judge_tier(
            project.intent_profile.budget_band,
            pack3,
            self._thresholds_published(snapshot_version),
        )
        changed = (
            decision.tier != classification.tier
            or decision.tier_provisional != classification.tier_provisional
        )

        updated_classification = classification.model_copy(
            update={
                "tier": decision.tier,
                "tier_provisional": decision.tier_provisional,
                "policy_snapshot_version": snapshot_version,
                "pending_flags": sorted(
                    set(classification.pending_flags) - {"amount_official"}
                    | set(decision.pending_flags)
                ),
            }
        )
        project = project.model_copy(
            update={
                "classification": updated_classification,
                "policy_stale": False,
                "updated_at": self._clock.now(),
            }
        )
        self._stores.projects.save(project)
        self._record_event(
            project_id,
            Actor.SYSTEM,
            "classification.recalculated",
            {
                "snapshot_version": snapshot_version,
                "tier": decision.tier.value,
                "tier_provisional": decision.tier_provisional,
                "changed": changed,
            },
        )
        return RecalcResult(decision.tier, decision.tier_provisional, changed)

    def mark_policy_stale(self, project_id: str, snapshot_version: str) -> Project:
        """Flag only. Frozen forms and filed data are never rewritten."""

        project = self.get_project(project_id)
        project = project.model_copy(
            update={"policy_stale": True, "updated_at": self._clock.now()}
        )
        self._stores.projects.save(project)
        self._record_event(
            project_id,
            Actor.SYSTEM,
            "policy.stale",
            {"snapshot_version": snapshot_version},
        )
        return project

    # --------------------------------------------------------------- internals

    def _thresholds_published(self, version: str | None = None) -> bool | None:
        pack = self._snapshots.get_pack(PackName.P3_TIER_THRESHOLDS, version)
        if "official_published" in pack:
            return bool(pack["official_published"])
        thresholds = pack.get("thresholds")
        return bool(thresholds)

    def _persist_classification(
        self, project: Project, outcome: ClassificationOutcome
    ) -> Project:
        now = self._clock.now()
        classification = outcome.classification
        if classification is not None:
            classification = classification.model_copy(update={"decided_at": now})
            project = project.model_copy(
                update={"classification": classification, "updated_at": now}
            )
            self._stores.projects.save(project)

        for proposed in outcome.facts:
            self._upsert_fact(project.project_id, proposed.key, proposed.value, proposed.source_ref)

        if outcome.alert is not None:
            self._write_alert_finding(project, outcome)

        target = outcome.next_state
        if target is None:
            return project

        if project.state is ProjectState.INTAKE_DONE and target in (
            ProjectState.CLASSIFIED,
            ProjectState.NEEDS_HUMAN_SUBJECT,
        ):
            project = self._transition(
                project, ProjectState.FORM_JUDGED, Actor.SYSTEM, "d1a.form_type_decided"
            )

        if project.state is not target:
            project = self._transition(
                project, target, Actor.SYSTEM, "classification.decided",
                detail={"reasons": outcome.reasons},
            )
        else:
            self._record_event(
                project.project_id,
                Actor.SYSTEM,
                "classification.rerun",
                {"reasons": outcome.reasons},
            )
        return project

    def _write_alert_finding(self, project: Project, outcome: ClassificationOutcome) -> None:
        quote = ""
        if outcome.classification and outcome.classification.matched_rules:
            quote = outcome.classification.matched_rules[0].quote
        finding = Finding(
            finding_id=new_id("finding"),
            asset_version="intent_profile",
            locator=Locator(quote=quote or (project.intent_profile.logline or "")),
            category=outcome.alert_category or "subject_edge_case",
            severity=outcome.alert_severity or FindingSeverity.NEEDS_HUMAN,
            evidence_refs=list(outcome.classification.evidence_refs)
            if outcome.classification
            else [],
            alert=outcome.alert,
            snapshot_version=outcome.classification.policy_snapshot_version
            if outcome.classification
            else None,
            created_at=self._clock.now(),
        )
        self._stores.findings.add(project.project_id, finding)
        self._record_event(
            project.project_id,
            Actor.SYSTEM,
            "finding.alert_created",
            {"finding_id": finding.finding_id, "category": finding.category},
        )

    def _upsert_fact(
        self, project_id: str, key: str, value, source_ref: SourceRef
    ) -> Fact:
        existing = self._stores.facts.get_by_key(project_id, key)
        if existing is not None and existing.value == value:
            return existing

        status = FactStatus.CONFIRMED
        conflicts_with = None
        if existing is not None and existing.source_ref.type is SourceRefType.ASSET:
            # An asset-derived fact outranks a self-reported answer: keep both and
            # let the review loop resolve the conflict.
            status = FactStatus.CONFLICT
            conflicts_with = existing.fact_id

        fact = Fact(
            fact_id=new_id("fact"),
            key=key,
            value=value,
            source_ref=source_ref,
            status=status,
            conflicts_with=conflicts_with,
            created_at=self._clock.now(),
        )
        return self._stores.facts.add(project_id, fact)

    def _transition(
        self,
        project: Project,
        to_state: ProjectState,
        actor: Actor,
        reason: str,
        detail: dict | None = None,
    ) -> Project:
        gate_context = None
        if to_state is ProjectState.GATE_D3_PASSED:
            version = (
                project.classification.policy_snapshot_version
                if project.classification
                else self._snapshots.latest_version()
            )
            gate_context = GateContext(
                findings=self._stores.findings.list(project.project_id),
                facts=self._stores.facts.list(project.project_id),
                materials=self._stores.materials.list(project.project_id),
                form_pack=self._snapshots.get_pack(PackName.P5_FORM_TEMPLATES, version),
            )

        result = transition(
            project,
            to_state,
            actor=actor,
            reason=reason,
            clock=self._clock,
            detail=detail,
            gate_context=gate_context,
        )
        self._stores.projects.save(result.project)
        self._stores.audit.add(project.project_id, result.audit)
        self._stores.timeline.add(project.project_id, result.timeline)
        return result.project

    def _record_event(
        self, project_id: str, actor: Actor, event: str, detail: dict
    ) -> TimelineEvent:
        entry = TimelineEvent(
            event_id=new_id("event"),
            at=self._clock.now(),
            actor=actor,
            event=event,
            detail=detail,
        )
        return self._stores.timeline.add(project_id, entry)


__all__ = ["WorkflowService", "RecalcResult", "AuditEntry"]
