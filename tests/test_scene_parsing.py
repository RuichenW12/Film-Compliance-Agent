"""Scene attribution in C1-a, driven by the synthetic scripts in fixtures/.

Every one of these cases came from running the real fixtures rather than from
imagination: the parser originally attributed findings to bare lines, reviewed
the documents' own disclaimers, invented a scene 47 out of "第47版", and filed
appendix text under the last episode.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.classify.subject_rules import load_subject_rules
from core.llm import UnavailableLLM
from core.review import review_script, split_scenes
from schemas.policy_snapshot import PackName
from schemas.snapshot import FileSnapshotService

SCRIPTS = Path(__file__).parent / "fixtures" / "scripts"
SEED = Path(__file__).resolve().parents[1] / "policy" / "seed-snapshot-v1.yaml"


@pytest.fixture(scope="module")
def rules():
    snapshots = FileSnapshotService(SEED)
    return load_subject_rules(
        snapshots.get_pack(PackName.P2_SUBJECT_RULES, snapshots.latest_version())
    )


def fixture(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


# ---------------------------------------------------------- the two heading forms


def test_episode_and_scene_on_one_line_still_work():
    """The plain form: 第一集 场景二 on the same line."""

    scenes = split_scenes(
        "第一集 场景一：码头。卧底警察与线人接头。\n"
        "第一集 场景二：派出所。民警审讯。\n"
    )
    assert [(s.episode, s.scene) for s in scenes] == [(1, 1), (1, 2)]


def test_a_body_line_inherits_the_heading_above_it():
    """The markdown form: an episode heading, then slug lines, then prose."""

    scenes = split_scenes(
        "### 第1集《海报上的名字》\n"
        "\n"
        "**内景·排练厅·上午**\n"
        "\n"
        "空舞台中央摆着一把木椅。\n"
        "\n"
        "**外景·剧场门口·夜**\n"
        "\n"
        "两人在门口告别。\n"
    )
    body = [s for s in scenes if "木椅" in s.quote or "告别" in s.quote]
    assert [(s.episode, s.scene) for s in body] == [(1, 1), (1, 2)]


def test_a_plain_script_with_no_episode_headings_is_reviewed_whole():
    """Skipping a preamble must not swallow a script that never declares one."""

    scenes = split_scenes("码头。卧底警察与线人接头。\n派出所。民警审讯。\n")
    assert len(scenes) == 2
    assert all(scene.episode is None for scene in scenes)


# ------------------------------------------------------- what must not be reviewed


def test_a_blockquote_disclaimer_is_not_reviewed(rules):
    """The fixtures' own disclaimers mention 庭审; they are commentary, not script."""

    document = (
        "# 《空白署名》\n"
        "\n"
        "> 合成测试剧本。其中的合同、调解和庭审情节均为戏剧化虚构。\n"
        "\n"
        "### 第1集\n"
        "\n"
        "**内景·排练厅·上午**\n"
        "\n"
        "两人排练。\n"
    )
    result = review_script(document, rules, UnavailableLLM())
    assert result.findings == []


def test_front_matter_above_the_first_episode_is_not_reviewed(rules):
    document = (
        "# 标题\n"
        "\n"
        "## 测试定位\n"
        "\n"
        "- 核心用途：验证法院与庭审场景的定位\n"
        "\n"
        "### 第1集\n"
        "\n"
        "**内景·排练厅·上午**\n"
        "\n"
        "两人排练。\n"
    )
    result = review_script(document, rules, UnavailableLLM())
    assert result.findings == []


def test_an_appendix_is_not_filed_under_the_last_episode(rules):
    """A section heading that is not an episode closes the one before it."""

    document = (
        "### 第7集\n"
        "\n"
        "**内景·剧场·夜**\n"
        "\n"
        "首演结束。\n"
        "\n"
        "## 附录：角色表\n"
        "\n"
        "`CH-003 法官`：在法院工作，负责庭审记录。\n"
    )
    result = review_script(document, rules, UnavailableLLM())
    assert result.findings == []


def test_a_version_number_is_not_a_scene_number():
    """"第47版" once became scene 47, because the 场 was optional."""

    scenes = split_scenes(
        "### 第1集\n"
        "\n"
        "**内景·排练厅·上午**\n"
        "\n"
        "第47版海报仍然没有定稿。\n"
    )
    body = [s for s in scenes if "海报" in s.quote]
    assert body[0].scene == 1


# --------------------------------------------------- the real fixtures, end to end


def test_the_clean_baseline_reports_nothing_but_stays_pending(rules):
    result = review_script(fixture("e2e-10min-clean-baseline.md"), rules, UnavailableLLM())
    assert result.findings == []
    assert result.pending_flags == ["script_semantic_check_pending"]


def test_the_public_security_fixture_meets_its_stated_minimum(rules):
    """The fixture documents 预期确定性命中：不少于 5 条."""

    result = review_script(
        fixture("e2e-30min-public-security.md"), rules, UnavailableLLM()
    )
    assert len(result.findings) >= 5
    assert {finding.category for finding in result.findings} == {"public_security"}


def test_every_finding_in_a_long_script_can_be_located(rules):
    """A finding a creator cannot navigate to is not much use."""

    result = review_script(
        fixture("e2e-70min-judicial-long-context.md"), rules, UnavailableLLM()
    )
    assert result.findings
    assert all(finding.scene.episode is not None for finding in result.findings)


def test_the_long_fixture_covers_the_scenes_it_says_it_covers(rules):
    """预期可定位场次：第4集第1、2场，第6集第1、2、4场，第7集第1、3场."""

    result = review_script(
        fixture("e2e-70min-judicial-long-context.md"), rules, UnavailableLLM()
    )
    located = {
        (finding.scene.episode, finding.scene.scene) for finding in result.findings
    }
    expected = {(4, 1), (4, 2), (6, 1), (6, 2), (6, 4), (7, 1), (7, 3)}
    assert expected <= located, f"missing {sorted(expected - located)}"


def test_a_synthetic_fixture_never_asserts_a_conclusion(rules):
    """Placeholder rules, so every finding routes to a human. See D-018."""

    result = review_script(
        fixture("e2e-70min-judicial-long-context.md"), rules, UnavailableLLM()
    )
    assert {finding.severity.value for finding in result.findings} == {"needs_human"}
