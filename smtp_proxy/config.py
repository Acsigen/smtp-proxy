"""Configuration loading and validation for SMTP Proxy."""

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class TLSConfig:
    """TLS/STARTTLS configuration."""
    enabled: bool = False
    cert_file: str = "certs/server.crt"
    key_file: str = "certs/server.key"


@dataclass
class AuthConfig:
    """SMTP authentication configuration."""
    required: bool = True
    username: str = "mailuser"
    password: str = "mailpass"


@dataclass
class SMTPConfig:
    """SMTP server configuration."""
    host: str = "0.0.0.0"
    port: int = 2525
    domain: str = "localhost"
    read_timeout_seconds: int = 10
    write_timeout_seconds: int = 10
    max_message_bytes: int = 10485760  # 10MB
    max_recipients: int = 50
    allow_insecure_auth: bool = True
    tls: TLSConfig = field(default_factory=TLSConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class WebConfig:
    """Web server configuration."""
    host: str = "0.0.0.0"
    port: int = 8080
    session_secret: str = "change-this-to-32-byte-secret!!"
    session_name: str = "smtp_proxy_session"

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "./data/smtp_proxy.db"


@dataclass
class AdminConfig:
    """Admin user configuration."""
    username: str = "admin"
    password: str = "changeme"


@dataclass
class Config:
    """Main application configuration."""
    smtp: SMTPConfig = field(default_factory=SMTPConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    admin: AdminConfig = field(default_factory=AdminConfig)

    @classmethod
    def load(cls, path: str) -> "Config":
        """Load configuration from a JSON file."""
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(config_path, "r") as f:
            data = json.load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Create Config from a dictionary."""
        smtp_data = data.get("smtp", {})
        tls_data = smtp_data.pop("tls", {})
        auth_data = smtp_data.pop("auth", {})

        smtp_config = SMTPConfig(
            **smtp_data,
            tls=TLSConfig(**tls_data),
            auth=AuthConfig(**auth_data),
        )

        web_config = WebConfig(**data.get("web", {}))
        database_config = DatabaseConfig(**data.get("database", {}))
        admin_config = AdminConfig(**data.get("admin", {}))

        config = cls(
            smtp=smtp_config,
            web=web_config,
            database=database_config,
            admin=admin_config,
        )

        config.validate()
        return config

    def validate(self) -> None:
        """Validate the configuration."""
        errors = []

        if self.smtp.port <= 0 or self.smtp.port > 65535:
            errors.append("SMTP port must be between 1 and 65535")

        if self.web.port <= 0 or self.web.port > 65535:
            errors.append("Web port must be between 1 and 65535")

        if not self.database.path:
            errors.append("Database path is required")

        if not self.admin.username:
            errors.append("Admin username is required")

        if not self.admin.password:
            errors.append("Admin password is required")

        if self.smtp.tls.enabled:
            if not Path(self.smtp.tls.cert_file).exists():
                errors.append(f"TLS certificate file not found: {self.smtp.tls.cert_file}")
            if not Path(self.smtp.tls.key_file).exists():
                errors.append(f"TLS key file not found: {self.smtp.tls.key_file}")

        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
