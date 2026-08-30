from __future__ import annotations

from pathlib import Path

import pytest

from core.review import split_scenes
from core.script_text import parse_script


FIXTURES = Path(__file__).parent / "fixtures" / "scripts"


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
