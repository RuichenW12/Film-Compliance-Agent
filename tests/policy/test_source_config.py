from pathlib import Path

import pytest

from workers.policy.source_config import load_policy_sources


ROOT = Path(__file__).parents[2]


def test_real_policy_source_is_strictly_loaded() -> None:
    sources = load_policy_sources(ROOT / "policy" / "policy_sources.yaml")

    source = sources["nrta_micro_drama_management_measures"]
    assert source.url == "https://www.nrta.gov.cn/art/2026/7/31/art_113_73785.html"
    assert source.content_selector == "#zoom"
    assert source.enabled is True


@pytest.mark.parametrize(
    "content",
    [
        "sources: []\nextra: true\n",
        "sources:\n  - source_id: duplicated\n    url: https://example.com/1\n    content_selector: '#a'\n    enabled: true\n  - source_id: duplicated\n    url: https://example.com/2\n    content_selector: '#b'\n    enabled: true\n",
        "sources:\n  - source_id: invalid_http\n    url: http://example.com\n    content_selector: '#a'\n    enabled: true\n",
        "sources:\n  - source_id: empty_selector\n    url: https://example.com\n    content_selector: ''\n    enabled: true\n",
        "sources:\n  - source_id: unknown_key\n    url: https://example.com\n    content_selector: '#a'\n    enabled: true\n    unexpected: true\n",
    ],
)
def test_invalid_source_config_is_rejected(tmp_path: Path, content: str) -> None:
    path = tmp_path / "sources.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises((TypeError, ValueError)):
        load_policy_sources(path)
