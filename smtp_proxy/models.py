"""Data models for SMTP Proxy."""

from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class Email:
    """Email model representing a received email."""
    id: int = 0
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    raw_message: bytes = b""
    size_bytes: int = 0
    received_at: datetime = field(default_factory=datetime.now)
    status: str = "received"
    auth_user: str = ""
    client_ip: str = ""

    def recipients_json(self) -> str:
        """Return recipients as a JSON string."""
        return json.dumps(self.recipients)

    @staticmethod
    def parse_recipients_json(recipients_json: str) -> list[str]:
        """Parse recipients from a JSON string."""
        try:
            return json.loads(recipients_json)
        except (json.JSONDecodeError, TypeError):
            return []

    def recipients_display(self) -> str:
        """Return recipients as a comma-separated string for display."""
        return ", ".join(self.recipients)

    def is_read(self) -> bool:
        """Check if the email has been read."""
        return self.status == "read"

    def is_new(self) -> bool:
        """Check if the email is new (unread)."""
        return self.status == "received"


@dataclass
class User:
    """User model for authentication."""
    id: int = 0
    username: str = ""
    password_hash: str = ""
    created_at: datetime = field(default_factory=datetime.now)
