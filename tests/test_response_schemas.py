"""No response schema may use a JSON-Schema union type.

Vertex's `responseSchema` is an OpenAPI 3.0 subset: `"type"` takes a single
string, never a list. A union is accepted by every fake LLM we test with and
rejected by the real backend, so it produces a suite that is fully green while
no live call can succeed. That has now happened twice -- once in
`core/intake_help.py`, once in `core/extract.py` -- which is twice more than a
mistake this cheap to detect should occur.

The check walks the schema dicts themselves rather than the source text, so a
schema assembled at import time is covered however it was written.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

import pytest

# Modules that declare a schema handed to the LLM port. Discovered rather than
# listed, so a new one is covered the day it is written.
CANDIDATE_PACKAGES = ["core"]


def _schema_dicts() -> list[tuple[str, str, dict]]:
    """Every module-level dict named *RESPONSE_SCHEMA or *_SCHEMA."""

    found: list[tuple[str, str, dict]] = []
    for package_name in CANDIDATE_PACKAGES:
        package = importlib.import_module(package_name)
        for info in pkgutil.walk_packages(package.__path__, f"{package_name}."):
            try:
                module = importlib.import_module(info.name)
            except Exception:  # pragma: no cover - an import error is another test's problem
                continue
            for attribute in dir(module):
                if not attribute.endswith("SCHEMA"):
                    continue
                value = getattr(module, attribute)
                if isinstance(value, dict):
                    found.append((info.name, attribute, value))
    return found


def _union_types(node: Any, path: str = "") -> list[str]:
    """Every place a `type` is a list rather than a single string."""

    offenders: list[str] = []
    if isinstance(node, dict):
        if isinstance(node.get("type"), list):
            offenders.append(path or "<root>")
        for key, value in node.items():
            offenders.extend(_union_types(value, f"{path}.{key}" if path else key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            offenders.extend(_union_types(value, f"{path}[{index}]"))
    return offenders


def test_at_least_one_response_schema_is_discovered() -> None:
    """Otherwise the test below passes by finding nothing to check."""

    assert _schema_dicts(), "no *SCHEMA dicts found under core/ -- has the naming moved?"


@pytest.mark.parametrize(
    "module_name,attribute,schema",
    _schema_dicts(),
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_response_schema_has_no_union_types(
    module_name: str, attribute: str, schema: dict
) -> None:
    offenders = _union_types(schema)
    assert not offenders, (
        f"{module_name}.{attribute} uses a union type at {offenders}. "
        "Vertex rejects it, and no fake-LLM test will tell you."
    )
