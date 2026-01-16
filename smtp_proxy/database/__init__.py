"""Database module for SMTP Proxy."""

from .connection import Database
from .email_repository import EmailRepository
from .user_repository import UserRepository

__all__ = ["Database", "EmailRepository", "UserRepository"]
