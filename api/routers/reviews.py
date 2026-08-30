"""Creator-facing upload-first review routes."""

from __future__ import annotations

from pathlib import PurePosixPath
import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from core.errors import ScriptTooLargeError, ValidationFailedError
from core.review_facade import ReviewFacade
from core.script_text import MAX_SCRIPT_BYTES
from schemas.enums import Role
from schemas.reviews import (
    ConfirmedReviewDetails,
    IdeaOnly,
    ReviewArtifactType,
    ReviewMode,
    ReviewView,
    StartReviewCommand,
    UploadedScript,
)

from ..deps.demo_auth import Principal, get_principal
from ..deps.services import get_review_facade


router = APIRouter(prefix="/v1/reviews", tags=["reviews"])


def _safe_filename(value: str, fallback: str = "download") -> str:
    normalized_path = value.replace("\\", "/").replace("\r", "").replace("\n", "")
    name = PurePosixPath(normalized_path).name.strip(" .")
    return name or fallback


def _content_disposition(filename: str) -> str:
    safe_name = _safe_filename(filename)
    ascii_name = (
        unicodedata.normalize("NFKD", safe_name)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name).strip(".-")
    ascii_name = ascii_name or "download"
    encoded = quote(safe_name, safe="")
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{encoded}"
    )


@router.post("", response_model=ReviewView, status_code=status.HTTP_201_CREATED)
async def create_review(
    mode: str = Form(default=ReviewMode.SCRIPT.value),
    script: UploadFile | None = File(default=None),
    principal: Principal = Depends(get_principal),
    facade: ReviewFacade = Depends(get_review_facade),
) -> ReviewView:
    principal.require(Role.CREATOR)
    try:
        selected_mode = ReviewMode(mode.strip().lower())
    except ValueError as exc:
        raise ValidationFailedError(
            "mode must be script or idea", {"field": "mode"}
        ) from exc

    if selected_mode is ReviewMode.IDEA:
        if script is not None:
            raise ValidationFailedError(
                "idea mode does not accept a script attachment",
                {"field": "script"},
            )
        source = IdeaOnly()
    else:
        if script is None:
            raise ValidationFailedError(
                "script mode requires an uploaded script",
                {"field": "script"},
            )
        filename = _safe_filename(script.filename or "script.md", "script.md")
        content = await script.read(MAX_SCRIPT_BYTES + 1)
        if len(content) > MAX_SCRIPT_BYTES:
            raise ScriptTooLargeError(
                "script exceeds the 5 MiB upload limit",
                {"max_bytes": MAX_SCRIPT_BYTES},
            )
        source = UploadedScript(
            filename=filename,
            media_type=script.content_type,
            content=content,
        )
    return facade.start(
        StartReviewCommand(owner_uid=principal.user_id, source=source)
    )


@router.get("/{review_id}", response_model=ReviewView)
def get_review(
    review_id: str,
    principal: Principal = Depends(get_principal),
    facade: ReviewFacade = Depends(get_review_facade),
) -> ReviewView:
    principal.require(Role.CREATOR)
    return facade.get(review_id, principal.user_id)


@router.post("/{review_id}/confirm", response_model=ReviewView)
def confirm_review(
    review_id: str,
    body: ConfirmedReviewDetails,
    principal: Principal = Depends(get_principal),
    facade: ReviewFacade = Depends(get_review_facade),
) -> ReviewView:
    principal.require(Role.CREATOR)
    return facade.confirm(review_id, principal.user_id, body)


@router.post("/{review_id}/retry-intake", response_model=ReviewView)
def retry_intake(
    review_id: str,
    principal: Principal = Depends(get_principal),
    facade: ReviewFacade = Depends(get_review_facade),
) -> ReviewView:
    principal.require(Role.CREATOR)
    return facade.retry_intake(review_id, principal.user_id)


@router.get("/{review_id}/source")
def download_source(
    review_id: str,
    principal: Principal = Depends(get_principal),
    facade: ReviewFacade = Depends(get_review_facade),
) -> Response:
    principal.require(Role.CREATOR)
    artifact = facade.source(review_id, principal.user_id)
    view = facade.get(review_id, principal.user_id)
    headers = {
        "Content-Disposition": _content_disposition(artifact.filename),
    }
    if view.source_sha256:
        headers["X-Source-Sha256"] = view.source_sha256
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers=headers,
    )


@router.get("/{review_id}/artifacts/{artifact_type}")
def download_artifact(
    review_id: str,
    artifact_type: ReviewArtifactType,
    principal: Principal = Depends(get_principal),
    facade: ReviewFacade = Depends(get_review_facade),
) -> Response:
    principal.require(Role.CREATOR)
    artifact = facade.artifact(review_id, principal.user_id, artifact_type)
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": _content_disposition(artifact.filename),
        },
    )
