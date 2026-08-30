from __future__ import annotations

from pathlib import Path
import re

import pytest

from core.review import split_scenes
from core.script_text import parse_script


FIXTURES = Path(__file__).parent / "fixtures" / "scripts"
MACHINE_TOKEN = re.compile(
    r"\b(?:[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+|"
    r"[a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b"
)
BACKTICK_IDENTIFIER = re.compile(r"`([^`\s]*[_-][^`\s]*)`")


@pytest.mark.parametrize(
    "name,title,episodes,minutes,scene_count,machine_key",
    [
        (
            "e2e-30min-public-security-en.md",
            "Hang Up First",
            1,
            30,
            15,
            "public_security",
        ),
        (
            "e2e-70min-judicial-long-context-en.md",
            "The Blank Byline",
            7,
            70,
            28,
            "judicial",
        ),
    ],
)
def test_english_fixture_contract(
    name: str,
    title: str,
    episodes: int,
    minutes: int,
    scene_count: int,
    machine_key: str,
) -> None:
    path = FIXTURES / name
    raw = path.read_bytes()
    decoded = raw.decode("utf-8", errors="strict")
    parsed = parse_script(name, raw)
    scenes = split_scenes(parsed.text)
    located = {
        (scene.episode, scene.scene)
        for scene in scenes
        if scene.episode is not None and scene.scene is not None
    }

    assert path.suffix == ".md"
    assert decoded.encode("utf-8") == raw
    assert parsed.title == title
    assert parsed.structure.source_episode_count == episodes
    assert parsed.structure.source_total_minutes == minutes
    assert parsed.structure.source_scene_count == scene_count
    assert max(scene.episode or 0 for scene in scenes) == episodes
    assert len(located) == scene_count
    assert machine_key in parsed.text

    boundary = parsed.text.lower()
    assert "synthetic" in boundary
    assert "unreviewed" in boundary
    assert "not legal guidance" in boundary


@pytest.mark.parametrize(
    "source_name,translation_name",
    [
        (
            "e2e-30min-public-security.md",
            "e2e-30min-public-security-en.md",
        ),
        (
            "e2e-70min-judicial-long-context.md",
            "e2e-70min-judicial-long-context-en.md",
        ),
    ],
)
def test_english_fixture_preserves_every_machine_token_and_appendix_item(
    source_name: str, translation_name: str
) -> None:
    source = (FIXTURES / source_name).read_text(encoding="utf-8")
    translation = (FIXTURES / translation_name).read_text(encoding="utf-8")

    source_tokens = set(MACHINE_TOKEN.findall(source))
    translation_tokens = set(MACHINE_TOKEN.findall(translation))
    assert source_tokens <= translation_tokens, sorted(source_tokens - translation_tokens)

    source_identifiers = set(BACKTICK_IDENTIFIER.findall(source))
    translation_identifiers = set(BACKTICK_IDENTIFIER.findall(translation))
    assert source_identifiers <= translation_identifiers, sorted(
        source_identifiers - translation_identifiers
    )

    assert source.count("- [x]") == translation.count("- [x]")
    assert "## 生成与测试检查项" in source
    assert "## Appendix: Generation and Test Checklist" in translation

    source_blocks = [block for block in source.split("\n\n") if block.strip()]
    translation_blocks = [
        block for block in translation.split("\n\n") if block.strip()
    ]
    assert len(translation_blocks) == len(source_blocks)

    source_tables = [line for line in source.splitlines() if line.startswith("|")]
    translation_tables = [
        line for line in translation.splitlines() if line.startswith("|")
    ]
    assert len(translation_tables) == len(source_tables)

    source_lines = source.splitlines()
    translation_lines = translation.splitlines()
    assert len(translation_lines) in {len(source_lines), len(source_lines) + 1}
    assert translation.count("\n---\n") == source.count("\n---\n")

    source_cues = [
        line for line in source_lines if line.startswith("**") and line.endswith("**")
    ]
    translation_cues = [
        line
        for line in translation_lines
        if line.startswith("**") and line.endswith("**")
    ]
    # A translated inline-emphasis sentence may become a fully bold line, but
    # no source cue or slug line may disappear.
    assert len(translation_cues) in {len(source_cues), len(source_cues) + 1}

    source_scene_starts = [
        index
        for index, line in enumerate(source_lines)
        if line.startswith("### 第") and "场景" in line
    ]
    translation_scene_starts = [
        index
        for index, line in enumerate(translation_lines)
        if line.startswith("### Episode ") and " Scene " in line
    ]
    source_appendix = source_lines.index("## 生成与测试检查项")
    translation_appendix = translation_lines.index(
        "## Appendix: Generation and Test Checklist"
    )
    source_scene_ends = source_scene_starts[1:] + [source_appendix]
    translation_scene_ends = translation_scene_starts[1:] + [translation_appendix]
    assert [
        end - start for start, end in zip(source_scene_starts, source_scene_ends)
    ] == [
        end - start
        for start, end in zip(translation_scene_starts, translation_scene_ends)
    ]

    assert "ZXQ" not in translation
    han_fragments = set(re.findall(r"[\u3400-\u9fff]+", translation))
    assert han_fragments <= {"苏国良", "真实经历", "确认版"}


def test_english_fixtures_preserve_reviewed_semantic_anchors() -> None:
    thirty = (FIXTURES / "e2e-30min-public-security-en.md").read_text(
        encoding="utf-8"
    )
    seventy = (
        FIXTURES / "e2e-70min-judicial-long-context-en.md"
    ).read_text(encoding="utf-8")

    assert "Expected deterministic findings: at least 5" in thirty
    assert "deterministic findings are retained" in thirty
    assert "Anticipated life" not in thirty
    assert "tweezers" in thirty
    assert "still needs a matching part" in thirty

    assert (
        "Episode 4 Scenes 1 and 2; Episode 6 Scenes 1, 2, and 4; "
        "Episode 7 Scenes 1 and 3"
    ) in seventy
    assert "Act Two, Scene Six" in seventy
    assert (
        "You came to collect Teacher Mei's belongings, not rewrite the play."
        in seventy
    )
