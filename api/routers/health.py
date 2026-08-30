"""Liveness and configuration visibility."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..deps.services import get_context

router = APIRouter(tags=["ops"])


# Two paths, one handler.
#
# `/healthz` is what the contract, the manual and `scripts/e2e_check.py` have
# always used, and it works locally. It does *not* work on Cloud Run: Google's
# front end answers it with a 404 before the request reaches the container.
# Verified rather than assumed -- `/zzz-not-a-route` reaches the app and uvicorn
# logs its 404, while `/healthz` appears in no log line at all, signed in or
# not.
#
# So `/health` is the path to use against a deployed service. `/healthz` stays
# because nothing is gained by breaking every local instruction, and because a
# health check that silently stops being reachable is precisely the failure this
# endpoint exists to catch.
@router.get("/health")
@router.get("/healthz")
def healthz(request: Request) -> dict:
    context = get_context(request)
    version = context.snapshots.latest_version()
    return {
        "status": "ok",
        "snapshot_version": version,
        "snapshot_verification_status": context.snapshots.verification_status(version),
        "llm_backend": context.llm.name,
        "llm_available": context.llm.available(),
        "store_backend": context.settings.store_backend,
        "flags": {
            "veo_teaser": context.settings.flag_veo_teaser,
            "us_track": context.settings.flag_us_track,
        },
    }
