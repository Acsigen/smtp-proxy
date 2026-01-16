"""SMTP session handler for individual client connections."""

import asyncio
import base64
import ssl
from datetime import datetime
from email import message_from_bytes
from email.policy import default as email_policy

from ..config import SMTPConfig
from ..database.email_repository import EmailRepository
from ..models import Email


class SMTPSession:
    """Handles a single SMTP client connection."""

    def __init__(
        self,
        config: SMTPConfig,
        email_repo: EmailRepository,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.config = config
        self.email_repo = email_repo
        self.reader = reader
        self.writer = writer

        # Session state
        self.authenticated = False
        self.auth_user = ""
        self.mail_from = ""
        self.rcpt_to: list[str] = []
        self.client_ip = ""

    async def handle(self) -> None:
        """Handle the SMTP session."""
        try:
            peername = self.writer.get_extra_info("peername")
            self.client_ip = peername[0] if peername else "unknown"

            await self._send(f"220 {self.config.domain} SMTP Ready")

            while True:
                try:
                    line = await asyncio.wait_for(
                        self.reader.readline(),
                        timeout=self.config.read_timeout_seconds,
                    )
                    if not line:
                        break

                    command = line.decode("utf-8", errors="replace").strip()
                    if not command:
                        continue

                    if not await self._process_command(command):
                        break
                except asyncio.TimeoutError:
                    await self._send("421 Timeout")
                    break
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass

    async def _process_command(self, line: str) -> bool:
        """Process a single SMTP command. Returns False to end session."""
        parts = line.split(None, 1)
        cmd = parts[0].upper() if parts else ""

        if cmd in ("EHLO", "HELO"):
            return await self._handle_ehlo(line)
        elif cmd == "AUTH":
            return await self._handle_auth(line)
        elif cmd == "MAIL":
            return await self._handle_mail(line)
        elif cmd == "RCPT":
            return await self._handle_rcpt(line)
        elif cmd == "DATA":
            return await self._handle_data()
        elif cmd == "RSET":
            return await self._handle_rset()
        elif cmd == "QUIT":
            await self._send("221 Bye")
            return False
        elif cmd == "NOOP":
            await self._send("250 OK")
            return True
        elif cmd == "STARTTLS":
            return await self._handle_starttls()
        else:
            await self._send("500 Unknown command")
            return True

    async def _handle_ehlo(self, line: str) -> bool:
        """Handle EHLO/HELO command."""
        extensions = [f"250-{self.config.domain} Hello"]

        if self.config.auth.required or self.config.auth.username:
            extensions.append("250-AUTH PLAIN LOGIN")

        if self.config.tls.enabled:
            extensions.append("250-STARTTLS")

        extensions.append(f"250-SIZE {self.config.max_message_bytes}")
        extensions.append("250 OK")

        for ext in extensions:
            await self._send(ext)
        return True

    async def _handle_auth(self, line: str) -> bool:
        """Handle AUTH command."""
        parts = line.split()
        if len(parts) < 2:
            await self._send("501 Syntax error")
            return True

        mechanism = parts[1].upper()
        if mechanism not in ("PLAIN", "LOGIN"):
            await self._send("504 Unsupported authentication mechanism")
            return True

        if mechanism == "PLAIN":
            return await self._handle_auth_plain(parts)
        else:
            return await self._handle_auth_login()

    async def _handle_auth_plain(self, parts: list[str]) -> bool:
        """Handle AUTH PLAIN mechanism."""
        if len(parts) == 3:
            credentials = parts[2]
        else:
            await self._send("334 ")
            try:
                cred_line = await asyncio.wait_for(
                    self.reader.readline(),
                    timeout=self.config.read_timeout_seconds,
                )
                credentials = cred_line.decode().strip()
            except asyncio.TimeoutError:
                await self._send("421 Timeout")
                return False

        try:
            decoded = base64.b64decode(credentials).decode()
            # Format: \0username\0password or identity\0username\0password
            parts = decoded.split("\0")
            if len(parts) >= 3:
                username, password = parts[1], parts[2]
            elif len(parts) == 2:
                username, password = parts[0], parts[1]
            else:
                raise ValueError("Invalid credentials format")

            if (
                username == self.config.auth.username
                and password == self.config.auth.password
            ):
                self.authenticated = True
                self.auth_user = username
                await self._send("235 Authentication successful")
                return True
        except Exception:
            pass

        await self._send("535 Authentication failed")
        return True

    async def _handle_auth_login(self) -> bool:
        """Handle AUTH LOGIN mechanism."""
        try:
            # Send username prompt
            await self._send("334 VXNlcm5hbWU6")  # Base64 "Username:"
            username_line = await asyncio.wait_for(
                self.reader.readline(),
                timeout=self.config.read_timeout_seconds,
            )
            username = base64.b64decode(username_line.strip()).decode()

            # Send password prompt
            await self._send("334 UGFzc3dvcmQ6")  # Base64 "Password:"
            password_line = await asyncio.wait_for(
                self.reader.readline(),
                timeout=self.config.read_timeout_seconds,
            )
            password = base64.b64decode(password_line.strip()).decode()

            if (
                username == self.config.auth.username
                and password == self.config.auth.password
            ):
                self.authenticated = True
                self.auth_user = username
                await self._send("235 Authentication successful")
                return True
        except Exception:
            pass

        await self._send("535 Authentication failed")
        return True

    async def _handle_mail(self, line: str) -> bool:
        """Handle MAIL FROM command."""
        if self.config.auth.required and not self.authenticated:
            await self._send("530 Authentication required")
            return True

        upper_line = line.upper()
        if "FROM:" not in upper_line:
            await self._send("501 Syntax error")
            return True

        # Extract address after FROM:
        idx = upper_line.index("FROM:")
        addr = line[idx + 5 :].strip()

        # Handle SIZE parameter
        if " " in addr:
            addr = addr.split()[0]

        # Remove angle brackets
        if addr.startswith("<") and addr.endswith(">"):
            addr = addr[1:-1]

        self.mail_from = addr
        await self._send("250 OK")
        return True

    async def _handle_rcpt(self, line: str) -> bool:
        """Handle RCPT TO command."""
        if self.config.auth.required and not self.authenticated:
            await self._send("530 Authentication required")
            return True

        if len(self.rcpt_to) >= self.config.max_recipients:
            await self._send("452 Too many recipients")
            return True

        upper_line = line.upper()
        if "TO:" not in upper_line:
            await self._send("501 Syntax error")
            return True

        # Extract address after TO:
        idx = upper_line.index("TO:")
        addr = line[idx + 3 :].strip()

        # Remove angle brackets
        if addr.startswith("<") and addr.endswith(">"):
            addr = addr[1:-1]

        self.rcpt_to.append(addr)
        await self._send("250 OK")
        return True

    async def _handle_data(self) -> bool:
        """Handle DATA command."""
        if self.config.auth.required and not self.authenticated:
            await self._send("530 Authentication required")
            return True

        if not self.mail_from or not self.rcpt_to:
            await self._send("503 Bad sequence of commands")
            return True

        await self._send("354 Start mail input; end with <CRLF>.<CRLF>")

        data = []
        total_size = 0

        while True:
            try:
                line = await asyncio.wait_for(
                    self.reader.readline(),
                    timeout=self.config.read_timeout_seconds,
                )
            except asyncio.TimeoutError:
                await self._send("421 Timeout")
                return False

            # Check for end of data
            if line in (b".\r\n", b".\n"):
                break

            # Dot-stuffing: remove leading dot if doubled
            if line.startswith(b".."):
                line = line[1:]

            total_size += len(line)
            if total_size > self.config.max_message_bytes:
                await self._send("552 Message too large")
                self._reset_transaction()
                return True

            data.append(line)

        raw_message = b"".join(data)

        # Parse email
        subject = ""
        body = ""
        try:
            msg = message_from_bytes(raw_message, policy=email_policy)
            subject = msg.get("Subject", "") or ""

            # Extract body
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        try:
                            body = part.get_content()
                        except Exception:
                            body = str(part.get_payload(decode=True) or "")
                        break
            else:
                try:
                    body = msg.get_content()
                except Exception:
                    payload = msg.get_payload(decode=True)
                    body = payload.decode("utf-8", errors="replace") if payload else ""
        except Exception:
            # If parsing fails, use raw message
            body = raw_message.decode("utf-8", errors="replace")

        if not isinstance(body, str):
            body = str(body)

        email = Email(
            sender=self.mail_from,
            recipients=self.rcpt_to.copy(),
            subject=subject,
            body=body,
            raw_message=raw_message,
            size_bytes=len(raw_message),
            received_at=datetime.now(),
            status="received",
            auth_user=self.auth_user,
            client_ip=self.client_ip,
        )

        self.email_repo.create(email)
        await self._send("250 OK: Message accepted")

        self._reset_transaction()
        return True

    async def _handle_rset(self) -> bool:
        """Handle RSET command."""
        self._reset_transaction()
        await self._send("250 OK")
        return True

    async def _handle_starttls(self) -> bool:
        """Handle STARTTLS command."""
        if not self.config.tls.enabled:
            await self._send("502 STARTTLS not available")
            return True

        await self._send("220 Ready to start TLS")

        try:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.load_cert_chain(
                self.config.tls.cert_file,
                self.config.tls.key_file,
            )

            # Upgrade connection to TLS
            transport = self.writer.transport
            protocol = transport.get_protocol()

            loop = asyncio.get_event_loop()
            new_transport = await loop.start_tls(
                transport,
                protocol,
                ssl_context,
                server_side=True,
            )

            # Update writer with new transport
            self.writer._transport = new_transport

            # Reset session state after STARTTLS
            self.authenticated = False
            self.auth_user = ""
            self._reset_transaction()

        except Exception as e:
            await self._send(f"454 TLS not available: {e}")

        return True

    def _reset_transaction(self) -> None:
        """Reset the current mail transaction."""
        self.mail_from = ""
        self.rcpt_to = []

    async def _send(self, message: str) -> None:
        """Send a response to the client."""
        try:
            self.writer.write(f"{message}\r\n".encode())
            await self.writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
