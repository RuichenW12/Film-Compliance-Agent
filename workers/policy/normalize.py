"""Deterministic extraction, normalization, hashing, and policy Diff."""

from __future__ import annotations

from difflib import unified_diff
from hashlib import sha256
import re

from bs4 import BeautifulSoup

from .models import PolicyDiff


class PolicyExtractError(ValueError):
    code = "POLICY_EXTRACT_FAILED"


_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li")


def _normalize_segment(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def normalize_html(content: bytes, selector: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    selected = soup.select_one(selector)
    if selected is None:
        raise PolicyExtractError(f"selector not found: {selector}")

    for noise in selected.select("script, style, noscript"):
        noise.decompose()

    blocks = selected.find_all(_BLOCK_TAGS)
    raw_segments = [block.get_text(" ", strip=True) for block in blocks]
    if not raw_segments:
        raw_segments = [selected.get_text(" ", strip=True)]

    segments = [segment for raw in raw_segments if (segment := _normalize_segment(raw))]
    if not segments:
        raise PolicyExtractError(f"selector has no text: {selector}")
    return "\n".join(segments)


def sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def create_policy_diff(source_id: str, previous: str, current: str) -> PolicyDiff:
    previous_sha256 = sha256_text(previous)
    current_sha256 = sha256_text(current)
    diff_lines = unified_diff(
        previous.splitlines(),
        current.splitlines(),
        fromfile=previous_sha256,
        tofile=current_sha256,
        lineterm="",
    )
    return PolicyDiff(
        source_id=source_id,
        previous_sha256=previous_sha256,
        current_sha256=current_sha256,
        unified_diff="\n".join(diff_lines),
    )
