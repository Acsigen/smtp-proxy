"""Async SMTP server implementation."""

import asyncio
import logging

from ..config import SMTPConfig
from ..database.email_repository import EmailRepository
from .session import SMTPSession

logger = logging.getLogger(__name__)


class SMTPServer:
    """Async SMTP server using asyncio."""

    def __init__(self, config: SMTPConfig, email_repo: EmailRepository):
        self.config = config
        self.email_repo = email_repo
        self._server: asyncio.Server | None = None
        self._shutdown_event = asyncio.Event()
        self._active_connections: set[asyncio.StreamWriter] = set()

    async def start(self) -> None:
        """Start the SMTP server."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.config.host,
            self.config.port,
        )

        addr = self._server.sockets[0].getsockname()
        logger.info(f"SMTP server listening on {addr[0]}:{addr[1]}")

        async with self._server:
            await self._shutdown_event.wait()

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a new client connection."""
        peername = writer.get_extra_info("peername")
        logger.debug(f"New SMTP connection from {peername}")

        self._active_connections.add(writer)
        session = SMTPSession(self.config, self.email_repo, reader, writer)
        try:
            await session.handle()
        except Exception as e:
            logger.error(f"Error handling SMTP session: {e}")
        finally:
            self._active_connections.discard(writer)
            if not writer.is_closing():
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
            logger.debug(f"SMTP connection closed from {peername}")

    async def shutdown(self) -> None:
        """Shutdown the SMTP server."""
        logger.info("Shutting down SMTP server...")
        self._shutdown_event.set()

        # Close all active connections
        if self._active_connections:
            logger.info(f"Closing {len(self._active_connections)} active connection(s)...")
            for writer in list(self._active_connections):
                if not writer.is_closing():
                    writer.close()
            # Wait for connections to close with timeout
            for writer in list(self._active_connections):
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=2.0)
                except (asyncio.TimeoutError, Exception):
                    pass
            self._active_connections.clear()

        if self._server:
            self._server.close()
            await self._server.wait_closed()

    @property
    def address(self) -> str:
        """Get the server address."""
        return f"{self.config.host}:{self.config.port}"
