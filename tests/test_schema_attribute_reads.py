"""No code reads a schema field that does not exist.

`_write_alert_finding` read `intent_profile.logline` for weeks after `logline`
was removed. It never crashed in a test because Python's `or` short-circuits
and every test happened to supply the left operand -- so the read waited on a
rare path, where it would have raised `AttributeError` in front of a creator.

Pydantic models here are `extra="forbid"`, so a stale attribute read is always a
bug and never a dynamic lookup. That makes it findable without running anything:
walk the source for `<name>.<attr>` where `<name>` is a variable we know holds a
model, and check the attribute against that model's fields.

Deliberately narrow. It covers the models whose fields have actually churned and
the variable names the code consistently uses for them, rather than attempting
whole-program type inference. A rename that also renames the variable slips
past; a field deletion, which is what happened, does not.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from schemas.project import ChannelProfile, Classification, IntentProfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Variable name -> the model it holds.
#
# Only names that mean one model everywhere. `draft` was in this list and had
# to come out: `workers/policy/refresh.py` uses it for a `ProposalDraft`, and
# the check duly reported four of its fields as missing from `FormDraft`. That
# is the honest limit of name-based inference -- a name shared by two models
# produces confident nonsense, so the answer is to claim less, not to add
# exceptions until the noise stops.
BOUND_NAMES = {
    "intent": IntentProfile,
    "intent_profile": IntentProfile,
    "channel_profile": ChannelProfile,
    "classification": Classification,
}

# Attribute chains rooted at a model-valued attribute rather than a bare name.
ATTRIBUTE_ROOTS = {
    "intent_profile": IntentProfile,
    "channel_profile": ChannelProfile,
    "classification": Classification,
}

# Real attributes that are not fields: pydantic's own API, and helpers defined
# on the models themselves.
ALLOWED = {
    "model_dump", "model_dump_json", "model_copy", "model_validate",
    "model_validate_json", "model_fields", "model_config", "copy", "dict",
    "json", "source_ref",
}

SEARCH_DIRS = ("core", "api", "workers", "store")


def _sources() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for directory in SEARCH_DIRS:
        files.extend(sorted((ROOT / directory).rglob("*.py")))
    return [f for f in files if "__pycache__" not in f.parts]


def _stale_reads(path: pathlib.Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    problems: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        attribute = node.attr
        if attribute in ALLOWED or attribute.startswith("_"):
            continue

        model = None
        if isinstance(node.value, ast.Name):
            model = BOUND_NAMES.get(node.value.id)
        elif isinstance(node.value, ast.Attribute):
            model = ATTRIBUTE_ROOTS.get(node.value.attr)

        if model is None:
            continue
        if attribute in model.model_fields:
            continue
        # A method on the model is fine; only unknown names are the bug.
        if hasattr(model, attribute):
            continue
        try:
            where = path.relative_to(ROOT)
        except ValueError:
            where = path  # a tmp file, from the self-check below
        problems.append(
            f"{where}:{node.lineno} reads "
            f"{model.__name__}.{attribute}, which is not a field"
        )
    return problems


@pytest.mark.parametrize("path", _sources(), ids=lambda p: str(p.name))
def test_no_source_file_reads_a_removed_field(path: pathlib.Path) -> None:
    problems = _stale_reads(path)
    assert not problems, "\n".join(problems)


def test_the_check_would_have_caught_the_logline_read(tmp_path) -> None:
    """Otherwise this file passes by looking at nothing."""

    sample = tmp_path / "sample.py"
    sample.write_text(
        "def f(project):\n"
        "    return project.intent_profile.logline or ''\n",
        encoding="utf-8",
    )
    problems = _stale_reads(sample)
    assert problems and "logline" in problems[0]
