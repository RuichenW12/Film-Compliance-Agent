"""WorkflowService: the only writer of project state (ground rule 1).

Agents and routers call these methods; they never mutate a project document
directly, and every state change goes through `state_machine.transition()`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from schemas.assets import AssetVersion, MaterialCard, UploadTicket
from schemas.common import AuditEntry, EvidenceRef, Fact, SourceRef, TimelineEvent
from schemas.enums import (
    Actor,
    TaskStatus,
    TaskType,
    InstitutionDecision,
    AlertOption,
    AssetKind,
    FindingStatus,
    MaterialStatus,
    AmountBracket,
    FactStatus,
    FindingSeverity,
    NotificationKind,
    ProjectState,
    SourceRefType,
    Tier,
)
from schemas.findings import Finding, Locator
from schemas.forms import FormDraft
from schemas.policy_snapshot import PackName
from schemas.project import (
    ChannelProfile,
    IntentProfile,
    Project,
    Roadmap,
    TracksEnabled,
)
from schemas.snapshot import SnapshotService
from schemas.workflow import (
    InstitutionReview,
    MockInstitution,
    Notification,
    WorkflowTask,
)

from .classify import classify
from .classify.chain import ROADMAP_TEMPLATE_BY_TIER
from .classify.subject_rules import load_subject_rules
from .classify.chain import ClassificationOutcome
from .classify.d1c import PUBLISHED_KEYS, judge_tier
from .clock import Clock
from .extract import extract_facts
from .errors import (
    GateBlockedError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    StateInvalidError,
    ValidationFailedError,
)
from .forms import build_fields, deferred_keys, draft_hash, pending_keys
from .gate import GateResult, evaluate_gate_d3, required_fact_keys
from .institution import check_licence
from .jobs import InlineRunner, JobOutcome, JobRunner, idempotency_key
from .ids import new_id
from .llm import LLMClient
from .materials import build_material_cards
from .review import SCRIPT_REVIEW_PROMPT_VERSION, evidence_for, review_script
from .roadmap import build_roadmap
from .teaser import PENDING_FLAG as TEASER_PENDING
from .teaser import PROMPT_VERSION as TEASER_PROMPT_VERSION
from .teaser import VideoBackend, build_request
from .state_machine import GateContext, transition

# The gate is only reachable once a pre-check has run: collect, review, gate.
GATE_READY_STATES = frozenset(
    {ProjectState.REVIEW_RUNNING, ProjectState.REVISION_LOOP}
)

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
        video: VideoBackend | None = None,
        jobs: JobRunner | None = None,
    ) -> None:
        self._stores = stores
        self._snapshots = snapshots
        self._clock = clock
        self._llm = llm
        self._video = video
        self._jobs = jobs or InlineRunner()

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
            # Through material_cards, so a pack-defined card blocks the gate
            # even if nobody has opened the collection page yet.
            self.material_cards(project_id),
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

    # States where re-deciding a classification is safe. Everything from
    # FORM_FROZEN onward is missing on purpose: once a form has been locked and
    # sent, its class is part of what the filing company is reviewing, and
    # changing it under them would make the document they hold describe a
    # different project. A stale project that far along goes round the revision
    # loop instead, which is visible to both sides.
    RECLASSIFIABLE_STATES = (
        ProjectState.CLASSIFIED,
        ProjectState.ROADMAP_CONFIRMED,
        ProjectState.COLLECTING_MATERIALS,
        ProjectState.REVIEW_RUNNING,
        ProjectState.REVISION_LOOP,
        ProjectState.GATE_D3_PASSED,
        ProjectState.NEEDS_HUMAN_SUBJECT,
        ProjectState.NEEDS_HUMAN_FORMTYPE,
    )

    def reclassify(self, project_id: str) -> tuple[Project, ClassificationOutcome]:
        """Re-run the whole chain against the current snapshot, on request.

        A policy change marks a project stale. For a threshold change the tier
        is recalculated automatically, because `recalc_tier` can answer that
        question from the amount alone. For a subject-rule change it is not
        (D-050) -- re-deciding a subject match needs D1a, D1b and D1c together
        and a human who asked for it. Which left a stale project with nowhere
        to go: it was told its answer rested on rules that had moved, and had
        no way to get a new answer.

        This is that way. The creator asks, the full chain runs against the
        pinned-now snapshot, and the flag clears.

        Unlike `run_classification` this never moves the state. Re-deciding is
        not starting over: a project halfway through collecting materials keeps
        its materials, its roadmap and its uploads, and only its classification
        is replaced.
        """

        project = self.get_project(project_id)
        if not project.policy_stale:
            raise StateInvalidError(
                "this project is not marked stale, so there is nothing to redo",
                {"state": project.state.value},
            )
        if project.state not in self.RECLASSIFIABLE_STATES:
            raise StateInvalidError(
                "a form that has been locked cannot be re-decided in place",
                {"state": project.state.value},
            )

        before = project.classification
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
        if outcome.classification is None:
            raise StateInvalidError(
                "the chain produced no classification to record",
                {"state": project.state.value},
            )

        now = self._clock.now()
        project = project.model_copy(
            update={
                "classification": outcome.classification.model_copy(
                    update={"decided_at": now}
                ),
                "policy_stale": False,
                "updated_at": now,
            }
        )
        self._stores.projects.save(project)

        for proposed in outcome.facts:
            self._upsert_fact(
                project_id, proposed.key, proposed.value, proposed.source_ref
            )

        # What changed, in the timeline, so a later reader can see that the
        # answer moved and what moved it.
        self._record_event(
            project_id,
            Actor.CREATOR,
            "classification.rerun_after_policy_change",
            {
                "from_snapshot": before.policy_snapshot_version if before else None,
                "to_snapshot": outcome.classification.policy_snapshot_version,
                "from_tier": before.tier.value if before else None,
                "to_tier": outcome.classification.tier.value,
                "changed": bool(before) and before.tier is not outcome.classification.tier,
            },
        )
        return project, outcome

    def choose_tier(self, project_id: str, amount_bracket: AmountBracket) -> tuple[Project, ClassificationOutcome]:
        """User picks a budget band -> D1c runs again on the same chain."""

        project, _ = self.submit_intent(project_id, {"amount_bracket": amount_bracket})
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
            project.intent_profile.amount_bracket,
            pack3,
            self._thresholds_published(snapshot_version),
            investment_amount_rmb=project.intent_profile.investment_amount_rmb,
            is_ai_generated=project.intent_profile.is_ai_generated,
        )
        changed = (
            decision.tier != classification.tier
            or decision.tier_provisional != classification.tier_provisional
        )

        classification_updates = {
            "tier": decision.tier,
            "tier_provisional": decision.tier_provisional,
            "policy_snapshot_version": snapshot_version,
            "policy_verification_status": self._snapshots.verification_status(
                snapshot_version
            ),
            "pending_flags": sorted(
                set(classification.pending_flags) - {"amount_official"}
                | set(decision.pending_flags)
            ),
        }
        if decision.clause_ref:
            classification_updates["evidence_refs"] = [
                EvidenceRef(
                    snapshot_version=snapshot_version,
                    clause_id=decision.clause_ref,
                )
            ]
        updated_classification = classification.model_copy(
            update=classification_updates
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
        # Re-running the same snapshot is not news. Only a real change is.
        if changed:
            self._notify(
                project,
                NotificationKind.TIER_RECALCULATED,
                {
                    "snapshot_version": snapshot_version,
                    "tier": decision.tier.value,
                    "tier_provisional": decision.tier_provisional,
                    "previous_tier": classification.tier.value,
                },
            )
        return RecalcResult(decision.tier, decision.tier_provisional, changed)

    def mark_policy_stale(self, project_id: str, snapshot_version: str) -> Project:
        """Flag only. Frozen forms and filed data are never rewritten."""

        project = self.get_project(project_id)
        already_stale = project.policy_stale
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
        # Redelivery must not refill the inbox: the consumer retries, the
        # creator should still see one notice per stale flag.
        if not already_stale:
            self._notify(
                project,
                NotificationKind.POLICY_STALE,
                {"snapshot_version": snapshot_version},
            )
        return project

    # --------------------------------------------------------- script review

    def run_script_review(self, project_id: str):
        """C1-a over the latest script version, recorded as a review task.

        The first review of a version is `review_full`; a later one is
        `review_incremental`, since prior findings carry forward. Both are keyed
        on the asset version, so a redelivery returns the first task.
        """

        asset = self._latest_script(project_id)
        if asset is None:
            raise NotFoundError(
                "this project has no uploaded script to review",
                {"project_id": project_id},
            )
        # Incremental means "relative to an earlier version", not "findings
        # already exist". Deciding it from findings made the job type flip
        # between two runs of the same version, which changed the idempotency
        # key and let a replay review the same script twice.
        earlier_review = any(
            task.type in (TaskType.REVIEW_FULL, TaskType.REVIEW_INCREMENTAL)
            and task.payload.get("asset_version") != asset.version_id
            for task in self._stores.tasks.list(project_id)
        )
        task_type = (
            TaskType.REVIEW_INCREMENTAL if earlier_review else TaskType.REVIEW_FULL
        )

        holder: list = []

        def work() -> JobOutcome:
            project, written, result = self._review_now(project_id)
            holder.append((project, written, result))
            return JobOutcome(
                result={
                    "finding_count": len(written),
                    "discarded": result.discarded,
                    "backend": result.backend,
                },
                status=TaskStatus.NEEDS_HUMAN
                if result.pending_flags
                else TaskStatus.SUCCEEDED,
                error=result.pending_flags[0] if result.pending_flags else None,
            )

        self._run_job(
            project_id,
            task_type,
            asset.version_id,
            work,
            payload={"asset_version": asset.version_id},
        )
        if holder:
            return holder[0]
        # Queued, or replayed: report the project and the findings as they stand.
        return (
            self.get_project(project_id),
            [],
            self._empty_review(),
        )

    def _empty_review(self):
        from .review import ReviewResult

        return ReviewResult(pending_flags=[], backend="queued")

    def _review_now(self, project_id: str):

        project = self.get_project(project_id)
        asset = self._latest_script(project_id)
        if asset is None:
            raise NotFoundError(
                "this project has no uploaded script to review",
                {"project_id": project_id},
            )

        data = self._stores.blobs.get(asset.storage_uri)
        if data is None:
            raise NotFoundError(
                "the stored bytes are missing for the latest script",
                {"asset_version": asset.version_id},
            )
        document = data.decode("utf-8", errors="replace")

        version = self._pinned_version(project)
        rules = load_subject_rules(
            self._snapshots.get_pack(PackName.P2_SUBJECT_RULES, version)
        )
        result = review_script(document, rules, self._llm)

        # Carry decisions across versions: a scene the creator already judged is
        # not re-litigated, and a scene they removed is marked self-fixed rather
        # than left open against a script that no longer contains it.
        carried, self_fixed = self._carry_findings_forward(
            project_id, asset.version_id, document
        )
        existing = carried

        written: list[Finding] = []
        for proposed in result.findings:
            key = (proposed.category, proposed.scene.quote)
            if key in existing:
                # Re-running a pre-check is normal and must not multiply scenes.
                continue
            existing.add(key)
            written.append(
                self._stores.findings.add(
                    project_id,
                    Finding(
                        finding_id=new_id("finding"),
                        asset_version=asset.version_id,
                        locator=Locator(
                            quote=proposed.scene.quote,
                            episode=proposed.scene.episode,
                            scene=proposed.scene.scene,
                            line=proposed.scene.line,
                            match_lines=sorted(set(proposed.match_lines)),
                        ),
                        category=proposed.category,
                        severity=proposed.severity,
                        evidence_refs=[evidence_for(proposed.clause_id, version)],
                        suggestion=proposed.suggestion,
                        prompt_version=SCRIPT_REVIEW_PROMPT_VERSION,
                        snapshot_version=version,
                        created_at=self._clock.now(),
                    ),
                )
            )

        self._record_event(
            project_id,
            Actor.SYSTEM,
            "review.completed",
            {
                "asset_version": asset.version_id,
                "finding_count": len(written),
                "self_fixed": self_fixed,
                "discarded": result.discarded,
                "pending_flags": result.pending_flags,
                "backend": result.backend,
            },
        )
        return self._advance_after_review(project_id), written, result

    def _advance_after_review(self, project_id: str) -> Project:
        """Move the review loop on, but only from a state that allows it.

        A pre-check run before collection has started reports without moving
        anything: the state machine, not this method, decides what is legal.
        """

        project = self.get_project(project_id)
        if project.state is ProjectState.COLLECTING_MATERIALS:
            project = self._transition(
                project, ProjectState.REVIEW_RUNNING, Actor.SYSTEM, "review.started"
            )
        if project.state is not ProjectState.REVIEW_RUNNING:
            return project

        blocking = [
            finding
            for finding in self._stores.findings.list(project_id)
            if finding.blocks_gate_d3
        ]
        if blocking:
            return self._transition(
                project,
                ProjectState.REVISION_LOOP,
                Actor.SYSTEM,
                "review.findings_open",
                detail={"open": len(blocking)},
            )
        return project

    def _carry_findings_forward(
        self, project_id: str, version_id: str, document: str
    ) -> tuple[set[tuple[str, str]], int]:
        """Move prior findings onto this version, or close the ones that are gone.

        A quote still present in the new script is the same problem, so its
        finding follows the version and keeps whatever the creator decided about
        it. A quote that has vanished was rewritten, which is the creator fixing
        it — recorded as `self_fixed`, never silently deleted.
        """

        seen: set[tuple[str, str]] = set()
        self_fixed = 0
        for finding in self._stores.findings.list(project_id):
            if finding.asset_version == version_id:
                seen.add((finding.category, finding.locator.quote))
                continue
            if finding.alert is not None:
                # Alert findings come from the intent profile, not the script.
                continue
            if finding.locator.quote and finding.locator.quote in document:
                self._stores.findings.save(
                    project_id, finding.model_copy(update={"asset_version": version_id})
                )
                seen.add((finding.category, finding.locator.quote))
            elif finding.status is FindingStatus.OPEN:
                self._stores.findings.save(
                    project_id,
                    finding.model_copy(update={"status": FindingStatus.SELF_FIXED}),
                )
                self_fixed += 1
        return seen, self_fixed

    # ---------------------------------------------------------- gate and form

    def pass_gate(self, project_id: str) -> Project:
        """Move to GATE_D3_PASSED, or refuse and say exactly what is missing."""

        project = self.get_project(project_id)
        report = self.gate_report(project_id)
        if not report.passed:
            raise GateBlockedError(
                "the pre-shoot gate is still blocked",
                {"gaps": [{"check": gap.check, "items": gap.items} for gap in report.gaps]},
            )
        if project.state is ProjectState.GATE_D3_PASSED:
            return project
        if project.state not in GATE_READY_STATES:
            # The state table says the same thing, but a raw "transition X -> Y
            # is not allowed" tells a creator nothing about what to do next.
            raise StateInvalidError(
                "the script pre-check must run before the gate can be passed",
                {"state": project.state.value},
            )
        return self._transition(
            project, ProjectState.GATE_D3_PASSED, Actor.SYSTEM, "gate.d3_passed"
        )

    def form_draft(self, project_id: str) -> FormDraft:
        """The current draft: frozen if it was frozen, rebuilt from facts if not."""

        project = self.get_project(project_id)
        existing = self._stores.forms.latest(project_id)
        if existing is not None and existing.frozen:
            return existing

        version = self._pinned_version(project)
        keys = required_fact_keys(
            self._snapshots.get_pack(PackName.P5_FORM_TEMPLATES, version)
        )
        fields, conflicts = build_fields(keys, self._stores.facts.list(project_id))
        draft = FormDraft(
            draft_id=existing.draft_id if existing else new_id("draft"),
            fields=fields,
            conflicts=conflicts,
            snapshot_version=version,
            parent_draft=existing.parent_draft if existing else None,
            created_at=existing.created_at if existing else self._clock.now(),
        )
        return self._stores.forms.put(project_id, draft)

    def confirm_form_field(
        self, project_id: str, key: str, value, reason: str | None = None
    ) -> FormDraft:
        """A human supplies a value the documents did not.

        It is recorded as a user answer rather than a document fact, so the form
        can always show where each field came from.
        """

        draft = self.form_draft(project_id)
        if draft.frozen:
            raise ConflictError(
                "a frozen form cannot be edited", {"draft_id": draft.draft_id}
            )
        if key not in draft.fields:
            raise NotFoundError(f"this form has no field named {key}", {"key": key})
        if value in (None, ""):
            raise ValidationFailedError(
                "a confirmed field needs a value; leave it pending instead",
                {"key": key},
            )

        self._upsert_fact(
            project_id,
            key,
            value,
            SourceRef(type=SourceRefType.USER_ANSWER, answer_id=new_id("fact")),
        )
        self._record_event(
            project_id,
            Actor.CREATOR,
            "form.field_confirmed",
            {"key": key, "reason": reason},
        )
        return self.form_draft(project_id)

    def defer_form_field(
        self, project_id: str, key: str, reason: str | None = None
    ) -> FormDraft:
        """The creator states this value comes from the institution, not them.

        The commonest case is `applicant_entity`: an individual creator has no
        广播电视节目制作经营许可证, so the licensed company that files the
        project supplies its own details. Before this there was no way to say
        that -- `confirm_form_field` refuses an empty value and tells you to
        leave the field pending, and a pending field holds the form shut
        forever. So the honest answer was unreachable and the only reachable
        answers were inventing a company or abandoning the filing.

        Deferring records a fact with no value and `PENDING_INSTITUTION`
        status. Nothing is invented: the field still renders 待补充, still
        hashes as unfilled, and `deferred_keys` lists it on the frozen form.
        What changes is that the gate and the freeze stop treating a declared
        gap as an unanswered one.
        """

        draft = self.form_draft(project_id)
        if draft.frozen:
            raise ConflictError(
                "a frozen form cannot be edited", {"draft_id": draft.draft_id}
            )
        if key not in draft.fields:
            raise NotFoundError(f"this form has no field named {key}", {"key": key})

        existing = self._stores.facts.get_by_key(project_id, key)
        if existing is not None and existing.status is FactStatus.CONFIRMED:
            raise ValidationFailedError(
                "this field already has a confirmed value; deferring would discard it",
                {"key": key},
            )

        fact = Fact(
            fact_id=new_id("fact"),
            key=key,
            value=None,
            source_ref=SourceRef(
                type=SourceRefType.USER_ANSWER, answer_id=new_id("fact")
            ),
            status=FactStatus.PENDING_INSTITUTION,
            created_at=self._clock.now(),
        )
        self._stores.facts.add(project_id, fact)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "form.field_deferred",
            {"key": key, "reason": reason},
        )
        return self.form_draft(project_id)

    def freeze_form(self, project_id: str) -> FormDraft:
        """Freeze only from GATE_D3_PASSED, and only with no field left pending."""

        project = self.get_project(project_id)
        existing = self._stores.forms.latest(project_id)
        if existing is not None and existing.frozen:
            return existing

        if project.state is not ProjectState.GATE_D3_PASSED:
            raise StateInvalidError(
                "a form can only be frozen once the pre-shoot gate has passed",
                {"state": project.state.value},
            )

        draft = self.form_draft(project_id)
        outstanding = pending_keys(draft)
        if outstanding:
            raise GateBlockedError(
                "every field must be filled or confirmed before freezing",
                {"pending": outstanding},
            )

        frozen = draft.model_copy(
            update={
                "frozen": True,
                "hash": draft_hash(draft),
                "confirmed_by_user_at": self._clock.now(),
            }
        )
        self._stores.forms.put(project_id, frozen)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "form.frozen",
            {
                "draft_id": frozen.draft_id,
                "hash": frozen.hash,
                # A frozen form with declared gaps is a different document from
                # a complete one, and the timeline should say which it was.
                "deferred": deferred_keys(frozen),
            },
        )
        self._transition(
            project, ProjectState.FORM_FROZEN, Actor.CREATOR, "form.frozen"
        )
        return frozen

    # ---------------------------------------------------------------- teaser

    def request_teaser(self, project_id: str, seconds: int = 8) -> WorkflowTask:
        """Ask for a promotional teaser. Records what happened, never a fake one.

        Idempotent on `{project_id}:teaser:{asset_version}` like every other
        job, so a retry returns the first task rather than generating twice.
        """

        project = self.get_project(project_id)
        # `core.teaser` still calls its input a logline, which is the right word
        # for what a teaser is generated from. The intake field it comes from is
        # now the synopsis — one story field, and it is the one the filing form
        # actually asks for.
        logline = (project.intent_profile.synopsis or "").strip()
        if not logline:
            raise ValidationFailedError(
                "a teaser needs a synopsis to work from", {"project_id": project_id}
            )

        latest = self._latest_script(project_id)
        version = latest.version_id if latest else "intent_profile"
        key = f"{project_id}:{TaskType.TEASER.value}:{version}"

        existing = self._stores.tasks.find_by_idempotency_key(key)
        if existing is not None:
            return existing

        now = self._clock.now()
        task = WorkflowTask(
            task_id=new_id("task"),
            project_id=project_id,
            type=TaskType.TEASER,
            status=TaskStatus.RUNNING,
            idempotency_key=key,
            payload={
                "seconds": seconds,
                "prompt_version": TEASER_PROMPT_VERSION,
                "snapshot_version": self._pinned_version(project),
            },
            created_at=now,
            updated_at=now,
        )
        self._stores.tasks.add(task)

        if self._video is None or not self._video.available():
            # No backend is a pending flag, never a placeholder video.
            task = task.model_copy(
                update={
                    "status": TaskStatus.NEEDS_HUMAN,
                    "error": TEASER_PENDING,
                    "updated_at": self._clock.now(),
                }
            )
        else:
            try:
                uri = self._video.generate(build_request(logline, seconds))
                task = task.model_copy(
                    update={
                        "status": TaskStatus.SUCCEEDED,
                        "result": {
                            "uri": uri,
                            "backend": self._video.name,
                            "promotional_only": True,
                        },
                        "updated_at": self._clock.now(),
                    }
                )
            except Exception as failure:  # a refused generation is not a teaser
                task = task.model_copy(
                    update={
                        "status": TaskStatus.FAILED,
                        "error": str(failure),
                        "updated_at": self._clock.now(),
                    }
                )

        self._stores.tasks.save(task)
        self._record_event(
            project_id,
            Actor.SYSTEM,
            "teaser.requested",
            {
                "task_id": task.task_id,
                "status": task.status.value,
                "error": task.error,
            },
        )
        return task

    # ------------------------------------------------- institution and filing

    def load_institutions(self, institutions: list[MockInstitution]) -> list[MockInstitution]:
        """Demo registry. Empty by default: no institution ships invented."""

        self._stores.institutions.load(institutions)
        return self._stores.institutions.list()

    def list_institutions(self) -> list[MockInstitution]:
        return self._stores.institutions.list()

    # The states an institution owns. A project sitting in either of these is
    # waiting on the reviewer, not on the creator, which is exactly what a queue
    # has to be able to say.
    INSTITUTION_QUEUE_STATES = (
        ProjectState.INSTITUTION_REVIEW,
        ProjectState.READY_FOR_EXTERNAL_FILING,
    )

    def institution_queue(self, institution_id: str | None = None) -> list[dict]:
        """What is waiting on an institution, newest submission first.

        `ProjectStore.list_all` existed as a port method that nothing called, so
        a reviewer had no way to discover work: they had to be handed a project
        id out of band and paste it in. A console without a queue is a lookup
        tool, not an inbox.

        Two states qualify. `INSTITUTION_REVIEW` needs a decision.
        `READY_FOR_EXTERNAL_FILING` has been accepted and still needs a
        registration number, which is also the institution's act -- leaving it
        out would let an accepted project fall off the reviewer's screen with
        the last step undone.
        """

        rows: list[dict] = []
        for project in self._stores.projects.list_all():
            if project.state not in self.INSTITUTION_QUEUE_STATES:
                continue
            review = self._stores.institution_reviews.latest(project.project_id)
            if institution_id and (
                review is None or review.institution_id != institution_id
            ):
                continue
            classification = project.classification
            rows.append(
                {
                    "project_id": project.project_id,
                    # Never invented: a project with no working title says so
                    # rather than borrowing one from somewhere else.
                    "title_working": project.title_working,
                    "state": project.state.value,
                    "tier": classification.tier.value if classification else None,
                    "institution_id": review.institution_id if review else None,
                    "review_id": review.review_id if review else None,
                    "decision": (
                        review.decision.value
                        if review is not None and review.decision is not None
                        else None
                    ),
                    "submitted_at": (
                        review.created_at.isoformat()
                        if review is not None and review.created_at is not None
                        else None
                    ),
                    # There is no `ok` field: an empty `reasons` is what
                    # passing means, and the reasons themselves are what the
                    # reviewer needs to see when it does not.
                    "licence_reasons": (
                        list(review.license_check.reasons)
                        if review is not None and review.license_check is not None
                        else []
                    ),
                }
            )

        # Newest submission first, and a row with no timestamp sorts last rather
        # than crashing the comparison.
        rows.sort(key=lambda row: row["submitted_at"] or "", reverse=True)
        return rows

    def submit_to_institution(
        self, project_id: str, institution_id: str
    ) -> tuple[Project, InstitutionReview]:
        """Hand a frozen form to a licensed institution, with a mock licence check."""

        project = self.get_project(project_id)
        # Re-submitting while already under review is switching institutions,
        # which the state table allows; the frozen form is unchanged either way.
        if project.state not in (
            ProjectState.FORM_FROZEN,
            ProjectState.INSTITUTION_REVIEW,
        ):
            raise StateInvalidError(
                "the form must be frozen before it goes to an institution",
                {"state": project.state.value},
            )

        review = InstitutionReview(
            review_id=new_id("review"),
            institution_id=institution_id,
            license_check=check_licence(
                institution_id, self._stores.institutions.get(institution_id)
            ),
            created_at=self._clock.now(),
        )
        self._stores.institution_reviews.put(project_id, review)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "institution.submitted",
            {
                "institution_id": institution_id,
                "license_reasons": list(review.license_check.reasons),
            },
        )
        project = self._transition(
            project,
            ProjectState.INSTITUTION_REVIEW,
            Actor.CREATOR,
            "institution.submitted",
        )
        return project, review

    def decide_institution_review(
        self,
        project_id: str,
        decision: str,
        return_comments: str | None = None,
        signed_agreement_uri: str | None = None,
    ) -> tuple[Project, InstitutionReview]:
        """The institution's verdict. Accepting needs a licence check that passed."""

        project = self.get_project(project_id)
        review = self._stores.institution_reviews.latest(project_id)
        if review is None:
            raise NotFoundError(
                "this project has not been submitted to an institution",
                {"project_id": project_id},
            )

        try:
            verdict = InstitutionDecision(decision)
        except ValueError as exc:
            raise ValidationFailedError(
                f"unknown decision: {decision}", {"decision": decision}
            ) from exc

        if verdict is InstitutionDecision.ACCEPT:
            if not (signed_agreement_uri or "").strip():
                raise ValidationFailedError(
                    "accepting requires the signed agreement",
                    {"field": "signed_agreement_uri"},
                )
            if review.license_check is None or not review.license_check.valid:
                # The check is mock, but a mock check that failed must still
                # stop the flow — otherwise the demo teaches the wrong lesson.
                raise ValidationFailedError(
                    "the mock license check did not pass for this institution",
                    {"reasons": list((review.license_check.reasons if review.license_check else ["no_license_check"]))},
                )
        if verdict is InstitutionDecision.RETURN and not (return_comments or "").strip():
            raise ValidationFailedError(
                "returning a project requires comments", {"field": "return_comments"}
            )

        updated = review.model_copy(
            update={
                "decision": verdict,
                "return_comments": return_comments,
                "signed_agreement_uri": signed_agreement_uri,
                "decided_at": self._clock.now(),
            }
        )
        self._stores.institution_reviews.put(project_id, updated)
        self._record_event(
            project_id,
            Actor.INSTITUTION,
            "institution.decided",
            {"decision": verdict.value, "review_id": updated.review_id},
        )

        target = {
            InstitutionDecision.ACCEPT: ProjectState.READY_FOR_EXTERNAL_FILING,
            InstitutionDecision.RETURN: ProjectState.INSTITUTION_RETURNED,
        }.get(verdict)
        if target is not None:
            project = self._transition(
                project, target, Actor.INSTITUTION, f"institution.{verdict.value}"
            )
        return project, updated

    def resume_after_return(self, project_id: str) -> Project:
        """Take a returned project back into the revision loop.

        Without this, `INSTITUTION_RETURNED` is a dead end: the state table
        allows the way back but nothing performed it, so a returned project
        could never be corrected and resubmitted.
        """

        project = self.get_project(project_id)
        if project.state is not ProjectState.INSTITUTION_RETURNED:
            raise StateInvalidError(
                "only a returned project can resume the revision loop",
                {"state": project.state.value},
            )
        review = self._stores.institution_reviews.latest(project_id)

        # Coming back around the loop starts a successor draft.
        #
        # Without this the revision loop was a dead end. `form_draft` returns a
        # frozen draft unchanged, and `freeze_form` early-returns one too, so a
        # returned project could be resumed and its gate re-passed but never
        # re-frozen -- the state never reached FORM_FROZEN again and every
        # resubmission answered 409. The creator could act on the reviewer's
        # comments and had no way to send the result.
        #
        # The frozen draft is not reopened: it is the record of what was
        # reviewed, and `parent_draft` is the field that was always meant to
        # carry that lineage. The successor rebuilds from facts on the next
        # read, so corrections show up and freezing produces a new hash.
        frozen_draft = self._stores.forms.latest(project_id)
        if frozen_draft is not None and frozen_draft.frozen:
            self._stores.forms.put(
                project_id,
                FormDraft(
                    draft_id=new_id("draft"),
                    form_type=frozen_draft.form_type,
                    snapshot_version=frozen_draft.snapshot_version,
                    parent_draft=frozen_draft.draft_id,
                    created_at=self._clock.now(),
                ),
            )

        self._record_event(
            project_id,
            Actor.CREATOR,
            "institution.return_acknowledged",
            {
                "comments": review.return_comments if review else None,
                "supersedes_draft": (
                    frozen_draft.draft_id
                    if frozen_draft is not None and frozen_draft.frozen
                    else None
                ),
            },
        )
        return self._transition(
            project,
            ProjectState.REVISION_LOOP,
            Actor.CREATOR,
            "institution.returned_for_revision",
        )

    def latest_institution_review(self, project_id: str):
        self.get_project(project_id)
        return self._stores.institution_reviews.latest(project_id)

    def list_tasks(self, project_id: str):
        """Async job records for this project (contract step 17)."""

        self.get_project(project_id)
        return self._stores.tasks.list(project_id)

    def record_filing(self, project_id: str, registration_number: str) -> Project:
        """Record a number a human read off a government system.

        Ground rule 3 at its sharpest: this is the one value the product must
        never generate, so it arrives as input and is stored verbatim.
        """

        if not (registration_number or "").strip():
            raise ValidationFailedError(
                "a filing needs the registration number a human received",
                {"field": "registration_number"},
            )

        project = self.get_project(project_id)
        project = project.model_copy(
            update={
                "registration_number": registration_number.strip(),
                "updated_at": self._clock.now(),
            }
        )
        self._stores.projects.save(project)
        self._record_event(
            project_id,
            Actor.INSTITUTION,
            "filing.recorded",
            {"registration_number": project.registration_number},
        )
        return self._transition(
            project, ProjectState.FILED, Actor.INSTITUTION, "filing.recorded"
        )

    # --------------------------------------------------------- finding actions

    def act_on_finding(
        self,
        project_id: str,
        finding_id: str,
        action: str,
        reason: str | None = None,
        option_id: str | None = None,
    ) -> Finding:
        """Apply one creator decision to one finding.

        `accept` acknowledges without releasing the gate: agreeing that a scene
        is a problem does not make it stop being one. `resolve`, `waive`, and
        `reject` each release it for a different recorded reason.
        """

        self.get_project(project_id)
        finding = self._stores.findings.get(project_id, finding_id)
        if finding is None:
            raise NotFoundError(
                f"finding not found: {finding_id}", {"finding_id": finding_id}
            )

        if action == "choose_option":
            updated = self._dispatch_alert(finding, option_id)
        else:
            updated = finding.model_copy(
                update={"status": self._status_for(action, reason)}
            )

        self._stores.findings.save(project_id, updated)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "finding.action",
            {
                "finding_id": finding_id,
                "action": action,
                "status": updated.status.value,
                "reason": reason,
                "option_id": option_id,
            },
        )
        return updated

    def _status_for(self, action: str, reason: str | None) -> FindingStatus:
        if action == "accept":
            return FindingStatus.ACCEPTED
        if action == "resolve":
            return FindingStatus.RESOLVED
        if action in ("waive", "reject"):
            if not (reason or "").strip():
                raise ValidationFailedError(
                    f"{action} requires a reason", {"action": action}
                )
            return (
                FindingStatus.WAIVED if action == "waive" else FindingStatus.REJECTED
            )
        raise ValidationFailedError(f"unknown finding action: {action}", {"action": action})

    def _dispatch_alert(self, finding: Finding, option_id: str | None) -> Finding:
        if finding.alert is None:
            raise ValidationFailedError(
                "this finding carries no alert to dispatch",
                {"finding_id": finding.finding_id},
            )
        offered = {option.id.value for option in finding.alert.options}
        if option_id not in offered:
            raise ValidationFailedError(
                "that option was not offered for this alert",
                {"offered": sorted(offered)},
            )
        alert = finding.alert.model_copy(
            update={
                "chosen_option": AlertOption(option_id),
                "chosen_at": self._clock.now(),
            }
        )
        return finding.model_copy(update={"alert": alert})

    def list_findings(self, project_id: str) -> list[Finding]:
        self.get_project(project_id)
        return self._stores.findings.list(project_id)

    def _latest_script(self, project_id: str) -> AssetVersion | None:
        scripts = [
            asset
            for asset in self._stores.assets.list(project_id)
            if asset.kind is AssetKind.SCRIPT
        ]
        return scripts[-1] if scripts else None

    # --------------------------------------------------------------- roadmap

    def roadmap_preview(self, project_id: str) -> tuple[Roadmap | None, list[str]]:
        """The plan this project would follow, built from the pinned snapshot."""

        project = self.get_project(project_id)
        if project.roadmap is not None:
            _, flags = self._build_roadmap_for(project)
            return project.roadmap, flags
        if project.classification is None:
            return None, ["classification_pending"]
        return self._build_roadmap_for(project)

    def confirm_roadmap(self, project_id: str) -> tuple[Project, list[str]]:
        """The creator accepts the plan. Idempotent: confirming twice is one event."""

        project = self.get_project(project_id)
        if project.classification is None:
            raise StateInvalidError(
                "a project must be classified before its roadmap is confirmed",
                {"state": project.state.value},
            )

        roadmap, flags = self._build_roadmap_for(project)
        if project.roadmap is not None and project.roadmap.confirmed:
            return project, flags

        project = project.model_copy(
            update={
                "roadmap": roadmap.model_copy(update={"confirmed": True}),
                "updated_at": self._clock.now(),
            }
        )
        self._stores.projects.save(project)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "roadmap.confirmed",
            {
                "template": roadmap.template,
                "step_count": len(roadmap.steps),
                "pending_flags": flags,
            },
        )
        project = self._transition(
            project,
            ProjectState.ROADMAP_CONFIRMED,
            Actor.CREATOR,
            "roadmap.confirmed",
        )
        # Confirming the plan is what starting collection means. Both
        # transitions are recorded, so the audit trail keeps ROADMAP_CONFIRMED
        # visible while the project rests where the work actually is. The
        # roadmap document carries `confirmed` regardless.
        project = self._transition(
            project,
            ProjectState.COLLECTING_MATERIALS,
            Actor.CREATOR,
            "materials.collection_started",
        )
        return project, flags

    def _build_roadmap_for(self, project: Project) -> tuple[Roadmap, list[str]]:
        classification = project.classification
        assert classification is not None  # callers check before reaching here
        template = ROADMAP_TEMPLATE_BY_TIER.get(
            classification.tier, f"{classification.tier.value}_template"
        )
        version = self._pinned_version(project)
        return build_roadmap(
            template, self._snapshots.get_pack(PackName.P4_PROCESS_TEMPLATES, version)
        )

    # ------------------------------------------------------------------- jobs

    def _run_job(
        self,
        project_id: str,
        task_type: TaskType,
        asset_version: str,
        work,
        payload: dict | None = None,
    ) -> tuple[WorkflowTask, JobOutcome | None, bool]:
        """Record the job, then let the runner decide where it executes.

        Returns the task, the outcome if it ran here, and whether this call was
        a replay. A replay returns the first task untouched: Pub/Sub redelivers,
        and a redelivered review must not write a second set of findings.
        """

        key = idempotency_key(project_id, task_type, asset_version)
        existing = self._stores.tasks.find_by_idempotency_key(key)
        if existing is not None:
            return existing, None, True

        now = self._clock.now()
        task = self._stores.tasks.add(
            WorkflowTask(
                task_id=new_id("task"),
                project_id=project_id,
                type=task_type,
                status=TaskStatus.QUEUED,
                idempotency_key=key,
                payload=payload or {},
                created_at=now,
                updated_at=now,
            )
        )

        task, outcome = self._jobs.run(task, work)
        task = self._stores.tasks.save(
            task.model_copy(update={"updated_at": self._clock.now()})
        )
        self._record_event(
            project_id,
            Actor.SYSTEM,
            "job.recorded",
            {
                "task_id": task.task_id,
                "type": task_type.value,
                "status": task.status.value,
                "error": task.error,
            },
        )
        return task, outcome, False

    def execute_task(self, task: WorkflowTask) -> WorkflowTask:
        """Run a queued task's work and record the outcome on it.

        The API's `_run_job` refuses to start a job whose key already has a
        task, which is what makes redelivery safe. A worker holding that very
        task needs the opposite: run the work this record stands for. Both paths
        call the same `_*_now` method, so the work has one implementation and
        only the trigger differs.
        """

        work = {
            TaskType.FACT_EXTRACT: lambda: self._extract_outcome(task),
            TaskType.REVIEW_FULL: lambda: self._review_outcome(task),
            TaskType.REVIEW_INCREMENTAL: lambda: self._review_outcome(task),
        }.get(task.type)

        if work is None:
            raise ValidationFailedError(
                f"no worker handles {task.type.value}", {"type": task.type.value}
            )

        running = self._stores.tasks.save(
            task.model_copy(
                update={"status": TaskStatus.RUNNING, "updated_at": self._clock.now()}
            )
        )
        outcome = work()
        finished = running.model_copy(
            update={
                "status": outcome.status,
                "result": outcome.result,
                "error": outcome.error,
                "updated_at": self._clock.now(),
            }
        )
        self._stores.tasks.save(finished)
        self._record_event(
            task.project_id,
            Actor.SYSTEM,
            "job.completed",
            {
                "task_id": finished.task_id,
                "type": finished.type.value,
                "status": finished.status.value,
                "error": finished.error,
            },
        )
        return finished

    def _extract_outcome(self, task: WorkflowTask) -> JobOutcome:
        version = str(task.payload.get("asset_version"))
        found, extraction = self._extract_now(task.project_id, version)
        return JobOutcome(
            result={
                "keys": [fact.key for fact in found],
                "discarded": extraction.discarded,
                "backend": extraction.backend,
            },
            status=TaskStatus.NEEDS_HUMAN
            if extraction.pending_flags
            else TaskStatus.SUCCEEDED,
            error=extraction.pending_flags[0] if extraction.pending_flags else None,
        )

    def _review_outcome(self, task: WorkflowTask) -> JobOutcome:
        _, written, result = self._review_now(task.project_id)
        return JobOutcome(
            result={
                "finding_count": len(written),
                "discarded": result.discarded,
                "backend": result.backend,
            },
            status=TaskStatus.NEEDS_HUMAN
            if result.pending_flags
            else TaskStatus.SUCCEEDED,
            error=result.pending_flags[0] if result.pending_flags else None,
        )

    # ------------------------------------------------------- fact extraction

    def extract_asset_facts(self, project_id: str, version_id: str):
        """Read one asset and store only the facts it can back verbatim.

        Recorded as a `fact_extract` task, so a redelivery of the same asset
        version returns the first task instead of extracting twice.
        """

        # Validate before recording a job: an asset that does not exist is a
        # 404, not a task that failed.
        self.read_asset(project_id, version_id)

        stored: list[Fact] = []
        result_holder: list = []

        def work() -> JobOutcome:
            found, extraction = self._extract_now(project_id, version_id)
            stored.extend(found)
            result_holder.append(extraction)
            return JobOutcome(
                result={
                    "keys": [fact.key for fact in found],
                    "discarded": extraction.discarded,
                    "backend": extraction.backend,
                },
                status=TaskStatus.NEEDS_HUMAN
                if extraction.pending_flags
                else TaskStatus.SUCCEEDED,
                error=extraction.pending_flags[0] if extraction.pending_flags else None,
            )

        task, _, replayed = self._run_job(
            project_id,
            TaskType.FACT_EXTRACT,
            version_id,
            work,
            payload={"asset_version": version_id},
        )
        if replayed or not result_holder:
            # Nothing ran here: report what the document already produced.
            return self._replayed_extraction(project_id, version_id, task)
        return stored, result_holder[0]

    def _replayed_extraction(self, project_id: str, version_id: str, task):
        """A replay reports the first run's facts rather than extracting again."""

        from .extract import ExtractionResult

        recorded = task.result or {}
        keys = set(recorded.get("keys") or [])
        facts = [f for f in self._stores.facts.list(project_id) if f.key in keys]
        return facts, ExtractionResult(
            discarded=list(recorded.get("discarded") or []),
            pending_flags=[task.error] if task.error else [],
            backend=str(recorded.get("backend") or "unavailable"),
        )

    def _extract_now(self, project_id: str, version_id: str):
        project = self.get_project(project_id)
        asset, data = self.read_asset(project_id, version_id)
        document = data.decode("utf-8", errors="replace")

        version = self._pinned_version(project)
        wanted = required_fact_keys(
            self._snapshots.get_pack(PackName.P5_FORM_TEMPLATES, version)
        )
        result = extract_facts(document, self._llm, wanted)

        stored: list[Fact] = []
        for proposed in result.facts:
            stored.append(
                self._upsert_fact(
                    project_id,
                    proposed.key,
                    proposed.value,
                    proposed.source_ref(asset.version_id),
                )
            )

        self._record_event(
            project_id,
            Actor.SYSTEM,
            "facts.extracted",
            {
                "asset_version": asset.version_id,
                "keys": [fact.key for fact in stored],
                "discarded": result.discarded,
                "pending_flags": result.pending_flags,
                "backend": result.backend,
            },
        )
        return stored, result

    def list_facts(self, project_id: str) -> list[Fact]:
        self.get_project(project_id)
        return self._stores.facts.list(project_id)

    # -------------------------------------------------------------- materials

    def material_cards(self, project_id: str) -> list[MaterialCard]:
        """The pack defines which cards exist; stored state defines where each is.

        Cards are materialised on first read and then kept, so a snapshot that
        later drops a card does not erase the creator's work on it.
        """

        project = self.get_project(project_id)
        stored = {card.material_id: card for card in self._stores.materials.list(project_id)}
        version = self._pinned_version(project)
        defined = build_material_cards(
            self._snapshots.get_pack(PackName.P5_FORM_TEMPLATES, version),
            self._snapshots,
            version,
        )

        cards: list[MaterialCard] = []
        for card in defined:
            existing = stored.pop(card.material_id, None)
            if existing is None:
                existing = self._stores.materials.put(project_id, card)
            cards.append(existing)
        # Cards the pack no longer defines stay visible rather than vanishing.
        cards.extend(stored.values())
        return cards

    def get_material(self, project_id: str, material_id: str) -> MaterialCard:
        for card in self.material_cards(project_id):
            if card.material_id == material_id:
                return card
        raise NotFoundError(
            f"material card not found: {material_id}", {"material_id": material_id}
        )

    def attach_material(
        self, project_id: str, material_id: str, asset_version: str
    ) -> MaterialCard:
        card = self.get_material(project_id, material_id)
        asset = self._stores.assets.get(project_id, asset_version)
        if asset is None:
            raise NotFoundError(
                f"asset version not found: {asset_version}",
                {"asset_version": asset_version},
            )
        if asset.kind is not card.asset_kind:
            raise ValidationFailedError(
                "asset kind does not match material card",
                {
                    "expected_kind": card.asset_kind.value,
                    "actual_kind": asset.kind.value,
                },
            )
        updated = card.model_copy(
            update={
                "asset_version": asset_version,
                "status": MaterialStatus.UPLOADED,
                "invalid_reasons": [],
            }
        )
        self._stores.materials.put(project_id, updated)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "material.attached",
            {"material_id": material_id, "asset_version": asset_version},
        )
        return updated

    def validate_material(self, project_id: str, material_id: str) -> MaterialCard:
        """Deterministic checks only. Nothing here is a compliance judgement."""

        card = self.get_material(project_id, material_id)
        reasons = self._material_defects(project_id, card)
        updated = card.model_copy(
            update={
                "status": MaterialStatus.INVALID if reasons else MaterialStatus.VALID,
                "invalid_reasons": reasons,
            }
        )
        self._stores.materials.put(project_id, updated)
        self._record_event(
            project_id,
            Actor.SYSTEM,
            "material.validated",
            {
                "material_id": material_id,
                "status": updated.status.value,
                "invalid_reasons": reasons,
            },
        )
        return updated

    def waive_material(
        self, project_id: str, material_id: str, reason: str
    ) -> MaterialCard:
        """A human waives a card, and the reason is recorded with the waiver."""

        if not reason.strip():
            raise ValidationFailedError("a waiver must carry a reason")
        card = self.get_material(project_id, material_id)
        updated = card.model_copy(
            update={
                "status": MaterialStatus.WAIVED,
                "waive_reason": reason.strip(),
                "invalid_reasons": [],
            }
        )
        self._stores.materials.put(project_id, updated)
        self._record_event(
            project_id,
            Actor.CREATOR,
            "material.waived",
            {"material_id": material_id, "reason": updated.waive_reason},
        )
        return updated

    def _material_defects(self, project_id: str, card: MaterialCard) -> list[str]:
        if card.asset_version is None:
            return ["no_asset_attached"]
        asset = self._stores.assets.get(project_id, card.asset_version)
        if asset is None:
            return ["asset_version_missing"]
        if not self._stores.blobs.get(asset.storage_uri):
            return ["stored_bytes_missing"]
        return []

    def _pinned_version(self, project: Project) -> str:
        """Judgements use the project's pinned snapshot, not whatever is latest."""

        if project.classification is not None:
            return project.classification.policy_snapshot_version
        return self._snapshots.latest_version()

    # ---------------------------------------------------------------- uploads

    def issue_upload_ticket(
        self,
        project_id: str,
        kind: AssetKind,
        issued_to: str,
        filename: str | None = None,
    ) -> UploadTicket:
        """A one-shot permit naming where one asset version may be written."""

        project = self.get_project(project_id)
        ticket_id = new_id("asset").replace("av_", "tkt_", 1)
        ticket = UploadTicket(
            ticket_id=ticket_id,
            project_id=project.project_id,
            kind=kind,
            storage_uri=f"blob://{project.project_id}/{ticket_id}",
            issued_to=issued_to,
            filename=filename,
            created_at=self._clock.now(),
        )
        return self._stores.upload_tickets.add(ticket)

    def complete_upload(self, ticket_id: str, data: bytes) -> AssetVersion:
        """Write the bytes, then the immutable version record that names them."""

        if not data:
            raise ValidationFailedError("an upload must carry bytes")

        pending = self._stores.upload_tickets.get(ticket_id)
        if pending is None:
            raise NotFoundError(
                f"upload ticket not found: {ticket_id}", {"ticket_id": ticket_id}
            )
        ticket = self._stores.upload_tickets.consume(ticket_id)
        if ticket is None:
            raise ConflictError(
                "this upload ticket was already used", {"ticket_id": ticket_id}
            )

        self._stores.blobs.put(ticket.storage_uri, data)
        asset = AssetVersion(
            version_id=new_id("asset"),
            kind=ticket.kind,
            storage_uri=ticket.storage_uri,
            sha256=hashlib.sha256(data).hexdigest(),
            parent_version=self._latest_version_of(ticket.project_id, ticket.kind),
            uploaded_by=ticket.issued_to,
            created_at=self._clock.now(),
        )
        self._stores.assets.add(ticket.project_id, asset)
        self._record_event(
            ticket.project_id,
            Actor.CREATOR,
            "asset.uploaded",
            {
                "version_id": asset.version_id,
                "kind": asset.kind.value,
                "sha256": asset.sha256,
                "parent_version": asset.parent_version,
            },
        )
        return asset

    def list_assets(self, project_id: str) -> list[AssetVersion]:
        self.get_project(project_id)
        return self._stores.assets.list(project_id)

    def read_asset(self, project_id: str, version_id: str) -> tuple[AssetVersion, bytes]:
        self.get_project(project_id)
        asset = self._stores.assets.get(project_id, version_id)
        if asset is None:
            raise NotFoundError(
                f"asset version not found: {version_id}", {"version_id": version_id}
            )
        data = self._stores.blobs.get(asset.storage_uri)
        if data is None:
            raise NotFoundError(
                "the stored bytes are missing for this version",
                {"version_id": version_id},
            )
        return asset, data

    def _latest_version_of(self, project_id: str, kind: AssetKind) -> str | None:
        """A revision chains onto the previous version of the same kind only."""

        same_kind = [
            asset
            for asset in self._stores.assets.list(project_id)
            if asset.kind is kind
        ]
        return same_kind[-1].version_id if same_kind else None

    # --------------------------------------------------------- notifications

    def list_notifications(
        self, user_id: str, unread_only: bool = False
    ) -> list[Notification]:
        return self._stores.notifications.list(user_id, unread_only)

    def mark_notification_read(self, notification_id: str, user_id: str) -> Notification:
        existing = self._stores.notifications.get(notification_id)
        if existing is None:
            raise NotFoundError(
                f"notification not found: {notification_id}",
                {"notification_id": notification_id},
            )
        if existing.user_id != user_id:
            raise ForbiddenError("this notification belongs to another user")
        marked = self._stores.notifications.mark_read(notification_id)
        assert marked is not None  # the get above already proved it exists
        return marked

    # --------------------------------------------------------------- internals

    def _thresholds_published(self, version: str | None = None) -> bool | None:
        pack = self._snapshots.get_pack(PackName.P3_TIER_THRESHOLDS, version)
        for key in PUBLISHED_KEYS:
            if key in pack:
                return bool(pack[key])
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
            # `logline` was removed from IntentProfile when the synopsis became
            # the single story field, and this line still read it. Python's
            # `or` short-circuits, so the crash only waited on an alert with no
            # matched-rule quote -- which every existing test happens to have.
            locator=Locator(quote=quote or (project.intent_profile.synopsis or "")),
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

    def _notify(
        self, project: Project, kind: NotificationKind, params: dict
    ) -> Notification:
        """One inbox entry for the project owner. Text is keys, rendered by the UI."""

        notification = Notification(
            notification_id=new_id("notification"),
            user_id=project.owner_uid,
            project_id=project.project_id,
            kind=kind,
            title_key=f"notification.{kind.value}.title",
            body_key=f"notification.{kind.value}.body",
            params=params,
            link=f"/dashboard?project={project.project_id}",
            created_at=self._clock.now(),
        )
        return self._stores.notifications.add(notification)

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
