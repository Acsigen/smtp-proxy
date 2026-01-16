# SMTP Proxy

A Python microservice that acts as an SMTP blackhole server with a web-based management UI. Emails are received via SMTP (with PLAIN/LOGIN and STARTTLS authentication), stored in SQLite, and can be viewed and managed through a Bootstrap-styled web interface.

## Features

- **SMTP Server**: Receives emails with PLAIN/LOGIN and STARTTLS authentication
- **Email Blackhole**: Stores emails in SQLite without forwarding
- **Web UI**: Bootstrap 5 interface for viewing and managing emails
- **Single User Login**: Session-based authentication for the web interface
- **Wipe History**: Button to delete all stored emails

## Requirements

- Python 3.12 or later

## Installation

### Setup Virtual Environment

```bash
git clone <repository-url>
cd smtp-proxy

# Create and activate virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

- `fastapi` - Web framework
- `uvicorn[standard]` - ASGI server
- `requests` - HTTP client library
- `jinja2` - Templating engine
- `python-multipart` - Form data handling
- `itsdangerous` - Signed cookies for sessions

## Configuration

The application uses a JSON configuration file. By default, it looks for `config.json` in the current directory.

### config.json

```json
{
    "smtp": {
        "host": "0.0.0.0",
        "port": 2525,
        "domain": "localhost",
        "read_timeout_seconds": 10,
        "write_timeout_seconds": 10,
        "max_message_bytes": 10485760,
        "max_recipients": 50,
        "allow_insecure_auth": false,
        "tls": {
            "enabled": true,
            "cert_file": "certs/server.crt",
            "key_file": "certs/server.key"
        },
        "auth": {
            "required": true,
            "username": "mailuser",
            "password": "mailpass"
        }
    },
    "web": {
        "host": "0.0.0.0",
        "port": 8080,
        "session_secret": "change-this-to-32-byte-secret!!",
        "session_name": "smtp_proxy_session"
    },
    "database": {
        "path": "./data/smtp_proxy.db"
    },
    "admin": {
        "username": "admin",
        "password": "changeme"
    }
}
```

### Configuration Options

| Section | Option | Description |
|---------|--------|-------------|
| smtp.host | string | SMTP server bind address |
| smtp.port | int | SMTP server port |
| smtp.domain | string | SMTP server domain name |
| smtp.tls.enabled | bool | Enable STARTTLS support |
| smtp.tls.cert_file | string | Path to TLS certificate |
| smtp.tls.key_file | string | Path to TLS private key |
| smtp.auth.required | bool | Require authentication for sending |
| smtp.auth.username | string | SMTP authentication username |
| smtp.auth.password | string | SMTP authentication password |
| web.host | string | Web server bind address |
| web.port | int | Web server port |
| web.session_secret | string | Secret key for session cookies |
| database.path | string | Path to SQLite database file |
| admin.username | string | Web UI admin username |
| admin.password | string | Web UI admin password |

## Usage

### Start the Server

```bash
# Activate virtual environment
source venv/bin/activate

# Using default config.json
python -m smtp_proxy.main

# Using custom config file
python -m smtp_proxy.main --config /path/to/config.json
```

### Access the Web UI

Open your browser and navigate to:

```
http://localhost:8080
```

Login with the admin credentials configured in `config.json` (default: `admin` / `changeme`).

### Send Test Emails

Using `swaks` (Swiss Army Knife for SMTP):

```bash
# Basic email without TLS
swaks --to recipient@example.com \
      --from sender@example.com \
      --server localhost:2525 \
      --auth PLAIN \
      --auth-user mailuser \
      --auth-password mailpass \
      --header "Subject: Test Email" \
      --body "This is a test message."
```

Using `curl` with SMTP:

```bash
curl --url "smtp://localhost:2525" \
     --user "mailuser:mailpass" \
     --mail-from "sender@example.com" \
     --mail-rcpt "recipient@example.com" \
     --upload-file email.txt
```

Using Python:

```python
import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg["Subject"] = "Test Email"
msg["From"] = "sender@example.com"
msg["To"] = "recipient@example.com"
msg.set_content("This is a test message.")

with smtplib.SMTP("localhost", 2525) as server:
    server.login("mailuser", "mailpass")
    server.send_message(msg)
```

## Enable STARTTLS

To enable STARTTLS support, generate TLS certificates:

```bash
# Create certs directory
mkdir -p certs

# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 \
    -keyout certs/server.key \
    -out certs/server.crt \
    -days 365 \
    -nodes \
    -subj "/CN=localhost"
```

Ensure `smtp.tls.enabled` is set to `true` in your config.json.

### Test with STARTTLS

```bash
swaks --to recipient@example.com \
      --from sender@example.com \
      --server localhost:2525 \
      --tls \
      --auth PLAIN \
      --auth-user mailuser \
      --auth-password mailpass
```

## Project Structure

```
smtp-proxy/
├── smtp_proxy/
│   ├── __init__.py
│   ├── main.py                  # Application entry point
│   ├── config.py                # Configuration loading
│   ├── models.py                # Email and User models
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py        # SQLite connection and schema
│   │   ├── email_repository.py  # Email CRUD operations
│   │   └── user_repository.py   # User CRUD operations
│   ├── smtp/
│   │   ├── __init__.py
│   │   ├── server.py            # Async SMTP server
│   │   └── session.py           # SMTP session handling
│   └── web/
│       ├── __init__.py
│       ├── app.py               # FastAPI application factory
│       ├── auth.py              # Session management
│       └── routes.py            # HTTP routes and handlers
├── templates/
│   ├── base.html                # Base layout template
│   ├── login.html               # Login page
│   ├── emails.html              # Email list page
│   └── email_detail.html        # Email detail page
├── certs/                       # TLS certificates (optional)
├── data/                        # SQLite database directory
├── config.json                  # Configuration file
├── requirements.txt             # Python dependencies
└── venv/                        # Virtual environment
```

## Database Schema

The application uses SQLite with the following schema:

### Users Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Emails Table

```sql
CREATE TABLE emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    recipients TEXT NOT NULL,
    subject TEXT DEFAULT '',
    body TEXT NOT NULL,
    raw_message BLOB NOT NULL,
    size_bytes INTEGER NOT NULL,
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'received',
    smtp_auth_user TEXT DEFAULT '',
    client_ip TEXT DEFAULT ''
);
```

## Security Notes

- Change the default `session_secret` in production
- Change the default admin and SMTP credentials
- Use HTTPS reverse proxy in production for the web UI
- Enable STARTTLS with proper certificates in production

## Roadmap

- [x] Deliver emails to blackhole
- [ ] Integrate with cloud email providers for forwarding:
  - [ ] GMail
  - [ ] Outlook/Microsoft 365
  - [ ] Yahoo Mail

## License

AGPLv3 License
