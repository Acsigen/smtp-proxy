"""Email repository for database operations."""

from datetime import datetime

from ..models import Email
from .connection import Database


class EmailRepository:
    """Repository for email CRUD operations."""

    def __init__(self, db: Database):
        self.db = db

    def create(self, email: Email) -> int:
        """Create a new email and return its ID."""
        query = """
            INSERT INTO emails (sender, recipients, subject, body, raw_message,
                              size_bytes, received_at, status, smtp_auth_user, client_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor = self.db.execute(
            query,
            (
                email.sender,
                email.recipients_json(),
                email.subject,
                email.body,
                email.raw_message,
                email.size_bytes,
                email.received_at.isoformat(),
                email.status,
                email.auth_user,
                email.client_ip,
            ),
        )
        return cursor.lastrowid

    def get_by_id(self, email_id: int) -> Email | None:
        """Get an email by its ID."""
        query = "SELECT * FROM emails WHERE id = ?"
        row = self.db.fetchone(query, (email_id,))
        if row is None:
            return None
        return self._row_to_email(row)

    def get_all(self) -> list[Email]:
        """Get all emails ordered by received_at descending."""
        query = "SELECT * FROM emails ORDER BY received_at DESC"
        rows = self.db.fetchall(query)
        return [self._row_to_email(row) for row in rows]

    def update_status(self, email_id: int, status: str) -> bool:
        """Update the status of an email."""
        query = "UPDATE emails SET status = ? WHERE id = ?"
        cursor = self.db.execute(query, (status, email_id))
        return cursor.rowcount > 0

    def delete_all(self) -> int:
        """Delete all emails and return the count of deleted rows."""
        query = "DELETE FROM emails"
        cursor = self.db.execute(query)
        return cursor.rowcount

    def count(self) -> int:
        """Get the total count of emails."""
        query = "SELECT COUNT(*) as count FROM emails"
        row = self.db.fetchone(query)
        return row["count"] if row else 0

    def _row_to_email(self, row) -> Email:
        """Convert a database row to an Email object."""
        received_at = row["received_at"]
        if isinstance(received_at, str):
            received_at = datetime.fromisoformat(received_at)

        return Email(
            id=row["id"],
            sender=row["sender"],
            recipients=Email.parse_recipients_json(row["recipients"]),
            subject=row["subject"],
            body=row["body"],
            raw_message=row["raw_message"],
            size_bytes=row["size_bytes"],
            received_at=received_at,
            status=row["status"],
            auth_user=row["smtp_auth_user"],
            client_ip=row["client_ip"],
        )
