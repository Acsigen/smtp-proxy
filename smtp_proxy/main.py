"""Main entry point for SMTP Proxy."""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

import uvicorn

from .config import Config
from .database import Database, EmailRepository, UserRepository
from .smtp import SMTPServer
from .web import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="SMTP Proxy - A development SMTP blackhole server with web UI"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )
    return parser.parse_args()


def ensure_admin_user(user_repo: UserRepository, username: str, password: str) -> None:
    """Ensure the admin user exists in the database."""
    if not user_repo.exists(username):
        user_repo.create(username, password)
        logger.info(f"Created admin user: {username}")
    else:
        logger.info(f"Admin user already exists: {username}")


async def run_smtp_server(smtp_server: SMTPServer) -> None:
    """Run the SMTP server."""
    try:
        await smtp_server.start()
    except asyncio.CancelledError:
        logger.info("SMTP server task cancelled")
    except Exception as e:
        logger.error(f"SMTP server error: {e}")


class WebServer:
    """Wrapper for Uvicorn server with graceful shutdown support."""

    def __init__(self, app, host: str, port: int):
        self.config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
        )
        self.server = uvicorn.Server(self.config)

    async def start(self) -> None:
        """Start the web server."""
        await self.server.serve()

    async def shutdown(self) -> None:
        """Signal the server to shutdown gracefully."""
        self.server.should_exit = True


async def main_async(config: Config) -> None:
    """Async main function to run both servers."""
    # Initialize database
    db = Database(config.database.path)
    logger.info(f"Database initialized at: {config.database.path}")

    # Create repositories
    email_repo = EmailRepository(db)
    user_repo = UserRepository(db)

    # Ensure admin user exists
    ensure_admin_user(user_repo, config.admin.username, config.admin.password)

    # Create SMTP server
    smtp_server = SMTPServer(config.smtp, email_repo)

    # Create FastAPI app and web server
    app = create_app(config, email_repo, user_repo)
    web_server = WebServer(app, config.web.host, config.web.port)

    # Setup shutdown event
    shutdown_event = asyncio.Event()

    def signal_handler():
        if not shutdown_event.is_set():
            logger.info("Received shutdown signal, initiating graceful shutdown...")
            shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler())

    # Start servers
    logger.info(f"Starting SMTP server on {config.smtp.address}")
    logger.info(f"Starting Web server on {config.web.address}")

    smtp_task = asyncio.create_task(run_smtp_server(smtp_server))
    web_task = asyncio.create_task(web_server.start())

    # Wait for shutdown signal or server failure
    done, pending = await asyncio.wait(
        [smtp_task, web_task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Graceful shutdown
    logger.info("Shutting down servers...")

    # Signal both servers to shutdown gracefully
    await smtp_server.shutdown()
    await web_server.shutdown()

    # Wait for tasks to complete with timeout
    for task in pending:
        if not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Task did not complete in time, cancelling...")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    # Close database
    db.close()
    logger.info("Shutdown complete")


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    try:
        config = Config.load(str(config_path))
        logger.info(f"Configuration loaded from: {config_path}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Run the async main - signal handlers are set up inside main_async
    asyncio.run(main_async(config))


if __name__ == "__main__":
    main()
