"""FastAPI application factory for injected Gate 3 state."""

from fastapi import FastAPI

from api.deps.policy import PolicyApiState
from api.errors import install_policy_error_handler
from api.routes.admin_policy import router as admin_policy_router


def create_app(initial_state: PolicyApiState) -> FastAPI:
    app = FastAPI(title="Film Compliance Agent")
    app.state.policy = initial_state
    install_policy_error_handler(app)
    app.include_router(admin_policy_router)
    return app
