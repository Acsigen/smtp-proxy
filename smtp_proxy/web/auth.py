"""Session management using signed cookies."""

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request, Response


class SessionManager:
    """Manages user sessions using signed cookies."""

    def __init__(self, secret: str, cookie_name: str, max_age: int = 86400):
        self.serializer = URLSafeTimedSerializer(secret)
        self.cookie_name = cookie_name
        self.max_age = max_age

    def create_session(
        self, response: Response, user_id: int, username: str
    ) -> None:
        """Create a new session and set the cookie."""
        data = {"user_id": user_id, "username": username}
        token = self.serializer.dumps(data)
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            max_age=self.max_age,
            httponly=True,
            samesite="lax",
        )

    def get_session(self, request: Request) -> dict | None:
        """Get session data from the request cookie."""
        token = request.cookies.get(self.cookie_name)
        if not token:
            return None
        try:
            data = self.serializer.loads(token, max_age=self.max_age)
            return data
        except (BadSignature, SignatureExpired):
            return None

    def destroy_session(self, response: Response) -> None:
        """Destroy the session by deleting the cookie."""
        response.delete_cookie(self.cookie_name)

    def get_user_id(self, request: Request) -> int | None:
        """Get the user ID from the session."""
        session = self.get_session(request)
        if session:
            return session.get("user_id")
        return None

    def get_username(self, request: Request) -> str | None:
        """Get the username from the session."""
        session = self.get_session(request)
        if session:
            return session.get("username")
        return None
