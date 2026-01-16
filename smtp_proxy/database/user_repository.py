"""User repository for database operations."""

import hashlib
import secrets
from datetime import datetime

from ..models import User
from .connection import Database


class UserRepository:
    """Repository for user CRUD operations."""

    HASH_ITERATIONS = 100000

    def __init__(self, db: Database):
        self.db = db

    def create(self, username: str, password: str) -> int:
        """Create a new user and return their ID."""
        password_hash = self._hash_password(password)
        query = """
            INSERT INTO users (username, password_hash, created_at)
            VALUES (?, ?, ?)
        """
        cursor = self.db.execute(
            query,
            (username, password_hash, datetime.now().isoformat()),
        )
        return cursor.lastrowid

    def get_by_username(self, username: str) -> User | None:
        """Get a user by their username."""
        query = "SELECT * FROM users WHERE username = ?"
        row = self.db.fetchone(query, (username,))
        if row is None:
            return None
        return self._row_to_user(row)

    def get_by_id(self, user_id: int) -> User | None:
        """Get a user by their ID."""
        query = "SELECT * FROM users WHERE id = ?"
        row = self.db.fetchone(query, (user_id,))
        if row is None:
            return None
        return self._row_to_user(row)

    def verify_password(self, user: User, password: str) -> bool:
        """Verify a password against the stored hash."""
        try:
            salt, stored_hash = user.password_hash.split("$")
            computed_hash = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode(),
                salt.encode(),
                self.HASH_ITERATIONS,
            ).hex()
            return secrets.compare_digest(computed_hash, stored_hash)
        except (ValueError, AttributeError):
            return False

    def update_password(self, user_id: int, new_password: str) -> bool:
        """Update a user's password."""
        password_hash = self._hash_password(new_password)
        query = "UPDATE users SET password_hash = ? WHERE id = ?"
        cursor = self.db.execute(query, (password_hash, user_id))
        return cursor.rowcount > 0

    def exists(self, username: str) -> bool:
        """Check if a user with the given username exists."""
        query = "SELECT 1 FROM users WHERE username = ? LIMIT 1"
        row = self.db.fetchone(query, (username,))
        return row is not None

    def _hash_password(self, password: str) -> str:
        """Hash a password with a random salt using PBKDF2."""
        salt = secrets.token_hex(16)
        hash_value = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            self.HASH_ITERATIONS,
        ).hex()
        return f"{salt}${hash_value}"

    def _row_to_user(self, row) -> User:
        """Convert a database row to a User object."""
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            created_at=created_at,
        )
