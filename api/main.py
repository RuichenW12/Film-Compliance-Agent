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
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dataclasses import replace

from api.deps.policy import PolicyApiState, build_local_policy_api_state
from workers.policy.adapters.live_projects import (
    InlineOutboxDelivery,
    LiveProjectRepository,
    LiveRecalcClient,
)
from workers.policy.consumer import PolicyUpdatedConsumer
from workers.policy.outbox import OutboxDispatcher
from api.errors import install_policy_error_handler
from api.routers.admin_policy import router as admin_policy_router
from core.errors import AppError
from schemas.enums import ErrorCode
from schemas.snapshot import SnapshotNotFoundError
from workers.policy.adapters.repository_snapshot import RepositorySnapshotService

from .deps.services import AppContext, build_context
from .routers import (
    assets,
    forms,
    health,
    institution,
    intake_help,
    internal,
    materials,
    notifications,
    projects,
    review,
    reviews,
    teaser,
)
from .settings import Settings

WEB_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


def create_app(
    *,
    context: AppContext | None = None,
    policy_state: PolicyApiState | None = None,
) -> FastAPI:
    settings = Settings.from_env()

    def install_policy_state(
        app: FastAPI, resolved: PolicyApiState, *, wire_fan_out: bool
    ) -> None:
        app.state.policy = resolved
        if context is None:
            app.state.context = build_context(
                settings,
                snapshots=RepositorySnapshotService(resolved.repository),
            )

        # Point the policy loop at the product's real projects.
        #
        # The consumer was always written -- idempotency receipts, impact
        # filtering, recalc -- and was wired to a fake repository holding no
        # projects. So a publish produced a new snapshot and told nobody: a
        # project pinned to the old version stayed pinned, unflagged, and its
        # creator never heard. This is the wire that was missing. See D-049.
        # Only on the default path. A caller who hands in a `policy_state`
        # has configured its dispatcher deliberately -- a test pointing it at a
        # failing publisher, say -- and replacing that would quietly defeat the
        # thing they set up.
        product = getattr(app.state, "context", None)
        if wire_fan_out and product is not None:
            repository = LiveProjectRepository(
                product.stores.projects, product.workflow
            )
            delivery = InlineOutboxDelivery(
                resolved.repository,
                PolicyUpdatedConsumer(repository, LiveRecalcClient(product.workflow)),
                resolved.clock,
            )
            app.state.policy = replace(resolved, delivery=delivery)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if policy_state is not None:
            install_policy_state(app, policy_state, wire_fan_out=False)
            yield
            return
        with TemporaryDirectory(prefix="film-compliance-policy-") as temp_dir:
            resolved = await build_local_policy_api_state(
                Path(temp_dir) / "blobs",
                seed_path=settings.snapshot_path,
            )
            install_policy_state(app, resolved, wire_fan_out=True)
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
        # PUT is the upload route: the browser preflights it, so omitting it
        # here fails the upload in the UI while every test still passes.
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=["Content-Type", "X-Mock-Role", "X-User-Id", "X-Internal-Token"],
    )

    install_policy_error_handler(app)
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(intake_help.router)
    app.include_router(assets.router)
    app.include_router(materials.router)
    app.include_router(review.router)
    app.include_router(reviews.router)
    app.include_router(forms.router)
    app.include_router(institution.router)
    app.include_router(teaser.router)
    app.include_router(notifications.router)
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
                    "details": {
                        "errors": jsonable_encoder(
                            exc.errors(),
                            custom_encoder={Exception: str},
                        )
                    },
                }
            },
        )

    return app


app = create_app()
