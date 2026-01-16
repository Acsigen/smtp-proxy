"""FastAPI application factory."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Config
from ..database.email_repository import EmailRepository
from ..database.user_repository import UserRepository
from .auth import SessionManager
from .routes import router


def create_app(
    config: Config,
    email_repo: EmailRepository,
    user_repo: UserRepository,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SMTP Proxy",
        description="A development SMTP blackhole server with web UI",
        version="1.0.0",
    )

    # Setup templates
    templates_dir = Path(__file__).parent.parent.parent / "templates"
    templates = Jinja2Templates(directory=str(templates_dir))

    # Setup session manager
    session_manager = SessionManager(
        secret=config.web.session_secret,
        cookie_name=config.web.session_name,
        max_age=86400,  # 24 hours
    )

    # Store dependencies in app state
    app.state.config = config
    app.state.email_repo = email_repo
    app.state.user_repo = user_repo
    app.state.templates = templates
    app.state.session_manager = session_manager

    # Include routes
    app.include_router(router)

    return app
