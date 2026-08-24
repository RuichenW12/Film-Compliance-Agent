from pathlib import Path

import pytest

from workers.policy.normalize import (
    PolicyExtractError,
    create_policy_diff,
    normalize_html,
    sha256_text,
)


FIXTURES = Path(__file__).parents[1] / "fixtures" / "policy"


def test_html_noise_does_not_change_normalized_hash() -> None:
    source = (FIXTURES / "source-v1.html").read_bytes()
    noisy = source.replace(b"noise-v1", b"changed-script-noise").replace(
        "站点导航 v1".encode(), "变化后的站点导航".encode()
    )

    normalized = normalize_html(source, "#zoom")
    noisy_normalized = normalize_html(noisy, "#zoom")

    assert normalized == noisy_normalized
    assert sha256_text(normalized) == sha256_text(noisy_normalized)


def test_text_change_produces_unified_diff() -> None:
    previous = normalize_html((FIXTURES / "source-v1.html").read_bytes(), "#zoom")
    current = normalize_html((FIXTURES / "source-v2.html").read_bytes(), "#zoom")

    diff = create_policy_diff("nrta_micro_drama", previous, current)

    assert diff.previous_sha256 != diff.current_sha256
    assert "-分类标准尚未公布。" in diff.unified_diff
    assert "+分类标准正式公布。" in diff.unified_diff


def test_missing_selector_is_an_extract_error() -> None:
    with pytest.raises(PolicyExtractError) as exc_info:
        normalize_html(b"<html><body>content</body></html>", "#zoom")

    assert exc_info.value.code == "POLICY_EXTRACT_FAILED"
