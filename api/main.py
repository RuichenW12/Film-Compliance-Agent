"""FastAPI application: product workflow routes and policy administration.

Both workstreams mount here. The product side (workstream A) carries its
dependencies in `AppContext`; the policy side (workstream B) builds its
deterministic demo state during lifespan startup.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps.policy import PolicyApiState, build_local_policy_api_state
from api.errors import install_policy_error_handler
from api.routes.admin_policy import router as admin_policy_router
from core.errors import AppError
from schemas.enums import ErrorCode
from schemas.snapshot import SnapshotNotFoundError
from workers.policy.adapters.repository_snapshot import RepositorySnapshotService

from .deps.services import AppContext, build_context
from .routers import health, internal, projects
from .settings import Settings

WEB_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(
    *,
    context: AppContext | None = None,
    policy_state: PolicyApiState | None = None,
) -> FastAPI:
    def install_policy_state(app: FastAPI, resolved: PolicyApiState) -> None:
        app.state.policy = resolved
        if context is None:
            app.state.context = build_context(
                Settings.from_env(),
                snapshots=RepositorySnapshotService(resolved.repository),
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if policy_state is not None:
            install_policy_state(app, policy_state)
            yield
            return
        with TemporaryDirectory(prefix="film-compliance-policy-") as temp_dir:
            resolved = await build_local_policy_api_state(
                Path(temp_dir) / "blobs"
            )
            install_policy_state(app, resolved)
            yield

    app = FastAPI(
        title="Film Compliance Agent",
        version="1.0.0",
        description=(
            "Pre-shoot compliance workflow and policy loop. Conclusions carry "
            "evidence; unknown fields stay unknown."
        ),
        lifespan=lifespan,
    )
    if context is not None:
        app.state.context = context

    app.add_middleware(
        CORSMiddleware,
        allow_origins=WEB_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Mock-Role", "X-User-Id", "X-Internal-Token"],
    )

    install_policy_error_handler(app)
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(internal.router)
    app.include_router(admin_policy_router)

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.envelope())

    @app.exception_handler(SnapshotNotFoundError)
    async def handle_snapshot_not_found(
        _: Request, exc: SnapshotNotFoundError
    ) -> JSONResponse:
        """A version the product cannot read is a 404, not a crash."""

        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": ErrorCode.NOT_FOUND.value,
                    "message": str(exc),
                    "details": {"hint": "the product reads snapshots through SnapshotService"},
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.VALIDATION_ERROR.value,
                    "message": "request validation failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    return app


app = create_app()
