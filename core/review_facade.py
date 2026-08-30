"""Deep module for the creator-facing upload, confirm, and review demo."""

from __future__ import annotations

from pathlib import Path

from core.clock import Clock
from core.classify.subject_rules import load_subject_rules
from core.comparison import budget_comparison
from core.errors import (
    ArtifactGenerationFailedError,
    ArtifactUnavailableError,
    ForbiddenError,
    NotFoundError,
    StateInvalidError,
)
from core.ids import new_id
from core.llm import LLMClient
from core.review_artifacts import ArtifactComposer, ArtifactFormField, ReviewPackage
from core.script_intake import ScriptIntakeAnalyzer
from core.script_text import ParsedScript, parse_script
from core.workflow_service import WorkflowService
from schemas.enums import AssetKind, FieldStatus, FindingSeverity, Tier
from schemas.policy_snapshot import PackName
from schemas.reviews import (
    CandidateReviewDetails,
    ConfirmedReviewDetails,
    GeneratedArtifact,
    IdeaOnly,
    IntakeStatus,
    ReviewArtifactLink,
    ReviewArtifactType,
    ReviewAmountOption,
    ReviewClassificationView,
    ReviewFindingView,
    ReviewMode,
    ReviewSession,
    ReviewState,
    ReviewView,
    SemanticStatus,
    StartReviewCommand,
    UploadedScript,
)
from schemas.snapshot import SnapshotService


_CLASS_NAMES = {
    Tier.T1: "Class 1",
    Tier.T2: "Class 2",
    Tier.T3: "Class 3",
    Tier.UNDETERMINED: "Undetermined",
}
_CATEGORY_NAMES = {
    "public_security": "Public security subject",
    "political": "Political subject",
    "military": "Military subject",
    "diplomatic": "Diplomatic subject",
    "national_security": "National security subject",
    "united_front": "United front subject",
    "ethnic": "Ethnic subject",
    "religious": "Religious subject",
    "judicial": "Judicial subject",
}
_SEVERITY_NAMES = {
    FindingSeverity.BLOCK: "Block",
    FindingSeverity.CO_REVIEW_REQUIRED: "Co-review required",
    FindingSeverity.CAUTION: "Caution",
    FindingSeverity.PASS: "Pass",
    FindingSeverity.NEEDS_HUMAN: "Needs human review",
}
_ARTIFACT_FILES = {
    ReviewArtifactType.FORM: "project-review-form.pdf",
    ReviewArtifactType.SUMMARY: "risk-summary.pdf",
    ReviewArtifactType.ANNOTATED_SCRIPT: "annotated-script.md",
}


