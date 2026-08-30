"""Safe, deterministic text extraction for creator-supplied scripts."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError

from core.errors import (
    ScriptTooLargeError,
    UnreadableScriptError,
    UnsupportedScriptTypeError,
)
from schemas.common import DomainModel
from schemas.reviews import ScriptStructure


MAX_SCRIPT_BYTES = 5 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 25 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
SUPPORTED_EXTENSIONS = frozenset({".md", ".txt", ".docx"})

_TITLE = re.compile(
    r"^#\s+(?:《(?P<bracketed>[^》]+)》|(?P<plain>.+?))[ \t]*$",
    re.MULTILINE,
)
_EPISODE_COUNT = re.compile(
    r"^-\s*(?:集数：\s*|Episodes?:\s*)(\d+)(?:\s*集|\s*episodes?)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_TOTAL_MINUTES = re.compile(
    r"^-\s*(?:目标时长：\s*约?\s*|(?:Target|Total)\s+runtime:\s*)"
    r"(\d+(?:\.\d+)?)(?:\s*分钟|\s*minutes?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_SCENE_HEADING = re.compile(
    r"^###\s+(?:第.+?集\s+场景.+?：|Episode\s+\d+\s+Scene\s+\d+\s*:)",
    re.IGNORECASE | re.MULTILINE,
)
_NUMBERED_SCENE = re.compile(
    r"^\s*第\s*\d+\s*集\s*[/·-]\s*第\s*\d+\s*场", re.MULTILINE
)


class ParsedScript(DomainModel):
    text: str
    structure: ScriptStructure
    title: str | None = None
    title_quote: str | None = None


def _decode_text(content: bytes) -> str:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UnreadableScriptError("script must be valid UTF-8") from exc
    return text.removeprefix("\ufeff")


def _docx_text(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            expanded = sum(member.file_size for member in members)
            suspicious_ratio = any(
                member.file_size > 0
                and (
                    member.compress_size == 0
                    or member.file_size / member.compress_size
                    > MAX_DOCX_COMPRESSION_RATIO
                )
                for member in members
            )
            if expanded > MAX_DOCX_UNCOMPRESSED_BYTES or suspicious_ratio:
                raise UnreadableScriptError(
                    "DOCX expansion exceeds the safe parsing limit"
                )
    except BadZipFile as exc:
        raise UnreadableScriptError(
            "script is not a readable DOCX document"
        ) from exc
    try:
        document = Document(BytesIO(content))
    except (
        BadZipFile,
        KeyError,
        PackageNotFoundError,
        ValueError,
        XMLSyntaxError,
    ) as exc:
        raise UnreadableScriptError("script is not a readable DOCX document") from exc

    lines: list[str] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = Paragraph(child, document).text
            if text.strip():
                lines.append(text)
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        text = paragraph.text
                        if text.strip():
                            lines.append(text)
    return "\n".join(lines)


def _structure(text: str) -> ScriptStructure:
    episode = _EPISODE_COUNT.search(text)
    duration = _TOTAL_MINUTES.search(text)
    scene_headings = _SCENE_HEADING.findall(text)
    if not scene_headings:
        scene_headings = _NUMBERED_SCENE.findall(text)
    return ScriptStructure(
        source_episode_count=int(episode.group(1)) if episode else None,
        source_total_minutes=float(duration.group(1)) if duration else None,
        source_scene_count=len(scene_headings),
    )


def parse_script(filename: str, content: bytes) -> ParsedScript:
    """Parse supported script bytes without interpreting document instructions."""

    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedScriptTypeError(
            "script must be a Markdown, text, or DOCX file",
            details={"extension": extension or None},
        )
    if len(content) > MAX_SCRIPT_BYTES:
        raise ScriptTooLargeError(
            "script exceeds the 5 MiB upload limit",
            details={"max_bytes": MAX_SCRIPT_BYTES},
        )

    text = _docx_text(content) if extension == ".docx" else _decode_text(content)
    if not text.strip():
        raise UnreadableScriptError("script is empty")

    title_match = _TITLE.search(text)
    title = None
    title_quote = None
    if title_match:
        title = title_match.group("bracketed") or title_match.group("plain")
        title = title.strip()
        title_quote = title_match.group(0)

    return ParsedScript(
        text=text,
        title=title,
        title_quote=title_quote,
        structure=_structure(text),
    )
