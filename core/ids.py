"""Server-side identifiers: `<prefix>_<ulid>` per API contract section 1."""

from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

PREFIXES = {
    "project": "proj",
    "task": "task",
    "finding": "fnd",
    "material": "mat",
    "draft": "draft",
    "proposal": "prop",
    "asset": "av",
    "fact": "fact",
    "notification": "ntf",
    "event": "evt",
    "review": "rev",
}


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def ulid(now_ms: int | None = None) -> str:
    """26-char Crockford base32 ULID: 48-bit timestamp + 80 bits of randomness."""

    timestamp = now_ms if now_ms is not None else int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(timestamp, 10) + _encode(randomness, 16)


def new_id(kind: str, now_ms: int | None = None) -> str:
    try:
        prefix = PREFIXES[kind]
    except KeyError as exc:
        raise ValueError(f"unknown id kind: {kind}") from exc
    return f"{prefix}_{ulid(now_ms).lower()}"
