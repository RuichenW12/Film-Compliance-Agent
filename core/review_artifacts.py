"""Pure rendering for the immutable creator review package."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from io import BytesIO
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from schemas.reviews import (
    ConfirmedReviewDetails,
    GeneratedArtifact,
    ReviewArtifactType,
    ReviewClassificationView,
    ReviewFindingView,
    ReviewMode,
    SemanticStatus,
)


DEMO_FIXTURE_SHA256 = (
    "e172493cb8691a6ee4a7e6c8e10e737bfc2672e7a2f532deb81f84e5e1b44005"
)


@dataclass(frozen=True)
class ArtifactFormField:
    key: str
    value: str
    status: str


@dataclass(frozen=True)
class ReviewPackage:
    """A store-free snapshot consumed by the renderer."""

    review_id: str
    mode: ReviewMode
    confirmed: ConfirmedReviewDetails
    classification: ReviewClassificationView
    findings: tuple[ReviewFindingView, ...]
    semantic_status: SemanticStatus | None
    form_fields: tuple[ArtifactFormField, ...]
    source_text: str | None = None
    source_filename: str | None = None
    source_sha256: str | None = None


class ArtifactComposer:
    """Render a package without reading stores or rerunning analysis."""

    def compose(
        self, package: ReviewPackage, artifact_type: ReviewArtifactType
    ) -> GeneratedArtifact:
        if artifact_type is ReviewArtifactType.FORM:
            return GeneratedArtifact(
                filename="project-review-form.pdf",
                media_type="application/pdf",
                content=self._pdf(
                    "Project Review Form", self._form_lines(package)
                ),
            )
        if artifact_type is ReviewArtifactType.SUMMARY:
            return GeneratedArtifact(
                filename="risk-summary.pdf",
                media_type="application/pdf",
                content=self._pdf("Risk Summary", self._summary_lines(package)),
            )
        if artifact_type is ReviewArtifactType.ANNOTATED_SCRIPT:
            return GeneratedArtifact(
                filename="annotated-script.md",
                media_type="text/markdown; charset=utf-8",
                content=self._annotated_script(package).encode("utf-8"),
            )
        raise ValueError(f"unsupported artifact type: {artifact_type}")

    @staticmethod
    def _classification_lines(package: ReviewPackage) -> list[str]:
        result_view = package.classification
        route = result_view.route or {}
        lines = [
            f"Classification boundary: {result_view.class_name}",
            (
                "Co-review required: Yes"
                if result_view.co_review_required
                else "Co-review required: No"
            ),
            "Subject categories: "
            + (", ".join(result_view.subjects) or "None identified"),
            f"Policy snapshot: {result_view.snapshot_version}",
            "Classification evidence: "
            + (
                ", ".join(
                    f"{ref.clause_id} ({ref.regime.value})"
                    for ref in result_view.evidence_refs
                )
                or "No clause reference available; human review boundary applies"
            ),
        ]
        for label, key in (
            ("Routing authority", "authority"),
            ("Pre-shoot filing", "pre_shoot_filing"),
            ("Result document", "result_document"),
        ):
            value = route.get(key)
            if value is not None:
                lines.append(f"{label}: {str(value).replace('_', ' ')}")
        return lines

    def _form_lines(self, package: ReviewPackage) -> list[str]:
        details = package.confirmed
        fields = {field.key: field for field in package.form_fields}
        applicant = fields.get("applicant_entity")
        applicant_value = (
            applicant.value
            if applicant and applicant.status == "filled"
            else "To be supplied by filing institution"
        )
        lines = [
            (
                "Boundary: Review preparation only; not a filing submission, "
                "legal advice, official approval, or production clearance."
            ),
            f"Title: {details.title}",
            f"Tags: {', '.join(details.tags)}",
            f"Synopsis: {details.synopsis}",
            f"Episode count: {details.episode_count}",
            f"Episode length (minutes): {details.episode_minutes:g}",
            "Investment category: " + self._amount_bracket_label(
                details.amount_bracket.value
            ),
            f"Applicant entity: {applicant_value}",
            "",
            *self._classification_lines(package),
            "",
            "Mapped form fields:",
        ]
        lines.extend(
            f"{field.key}: {field.value} [{field.status}]"
            for field in package.form_fields
        )
        return lines

    def _summary_lines(self, package: ReviewPackage) -> list[str]:
        semantic = (
            package.semantic_status.value.title()
            if package.semantic_status is not None
            else "Not applicable"
        )
        category_counts = Counter(item.category for item in package.findings)
        status_counts = Counter(item.status for item in package.findings)
        lines = [
            *self._classification_lines(package),
            f"Semantic status: {semantic}",
            "Counts by category: " + (
                ", ".join(
                    f"{self._human_label(key)}={value}"
                    for key, value in sorted(category_counts.items())
                )
                or "none"
            ),
            "Counts by status: " + (
                ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items()))
                or "none"
            ),
            (
                "Evidence boundary: Findings marked Needs human review are "
                "signals for review, not legal conclusions. This preparation "
                "is not legal advice or official approval. Uploaded content is "
                "user-supplied and not independently verified."
            ),
            (
                "Fixture provenance: Synthetic and externally unreviewed demo "
                "fixture; not an industry-approved or legal benchmark."
                if package.source_sha256 == DEMO_FIXTURE_SHA256
                else "Source provenance: User supplied; external review status unknown."
            ),
            "",
        ]
        if not package.findings:
            lines.append("No script findings were produced.")
            return lines
        for finding in package.findings:
            location = " / ".join(
                part
                for part in (
                    f"Episode {finding.episode}" if finding.episode else "",
                    f"Scene {finding.scene}" if finding.scene else "",
                )
                if part
            ) or "Location unavailable"
            evidence = ", ".join(
                f"{ref.clause_id} ({ref.regime.value})"
                for ref in finding.evidence_refs
            ) or "No clause reference; human confirmation required"
            lines.extend(
                [
                    f"{finding.risk_id} - {finding.status}",
                    f"Location: {location}",
                    f"Category: {self._human_label(finding.category)}",
                    f"Quote: {finding.quote}",
                    f"Explanation: {finding.explanation or 'Not supplied'}",
                    f"Suggestion: {finding.suggestion or 'Review manually'}",
                    f"Evidence: {evidence}",
                    "",
                ]
            )
        return lines

    @staticmethod
    def _human_label(value: str) -> str:
        normalized = value.replace("_", " ").strip()
        return normalized[:1].upper() + normalized[1:]

    @staticmethod
    def _amount_bracket_label(value: str) -> str:
        return {
            "below_lower": "Below the lower policy threshold",
            "between": "Between the lower and upper policy thresholds",
            "at_or_above_upper": "At or above the upper policy threshold",
        }.get(value, ArtifactComposer._human_label(value))

    @staticmethod
    def _annotated_script(package: ReviewPackage) -> str:
        if package.source_text is None:
            raise ValueError("annotated scripts require normalized source text")

        findings_by_line: dict[int, list[ReviewFindingView]] = {}
        findings_by_quote: dict[str, list[ReviewFindingView]] = {}
        for finding in package.findings:
            if finding.line is not None:
                findings_by_line.setdefault(finding.line, []).append(finding)
            findings_by_quote.setdefault(finding.quote.strip(), []).append(finding)

        rendered: list[str] = [
            "<!-- Derived review copy from normalized script text; download "
            "Original source for the exact uploaded bytes. -->\n"
        ]
        inserted: set[str] = set()
        for line_number, source_line in enumerate(
            package.source_text.splitlines(keepends=True), start=1
        ):
            rendered.append(source_line)
            matches = findings_by_line.get(line_number, [])
            if not matches:
                matches = findings_by_quote.get(
                    source_line.rstrip("\r\n").strip(), []
                )
            for finding in matches:
                if finding.risk_id in inserted:
                    continue
                if source_line and not source_line.endswith(("\n", "\r")):
                    rendered.append("\n")
                rendered.append(ArtifactComposer._annotation(finding))
                inserted.add(finding.risk_id)

        missing = [
            finding
            for finding in package.findings
            if finding.risk_id not in inserted
        ]
        if missing:
            if rendered and not rendered[-1].endswith("\n"):
                rendered.append("\n")
            rendered.append("\n<!-- Review notes without an exact line match -->\n")
            rendered.extend(ArtifactComposer._annotation(item) for item in missing)
        return "".join(rendered)

    @staticmethod
    def _annotation(finding: ReviewFindingView) -> str:
        def safe(value: str) -> str:
            return value.replace("--", "-").replace("\r", " ").replace("\n", " ")

        evidence = ", ".join(ref.clause_id for ref in finding.evidence_refs)
        parts = [
            finding.risk_id,
            finding.status,
            f"category={finding.category}",
        ]
        if evidence:
            parts.append(f"evidence={evidence}")
        if finding.suggestion:
            parts.append(f"suggestion={safe(finding.suggestion)}")
        parts.append(
            "explanation="
            + safe(
                finding.explanation
                or "Human confirmation is required for this review signal"
            )
        )
        return f"<!-- {' | '.join(safe(part) for part in parts)} -->\n"

    @staticmethod
    def _pdf(title: str, lines: list[str]) -> bytes:
        """Use deterministic, uncompressed pages so artifacts are testable."""

        buffer = BytesIO()
        document = canvas.Canvas(
            buffer,
            pagesize=A4,
            pageCompression=0,
            invariant=1,
        )
        document.setTitle(title)
        _, height = A4
        left = 54
        top = height - 54
        bottom = 54
        line_height = 15
        y = top

        try:
            pdfmetrics.getFont("STSong-Light")
        except KeyError:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

        def draw(value: str, *, heading: bool = False) -> None:
            nonlocal y
            wrapped = textwrap.wrap(
                value,
                width=88,
                replace_whitespace=False,
                drop_whitespace=True,
            ) or [""]
            for segment in wrapped:
                if y < bottom:
                    document.showPage()
                    y = top
                font = (
                    "STSong-Light"
                    if any(ord(character) > 127 for character in segment)
                    else "Helvetica-Bold" if heading else "Helvetica"
                )
                document.setFont(font, 14 if heading else 9.5)
                document.drawString(left, y, segment)
                y -= 20 if heading else line_height

        draw(title, heading=True)
        y -= 6
        for line in lines:
            draw(line)
        document.save()
        return buffer.getvalue()
