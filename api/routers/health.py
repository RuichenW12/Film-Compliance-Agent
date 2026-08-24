"""Liveness and configuration visibility."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..deps.services import get_context

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz(request: Request) -> dict:
    context = get_context(request)
    return {
        "status": "ok",
        "snapshot_version": context.snapshots.latest_version(),
        "llm_backend": context.llm.name,
        "llm_available": context.llm.available(),
        "store_backend": context.settings.store_backend,
        "flags": {
            "veo_teaser": context.settings.flag_veo_teaser,
            "us_track": context.settings.flag_us_track,
        },
    }
