"""Pure rendering for the immutable creator review package."""

from __future__ import annotations

from dataclasses import dataclass
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
        return [
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
            f"Review ID: {package.review_id}",
            f"Title: {details.title}",
            f"Tags: {', '.join(details.tags)}",
            f"Synopsis: {details.synopsis}",
            f"Episode count: {details.episode_count}",
            f"Episode length (minutes): {details.episode_minutes:g}",
            f"Investment category: {details.amount_bracket.value}",
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
        lines = [
            f"Review ID: {package.review_id}",
            *self._classification_lines(package),
            f"Semantic status: {semantic}",
            (
                "Evidence boundary: Findings marked Needs human review are "
                "signals for review, not legal conclusions."
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
                    f"Category: {finding.category}",
                    f"Quote: {finding.quote}",
                    f"Explanation: {finding.explanation or 'Not supplied'}",
                    f"Suggestion: {finding.suggestion or 'Review manually'}",
                    f"Evidence: {evidence}",
                    "",
                ]
            )
        return lines

    @staticmethod
    def _annotated_script(package: ReviewPackage) -> str:
        if package.source_text is None:
            raise ValueError("annotated scripts require normalized source text")

        findings_by_quote: dict[str, list[ReviewFindingView]] = {}
        for finding in package.findings:
            findings_by_quote.setdefault(finding.quote.strip(), []).append(finding)

        rendered: list[str] = []
        inserted: set[str] = set()
        for source_line in package.source_text.splitlines(keepends=True):
            rendered.append(source_line)
            matches = findings_by_quote.get(source_line.rstrip("\r\n").strip(), [])
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
