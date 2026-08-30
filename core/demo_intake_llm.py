"""Bounded local inference for the four checked-in browser-demo scripts.

This adapter is deliberately content addressed. It is not a general offline
model and must fail closed when a request is not one of the reviewed demo
inputs below. Production composition roots do not import it.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any

from .errors import UpstreamLLMError
from .llm import LLMRequest
from .review import SCRIPT_REVIEW_PROMPT_ID
from .script_intake import SCRIPT_INTAKE_PROMPT_ID


class DemoIntakeLLM:
    """Fixture-bounded ``LLMClient`` for local, credential-free demos."""

    name = "local-content-aware-demo"

    def available(self) -> bool:
        return True

    def structured(self, request: LLMRequest) -> dict[str, Any]:
        if request.prompt_id == SCRIPT_INTAKE_PROMPT_ID:
            replies = _INTAKE_REPLIES
        elif request.prompt_id == SCRIPT_REVIEW_PROMPT_ID:
            replies = _REVIEW_REPLIES
        else:
            raise UpstreamLLMError(
                f"unsupported demo prompt: {request.prompt_id}",
                {"prompt_id": request.prompt_id},
            )

        checksum = _document_checksum(request.document)
        try:
            return deepcopy(replies[checksum])
        except KeyError as exc:
            raise UpstreamLLMError(
                "unknown demo document",
                {
                    "prompt_id": request.prompt_id,
                    "document_sha256": checksum,
                },
            ) from exc


def _document_checksum(document: str) -> str:
    if not isinstance(document, str):
        raise UpstreamLLMError("demo document must be text")
    return sha256(document.encode("utf-8")).hexdigest()


def _suggested(value: Any, explanation: str) -> dict[str, Any]:
    return {
        "value": value,
        "origin": "suggested",
        "explanation": explanation,
    }


def _intake_reply(
    *,
    tags: list[str],
    synopsis: str,
    episode_count: int,
    episode_minutes: float,
    language: str,
) -> dict[str, Any]:
    if language == "zh":
        return {
            "tags": _suggested(tags, "根据当前上传剧本的主题与人物关系生成，可编辑。"),
            "synopsis": _suggested(
                synopsis, "仅压缩当前上传剧本的故事信息，不作合规或法律结论。"
            ),
            "episode_count": _suggested(
                episode_count, "拆分建议保持原剧本总时长不变，可编辑。"
            ),
            "episode_minutes": _suggested(
                episode_minutes, "单集时长与建议集数共同保持原总时长。"
            ),
            "amount_bracket": _suggested(
                "at_or_above_upper", "依据当前快照档位给出的可编辑制作金额估算。"
            ),
        }
    return {
        "tags": _suggested(
            tags, "Editable tags derived from the current uploaded screenplay."
        ),
        "synopsis": _suggested(
            synopsis,
            "A concise summary of this upload without a compliance or legal conclusion.",
        ),
        "episode_count": _suggested(
            episode_count,
            "The proposed split preserves the source screenplay's total duration.",
        ),
        "episode_minutes": _suggested(
            episode_minutes,
            "Episode length and count preserve the source duration together.",
        ),
        "amount_bracket": _suggested(
            "at_or_above_upper",
            "An editable production estimate from the current snapshot bands.",
        ),
    }


# SHA-256 values cover the exact normalized text sent in the current LLMRequest.
# They intentionally change when a fixture changes, forcing this bounded demo
# behavior to be reviewed alongside fixture edits.
_INTAKE_REPLIES: dict[str, dict[str, Any]] = {
    # e2e-30min-public-security.md
    "e172493cb8691a6ee4a7e6c8e10e737bfc2672e7a2f532deb81f84e5e1b44005": _intake_reply(
        tags=["公安题材", "反诈", "家庭现实"],
        synopsis="社区民警帮助一对父女把险些受骗的经历转化为真实的社区提醒，也让他们重新建立彼此确认的联系。",
        episode_count=10,
        episode_minutes=3,
        language="zh",
    ),
    # e2e-30min-public-security-en.md
    "d794b9fe81f0053af287430dd38826e40f6c3b8399615ae735cbbd736241770f": _intake_reply(
        tags=["public security", "anti-fraud", "family drama"],
        synopsis="A community police officer helps a father and daughter turn an almost-successful scam call into an honest public warning and a new way to stay in contact.",
        episode_count=10,
        episode_minutes=3,
        language="en",
    ),
    # e2e-70min-judicial-long-context.md
    "ba8bbb3e0b1b1bcf55b6971bc80f208ff4436fdf24082ad32451fe2432638d7b": _intake_reply(
        tags=["司法题材", "著作权争议", "都市现实"],
        synopsis="编剧林夏为恩师遗作的署名与剧场经理发生争议，双方在调解和庭审过程中依靠版本证据重新厘清共同创作的贡献边界。",
        episode_count=7,
        episode_minutes=10,
        language="zh",
    ),
    # e2e-70min-judicial-long-context-en.md
    "964827621408d88452688bb04f8a6d1f5fa415aead3bc4e23c4d54c3e36a7a12": _intake_reply(
        tags=["judicial", "authorship dispute", "theater drama"],
        synopsis="A playwright challenges the missing credit on her late mentor's work, and a mediation and hearing force every contributor to confront the evidence of shared authorship.",
        episode_count=7,
        episode_minutes=10,
        language="en",
    ),
}


# Semantic review receives only reviewable scene lines, so these checksums are
# intentionally distinct from the corresponding full-document intake hashes.
_REVIEW_REPLIES: dict[str, dict[str, Any]] = {
    # reviewable e2e-30min-public-security-en.md
    "4350e22541f3d898eb0787a29d5e65ee75c5154043891512348feeacf64c7d2a": {
        "hits": [
            {
                "category": "public_security",
                "quote": "The police station is right at the end of the street. You don't have to argue with them, and you don't have to make a decision right now. Just change locations, sit down, and confirm.",
                "reason": "The scene centers on seeking help at a police station during a suspected scam call; a human must review the governed subject boundary.",
            }
        ]
    },
    # reviewable e2e-70min-judicial-long-context-en.md
    "cdb6d6341e7659acb3c9f4c0c58cfdc0ae6145db3dc9c1f3d8b3fa767e0c7923": {
        "hits": [
            {
                "category": "judicial",
                "quote": "Let's separate the performance authorization from the promotional credits first. Do both sides acknowledge the authenticity of the main text of the authorization?",
                "reason": "A judge is conducting court mediation about authorization and credit; the governed judicial category remains for human review.",
            }
        ]
    },
}
