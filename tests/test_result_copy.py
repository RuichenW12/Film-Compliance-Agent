"""Every value the result card can name has English copy.

The card renders enum values, filing-route fields and pending flags through
`t()`, which falls back to the key itself when a bundle has no entry. That
fallback is the bug we just fixed by hand: a creator opened the classification
result and read `micro_drama`, `Tier T3` and `script_verify`, because those
were the raw values with nothing behind them.

The fallback is right — a missing string should not crash a page — but nothing
stopped a new enum member from reaching a creator as its own identifier. So
these tests walk the enums the card actually keys off and assert the copy
exists. Adding a tier, a form type or an authority now fails here until it can
be said in words.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemas.enums import FormType, Tier

LOCALES = Path(__file__).resolve().parent.parent / "web" / "locales"


def _en() -> dict[str, str]:
    return json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("form_type", list(FormType))
def test_every_form_type_has_a_name(form_type: FormType) -> None:
    assert f"form_type.{form_type.value}" in _en()


@pytest.mark.parametrize("tier", list(Tier))
def test_every_tier_has_a_name_and_a_meaning(tier: Tier) -> None:
    bundle = _en()
    assert f"tier.{tier.value}.name" in bundle
    assert f"tier.{tier.value}.meaning" in bundle


def test_every_filing_route_value_in_the_snapshot_has_copy() -> None:
    """The route comes from the policy snapshot, so its vocabulary is data.

    A snapshot may introduce an authority or a result document we have never
    rendered. That is a policy change reaching the UI, and it should be caught
    here rather than shown to a creator as `nrta_provincial`.
    """
    import yaml

    bundle = _en()
    missing: list[str] = []
    checked = 0

    for path in sorted((Path(__file__).resolve().parent.parent / "policy").glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for routes in _find_filing_routes(document):
            for tier, route in routes.items():
                if not isinstance(route, dict):
                    continue
                checked += 1
                for field, prefix in (
                    ("authority", "filing.authority"),
                    ("result_document", "filing.document"),
                    ("pre_shoot_filing", "result.step.pre_shoot"),
                ):
                    value = route.get(field)
                    if value and f"{prefix}.{value}" not in bundle:
                        missing.append(f"{path.name}:{tier} -> {prefix}.{value}")

    # Without this the test passes by finding nothing, which is exactly the
    # state a renamed snapshot key would leave it in.
    assert checked, "no filing routes found in policy/*.yaml — has the shape moved?"
    assert not missing, f"filing-route values with no English copy: {sorted(set(missing))}"


def _find_filing_routes(node: object) -> list[dict]:
    """Every `filing_routes` block, wherever a snapshot chooses to nest it."""
    found: list[dict] = []
    if isinstance(node, dict):
        routes = node.get("filing_routes")
        if isinstance(routes, dict):
            found.append(routes)
        for value in node.values():
            found.extend(_find_filing_routes(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_find_filing_routes(value))
    return found


CARD = Path(__file__).resolve().parent.parent / "web" / "components" / "classification-card.tsx"
CLASSIFY = Path(__file__).resolve().parent.parent / "core" / "classify"

# Flags the card deliberately does not say out loud, and why. `script_verify`
# marks the script pre-check as the next stage, which the card already states in
# its own words; saying it twice, once in English and once as a key, is worse
# than saying it once.
SILENT_FLAGS = {"script_verify"}


def _speakable_flags() -> set[str]:
    """The flag list the card actually renders, read from the card itself."""
    import re

    source = CARD.read_text(encoding="utf-8")
    block = re.search(r"const SPEAKABLE_FLAGS = \[(.*?)\];", source, re.S)
    assert block, "SPEAKABLE_FLAGS not found — has the card been restructured?"
    return set(re.findall(r'"([a-z_]+)"', block.group(1)))


def _classification_flags() -> set[str]:
    """Every flag literal the classification chain can attach to a result."""
    import re

    found: set[str] = set()
    for path in CLASSIFY.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "pending_flags" in line or "flags.add" in line:
                found.update(re.findall(r'"([a-z_]{4,})"', line))
    return found - {"pending_flags"}


@pytest.mark.parametrize("flag", sorted(_speakable_flags()))
def test_every_rendered_flag_has_copy(flag: str) -> None:
    assert f"flag.{flag}" in _en(), f"the card renders {flag} but has nothing to say about it"


def test_no_classification_flag_is_unaccounted_for() -> None:
    """A new flag is either said in words or explicitly listed as silent.

    Without this, adding a flag in `core/classify` ships it to a creator as a
    raw identifier — which is the bug this whole module exists to prevent.
    """
    unaccounted = _classification_flags() - _speakable_flags() - SILENT_FLAGS
    assert not unaccounted, (
        "these classification flags are neither rendered with copy nor listed "
        f"as deliberately silent: {sorted(unaccounted)}"
    )


def test_every_clause_the_card_can_cite_has_an_english_name() -> None:
    """`evidence_refs` carry a clause id; the card renders its name.

    The ids are stable and the snapshot's own `title` is Chinese, so the English
    reading lives in the bundle. A clause added to a snapshot with no entry here
    would render as an empty bullet under "Decided under" -- worse than the raw
    id it replaced, because it says nothing at all.
    """
    import re
    import yaml

    bundle = _en()
    missing: list[str] = []
    seen = 0

    for path in sorted((Path(__file__).resolve().parent.parent / "policy").glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for clause_id in set(re.findall(r"clause_(?:id|ref):\s*([A-Za-z0-9_-]+)", text)):
            seen += 1
            if f"clause.{clause_id}" not in bundle:
                missing.append(f"{path.name}: clause.{clause_id}")

    assert seen, "no clause ids found in policy/*.yaml -- has the shape moved?"
    assert not missing, f"clauses with no English name: {sorted(set(missing))}"


def test_the_english_bundle_has_no_chinese() -> None:
    """The UI is English-only in this build.

    Removing the glosses was a deliberate call (D-039) that gives something up:
    a creator who reads "Class 3" here will meet the Chinese term on the actual
    filing form. Keeping that removal consistent is the least we can do, and a
    stray Chinese string in one label is exactly the kind of thing that creeps
    back in one copy edit at a time.
    """
    import json
    import re

    bundle = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    cjk = re.compile(r"[\u4e00-\u9fff]")
    offenders = sorted(k for k, v in bundle.items() if isinstance(v, str) and cjk.search(v))
    assert not offenders, f"English bundle carries Chinese text: {offenders}"
