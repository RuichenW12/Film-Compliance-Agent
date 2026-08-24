"""FastAPI application: error envelope, demo auth, and the v1 routes."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.errors import AppError
from schemas.enums import ErrorCode

from .deps.services import AppContext, build_context
from .routers import health, internal, projects
from .settings import Settings


def create_app(context: AppContext | None = None) -> FastAPI:
    app = FastAPI(
        title="Film Compliance Agent API",
        version="1.0.0",
        description=(
            "Pre-shoot compliance workflow. Conclusions carry evidence; unknown "
            "fields stay unknown."
        ),
    )
    app.state.context = context or build_context(Settings.from_env())

    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(internal.router)

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.envelope())

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
