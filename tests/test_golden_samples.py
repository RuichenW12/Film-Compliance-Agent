"""The C1-a golden-sample harness.

Two jobs, kept separate on purpose:

1. **Run the harness** against synthetic scripts in `tests/fixtures/scripts/`.
   Those prove the machinery works. They are made up, so they prove nothing
   about the law.
2. **Run real golden samples** from `tests/golden/*.yaml` when they exist. A
   sample without `provenance` and `reviewed_by` is rejected rather than
   trusted, so an unreviewed draft cannot become an assertion about the law by
   being dropped in a directory.

With no golden samples present the second job reports a skip naming what is
missing. It never reports a pass — an empty corpus is not evidence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.classify.subject_rules import load_subject_rules
from core.llm import UnavailableLLM
from core.review import review_script
from schemas.policy_snapshot import PackName

GOLDEN_DIR = Path(__file__).parent / "golden"
SCRIPTS_DIR = Path(__file__).parent / "fixtures" / "scripts"
REQUIRED_FIELDS = ("sample_id", "provenance", "reviewed_by", "script", "expected")


def golden_files() -> list[Path]:
    return sorted(GOLDEN_DIR.glob("*.yaml"))


def run_review(script: str, snapshots):
    rules = load_subject_rules(
        snapshots.get_pack(PackName.P2_SUBJECT_RULES, snapshots.latest_version())
    )
    return review_script(script, rules, UnavailableLLM())


# ------------------------------------------------- the harness, on synthetics


def test_the_harness_finds_the_scenes_the_seed_rules_describe(snapshots):
    script = (SCRIPTS_DIR / "public-security.txt").read_text(encoding="utf-8")
    result = run_review(script, snapshots)

    categories = {finding.category for finding in result.findings}
    assert categories == {"public_security"}
    assert all(finding.scene.quote in script for finding in result.findings)


def test_the_harness_reports_nothing_on_a_clean_script(snapshots):
    script = (SCRIPTS_DIR / "clean-romance.txt").read_text(encoding="utf-8")
    result = run_review(script, snapshots)
    assert result.findings == []


def test_synthetic_scripts_never_claim_to_be_reviewed(snapshots):
    """A synthetic sample must not be mistaken for expert-confirmed material."""

    result = run_review(
        (SCRIPTS_DIR / "public-security.txt").read_text(encoding="utf-8"), snapshots
    )
    assert all(finding.expert_pending for finding in result.findings)
    assert all(
        finding.severity.value == "needs_human" for finding in result.findings
    )


# --------------------------------------------------- the corpus, when it exists


def test_the_golden_corpus_is_reported_not_assumed():
    """An empty corpus is a skip with a reason, never a silent pass."""

    files = golden_files()
    if not files:
        pytest.skip(
            "no golden samples yet: add expert-reviewed YAML to tests/golden/ "
            "per SCHEMA.md before claiming C1-a accuracy"
        )
    assert files


@pytest.mark.parametrize("path", golden_files(), ids=lambda p: p.stem)
def test_a_golden_sample_declares_its_provenance(path: Path):
    sample = yaml.safe_load(path.read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_FIELDS if not sample.get(field)]
    assert not missing, f"{path.name} is missing {missing}; see tests/golden/SCHEMA.md"


@pytest.mark.parametrize("path", golden_files(), ids=lambda p: p.stem)
def test_a_golden_sample_reviews_the_way_its_reviewer_said(path: Path, snapshots):
    sample = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = sample["expected"]
    result = run_review(sample["script"], snapshots)

    found = {finding.category for finding in result.findings}
    assert found >= set(expected.get("categories") or []), (
        f"{sample['sample_id']}: expected {expected.get('categories')}, found {sorted(found)}"
    )
    assert len(result.findings) >= int(expected.get("min_findings", 0))
    forbidden = set(expected.get("must_not_report") or []) & found
    assert not forbidden, f"{sample['sample_id']}: false positives {sorted(forbidden)}"