class ReviewFacade:
    def __init__(
        self,
        *,
        stores,
        snapshots: SnapshotService,
        clock: Clock,
        llm: LLMClient | None,
        artifact_composer: ArtifactComposer | None = None,
    ) -> None:
        self._stores = stores
        self._snapshots = snapshots
        self._clock = clock
        self._llm = llm
        self._workflow = WorkflowService(stores, snapshots, clock, llm)
        self._intake = ScriptIntakeAnalyzer(llm)
        self._artifact_composer = artifact_composer or ArtifactComposer()

    def start(self, command: StartReviewCommand) -> ReviewView:
        parsed = None
        if isinstance(command.source, UploadedScript):
            # Validate before creating durable project/session records so rejected
            # uploads cannot leave orphaned UPLOADING reviews.
            parsed = parse_script(command.source.filename, command.source.content)
        project = self._workflow.create_project(command.owner_uid)
        now = self._clock.now()
        mode = (
            ReviewMode.IDEA
            if isinstance(command.source, IdeaOnly)
            else ReviewMode.SCRIPT
        )
        session = ReviewSession(
            review_id=new_id("review"),
            owner_uid=command.owner_uid,
            mode=mode,
            state=(
                ReviewState.AWAITING_CONFIRMATION
                if mode is ReviewMode.IDEA
                else ReviewState.UPLOADING
            ),
            project_id=project.project_id,
            candidates=CandidateReviewDetails()
            if mode is ReviewMode.IDEA
            else None,
            intake_status=IntakeStatus.NOT_STARTED,
            created_at=now,
            updated_at=now,
        )
        self._stores.review_sessions.put(session)
        try:
            self._record(project.project_id, "review.session_created", session)
            if mode is ReviewMode.IDEA:
                return self._view(session)
            assert isinstance(command.source, UploadedScript)
            assert parsed is not None
            return self._start_script(session, command.source, parsed)
        except Exception as exc:
            current = self._stores.review_sessions.get(session.review_id) or session
            code = getattr(getattr(exc, "code", None), "value", None)
            failed = self._updated(
                current,
                state=ReviewState.FAILED,
                error_code=code or type(exc).__name__,
                error_message=str(exc),
            )
            try:
                self._stores.review_sessions.put(failed)
            except Exception:
                pass
            raise

    def _start_script(
        self, session: ReviewSession, source: UploadedScript, parsed: ParsedScript
    ) -> ReviewView:
        filename = (
            Path(source.filename.replace("\\", "/")).name or "script.md"
        )
        normalized_uri = (
            f"blob://{session.project_id}/{session.review_id}/normalized-text"
        )
        self._stores.blobs.put(normalized_uri, parsed.text.encode("utf-8"))
        ticket = self._workflow.issue_upload_ticket(
            session.project_id,
            AssetKind.SCRIPT,
            session.owner_uid,
            filename,
        )
        asset = self._workflow.complete_upload(
            ticket.ticket_id,
            source.content,
            text_storage_uri=normalized_uri,
        )
        session = self._updated(
            session,
            state=ReviewState.EXTRACTING,
            asset_version=asset.version_id,
            source_filename=filename,
            source_sha256=asset.sha256,
            normalized_text_uri=normalized_uri,
            intake_status=IntakeStatus.RUNNING,
        )
        self._stores.review_sessions.put(session)
        self._record(session.project_id, "review.source_normalized", session)

        analysis = self._intake.analyze(parsed, self._threshold_options())
        session = self._updated(
            session,
            state=ReviewState.AWAITING_CONFIRMATION,
            candidates=analysis.candidates,
            intake_status=analysis.status,
            intake_pending_flags=analysis.pending_flags,
        )
        self._stores.review_sessions.put(session)
        self._record(
            session.project_id,
            "review.candidates_prepared",
            session,
            {"backend": analysis.backend},
        )
        return self._view(session)

    def get(self, review_id: str, actor_uid: str) -> ReviewView:
        return self._view(self._owned(review_id, actor_uid))

    def confirm(
        self,
        review_id: str,
        actor_uid: str,
        details: ConfirmedReviewDetails,
    ) -> ReviewView:
        session = self._owned(review_id, actor_uid)
        if session.state is ReviewState.COMPLETE:
            if session.confirmed == details:
                return self._view(session)
            raise StateInvalidError("this review has already been completed")
        if session.state is not ReviewState.AWAITING_CONFIRMATION:
            raise StateInvalidError(
                "review details can only be confirmed at the confirmation step",
                {"state": session.state.value},
            )

        session = self._updated(
            session,
            state=ReviewState.ANALYZING,
            confirmed=details,
        )
        if not self._stores.review_sessions.compare_and_put(
            review_id, ReviewState.AWAITING_CONFIRMATION, session
        ):
            current = self._owned(review_id, actor_uid)
            if current.state is ReviewState.COMPLETE and current.confirmed == details:
                return self._view(current)
            raise StateInvalidError(
                "review confirmation is already being processed",
                {"state": current.state.value},
            )
        return self._analyze_claimed(session)

    def reanalyze(
        self,
        review_id: str,
        owner_uid: str,
        details: ConfirmedReviewDetails,
    ) -> ReviewView:
        session = self._owned(review_id, owner_uid)
        if session.state is not ReviewState.COMPLETE:
            raise StateInvalidError(
                "only a completed review can be reanalyzed",
                {"state": session.state.value},
            )
        if session.confirmed == details:
            return self._view(session)

        analyzing = self._updated(
            session,
            state=ReviewState.ANALYZING,
            confirmed=details,
            semantic_status=None,
        )
        if not self._stores.review_sessions.compare_and_put(
            review_id, ReviewState.COMPLETE, analyzing
        ):
            current = self._owned(review_id, owner_uid)
            raise StateInvalidError(
                "review reanalysis is already being processed",
                {"state": current.state.value},
            )
        return self._analyze_claimed(analyzing)

    def _analyze_claimed(self, session: ReviewSession) -> ReviewView:
        try:
            assert session.confirmed is not None
            self._workflow.apply_review_confirmation(
                session.project_id, session.mode, session.confirmed
            )
            self._workflow.run_classification(session.project_id)
            semantic_status = None
            if session.mode is ReviewMode.SCRIPT:
                _, _, result = self._workflow.run_script_review(session.project_id)
                semantic_status = (
                    SemanticStatus.PENDING
                    if "script_semantic_check_pending" in result.pending_flags
                    else SemanticStatus.COMPLETE
                )
            draft = self._workflow.form_draft(session.project_id)
            applicant = draft.fields.get("applicant_entity")
            if applicant is not None and applicant.status is FieldStatus.PENDING:
                self._workflow.defer_form_field(
                    session.project_id,
                    "applicant_entity",
                    "To be supplied by filing institution",
                )
            session = self._updated(
                session,
                state=ReviewState.COMPLETE,
                semantic_status=semantic_status,
            )
            self._stores.review_sessions.put(session)
            self._record(session.project_id, "review.package_ready", session)
            return self._view(session)
        except Exception as exc:
            code = getattr(getattr(exc, "code", None), "value", None)
            failed = self._updated(
                session,
                state=ReviewState.FAILED,
                error_code=code or type(exc).__name__,
                error_message=str(exc),
            )
            self._stores.review_sessions.put(failed)
            raise

    def retry_intake(self, review_id: str, actor_uid: str) -> ReviewView:
        session = self._owned(review_id, actor_uid)
        if session.state is not ReviewState.AWAITING_CONFIRMATION or (
            session.intake_status
            not in {IntakeStatus.UNAVAILABLE, IntakeStatus.PARTIAL}
        ):
            raise StateInvalidError("intake extraction is not retryable now")
        assert session.normalized_text_uri is not None
        content = self._stores.blobs.get(session.normalized_text_uri)
        if content is None:
            raise NotFoundError("normalized script text is missing")
        extracting = self._updated(
            session,
            state=ReviewState.EXTRACTING,
            intake_status=IntakeStatus.RUNNING,
        )
        if not self._stores.review_sessions.compare_and_put(
            review_id, ReviewState.AWAITING_CONFIRMATION, extracting
        ):
            current = self._owned(review_id, actor_uid)
            raise StateInvalidError(
                "review intake is already being processed",
                {"state": current.state.value},
            )
        try:
            parsed = parse_script("normalized.md", content)
            analysis = self._intake.analyze(parsed, self._threshold_options())
            updated = self._updated(
                extracting,
                state=ReviewState.AWAITING_CONFIRMATION,
                candidates=analysis.candidates,
                intake_status=analysis.status,
                intake_pending_flags=analysis.pending_flags,
            )
            if not self._stores.review_sessions.compare_and_put(
                review_id, ReviewState.EXTRACTING, updated
            ):
                raise StateInvalidError("review state changed during intake retry")
            return self._view(updated)
        except Exception as exc:
            code = getattr(getattr(exc, "code", None), "value", None)
            failed = self._updated(
                extracting,
                state=ReviewState.FAILED,
                error_code=code or type(exc).__name__,
                error_message=str(exc),
            )
            self._stores.review_sessions.compare_and_put(
                review_id, ReviewState.EXTRACTING, failed
            )
            raise

    def source(self, review_id: str, actor_uid: str) -> GeneratedArtifact:
        session = self._owned(review_id, actor_uid)
        if session.mode is not ReviewMode.SCRIPT or session.asset_version is None:
            raise StateInvalidError("idea reviews do not have an uploaded source")
        _, content = self._workflow.read_asset(
            session.project_id, session.asset_version
        )
        filename = session.source_filename or "script.md"
        media_type = {
            ".md": "text/markdown",
            ".txt": "text/plain",
            ".docx": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
        }.get(Path(filename).suffix.lower(), "application/octet-stream")
        return GeneratedArtifact(
            filename=filename,
            media_type=media_type,
            content=content,
        )

    def artifact(
        self,
        review_id: str,
        actor_uid: str,
        artifact_type: ReviewArtifactType,
    ) -> GeneratedArtifact:
        session = self._owned(review_id, actor_uid)
        if session.state is not ReviewState.COMPLETE:
            raise StateInvalidError("review artifacts are available after analysis")
        if (
            session.mode is ReviewMode.IDEA
            and artifact_type is not ReviewArtifactType.FORM
        ):
            raise ArtifactUnavailableError(
                "idea reviews expose only the review form",
                {"artifact_type": artifact_type.value},
            )
        if session.confirmed is None:
            raise StateInvalidError("completed review details are missing")

        view = self._view(session)
        if view.classification is None:
            raise StateInvalidError("review classification is missing")
        draft = self._stores.forms.latest(session.project_id)
        if draft is None:
            raise StateInvalidError("review form draft is missing")

        source_text = None
        if session.normalized_text_uri is not None:
            content = self._stores.blobs.get(session.normalized_text_uri)
            if content is None:
                raise NotFoundError("normalized script text is missing")
            source_text = content.decode("utf-8")

        package = ReviewPackage(
            review_id=session.review_id,
            mode=session.mode,
            confirmed=session.confirmed.model_copy(deep=True),
            classification=view.classification.model_copy(deep=True),
            findings=tuple(item.model_copy(deep=True) for item in view.findings),
            semantic_status=session.semantic_status,
            form_fields=tuple(
                ArtifactFormField(
                    key=key,
                    value=field.display_value,
                    status=field.status.value,
                )
                for key, field in sorted(draft.fields.items())
            ),
            source_text=source_text,
            source_filename=session.source_filename,
            source_sha256=session.source_sha256,
        )
        try:
            return self._artifact_composer.compose(package, artifact_type)
        except Exception as exc:
            raise ArtifactGenerationFailedError(
                "could not generate the requested review artifact",
                {"artifact_type": artifact_type.value},
            ) from exc

    def _owned(self, review_id: str, actor_uid: str) -> ReviewSession:
        session = self._stores.review_sessions.get(review_id)
        if session is None:
            raise NotFoundError(f"review not found: {review_id}")
        if session.owner_uid != actor_uid:
            raise ForbiddenError("this review belongs to another creator")
        return session

    def _threshold_options(self) -> list[dict]:
        version = self._snapshots.latest_version()
        rows = budget_comparison(self._snapshots, version) or []
        return [
            {
                "value": row["amount_bracket"],
                "label": self._amount_label(
                    row["amount_bracket"], row["lower_rmb"], row["upper_rmb"]
                ),
                "lower_rmb": row["lower_rmb"],
                "upper_rmb": row["upper_rmb"],
            }
            for row in rows
        ]

    @staticmethod
    def _amount_label(bracket: str, lower: int, upper: int) -> str:
        if bracket == "below_lower":
            return f"Below CNY {lower:,}"
        if bracket == "between":
            return f"CNY {lower:,}–{upper:,}"
        return f"CNY {upper:,} or above"

    def _view(self, session: ReviewSession) -> ReviewView:
        if session.state is ReviewState.FAILED:
            return ReviewView(
                review_id=session.review_id,
                state=session.state,
                mode=session.mode,
                candidates=session.candidates,
                confirmed=session.confirmed,
                intake_status=session.intake_status,
                semantic_status=session.semantic_status,
                source_filename=session.source_filename,
                source_sha256=session.source_sha256,
                source_download_url=(
                    f"/v1/reviews/{session.review_id}/source"
                    if session.mode is ReviewMode.SCRIPT
                    and session.asset_version is not None
                    else None
                ),
                amount_options=[],
                classification=None,
                findings=[],
                artifacts=[],
                failure_message=(
                    "We couldn't complete this review. Start a new review and "
                    "upload the source again."
                ),
            )
        project = self._workflow.get_project(session.project_id)
        findings = sorted(
            self._stores.findings.list(session.project_id),
            key=lambda item: (
                item.locator.episode if item.locator.episode is not None else 10**9,
                item.locator.scene if item.locator.scene is not None else 10**9,
                item.category,
                item.locator.quote,
            ),
        )
        finding_views = [
            ReviewFindingView(
                risk_id=f"RISK-{index:03d}",
                episode=finding.locator.episode,
                scene=finding.locator.scene,
                line=finding.locator.line,
                match_lines=finding.locator.match_lines,
                quote=finding.locator.quote,
                category=finding.category,
                status=_SEVERITY_NAMES[finding.severity],
                evidence_refs=finding.evidence_refs,
                explanation=(
                    finding.alert.risk_reason if finding.alert is not None else None
                ),
                suggestion=finding.suggestion,
            )
            for index, finding in enumerate(findings, start=1)
        ]

        classification = None
        if project.classification is not None:
            categories = {item.category for item in findings}
            rules = load_subject_rules(
                self._snapshots.get_pack(
                    PackName.P2_SUBJECT_RULES,
                    project.classification.policy_snapshot_version,
                )
            )
            category_by_rule = {rule.rule_id: rule.category for rule in rules}
            categories.update(
                category_by_rule[matched.rule_id]
                for matched in project.classification.matched_rules
                if matched.rule_id in category_by_rule
            )
            subjects = sorted(
                _CATEGORY_NAMES.get(category, category.replace("_", " "))
                for category in categories
            )
            classification = ReviewClassificationView(
                class_name=_CLASS_NAMES[project.classification.tier],
                co_review_required=project.classification.co_review_required,
                subjects=subjects,
                snapshot_version=project.classification.policy_snapshot_version,
                evidence_refs=project.classification.evidence_refs,
                route=project.classification.filing_route,
            )

        artifacts: list[ReviewArtifactLink] = []
        if session.state is ReviewState.COMPLETE:
            types = [ReviewArtifactType.FORM]
            if session.mode is ReviewMode.SCRIPT:
                types.extend(
                    [
                        ReviewArtifactType.SUMMARY,
                        ReviewArtifactType.ANNOTATED_SCRIPT,
                    ]
                )
            artifacts = [
                ReviewArtifactLink(
                    artifact_type=artifact_type,
                    filename=_ARTIFACT_FILES[artifact_type],
                    download_url=(
                        f"/v1/reviews/{session.review_id}/artifacts/"
                        f"{artifact_type.value}"
                    ),
                )
                for artifact_type in types
            ]

        return ReviewView(
            review_id=session.review_id,
            state=session.state,
            mode=session.mode,
            candidates=session.candidates,
            confirmed=session.confirmed,
            intake_status=session.intake_status,
            semantic_status=session.semantic_status,
            source_filename=session.source_filename,
            source_sha256=session.source_sha256,
            source_download_url=(
                f"/v1/reviews/{session.review_id}/source"
                if session.mode is ReviewMode.SCRIPT
                else None
            ),
            amount_options=[
                ReviewAmountOption.model_validate(option)
                for option in self._threshold_options()
            ],
            classification=classification,
            findings=finding_views,
            artifacts=artifacts,
            failure_message=(
                "We couldn't complete this review. Start a new review and upload "
                "the source again."
                if session.state is ReviewState.FAILED
                else None
            ),
        )

    def _updated(self, session: ReviewSession, **changes) -> ReviewSession:
        payload = session.model_dump()
        payload.update(changes)
        payload["updated_at"] = self._clock.now()
        return ReviewSession.model_validate(payload)

    def _record(
        self,
        project_id: str,
        event: str,
        session: ReviewSession,
        extra: dict | None = None,
    ) -> None:
        detail = {
            "review_id": session.review_id,
            "state": session.state.value,
        }
        if session.source_sha256:
            detail["sha256"] = session.source_sha256
        detail.update(extra or {})
        self._workflow.record_review_event(project_id, event, detail)
