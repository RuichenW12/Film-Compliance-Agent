"""FastAPI application factory for the local Gate 3 demo."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps.policy import PolicyApiState, build_local_policy_api_state
from api.errors import install_policy_error_handler
from api.routes.admin_policy import router as admin_policy_router


def create_app(initial_state: PolicyApiState | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if initial_state is not None:
            app.state.policy = initial_state
            yield
            return
        with TemporaryDirectory(prefix="film-compliance-policy-") as temp_dir:
            app.state.policy = await build_local_policy_api_state(
                Path(temp_dir) / "blobs"
            )
            yield

    app = FastAPI(title="Film Compliance Agent", lifespan=lifespan)
    install_policy_error_handler(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Mock-Role"],
    )
    app.include_router(admin_policy_router)
    return app


app = create_app()
