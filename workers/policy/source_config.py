"""Strict policy source configuration loading."""

from pathlib import Path
from typing import Any

import yaml

from .models import PolicySource


def load_policy_sources(path: Path) -> dict[str, PolicySource]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"sources"}:
        raise ValueError("policy source config must contain only sources")
    rows = raw["sources"]
    if not isinstance(rows, list):
        raise TypeError("policy source config sources must be a list")

    sources: dict[str, PolicySource] = {}
    for row in rows:
        source = PolicySource.model_validate(row)
        if source.source_id in sources:
            raise ValueError(f"duplicate policy source id: {source.source_id}")
        sources[source.source_id] = source
    return sources
