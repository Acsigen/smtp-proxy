"""Web routes for the SMTP Proxy UI."""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from .auth import SessionManager
from ..database.email_repository import EmailRepository
from ..database.user_repository import UserRepository

router = APIRouter()


def get_session_manager(request: Request) -> SessionManager:
    """Get session manager from app state."""
    return request.app.state.session_manager


def get_email_repo(request: Request) -> EmailRepository:
    """Get email repository from app state."""
    return request.app.state.email_repo


def get_user_repo(request: Request) -> UserRepository:
    """Get user repository from app state."""
    return request.app.state.user_repo


def require_auth(request: Request) -> dict:
    """Check authentication and return session data."""
    session_manager = get_session_manager(request)
    session = session_manager.get_session(request)

    if not session or "user_id" not in session:
        raise HTTPException(status_code=303, headers={"Location": "/login"})

    return session


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    session_manager = get_session_manager(request)
    session = session_manager.get_session(request)

    # Redirect to emails if already logged in
    if session and "user_id" in session:
        return RedirectResponse("/emails", status_code=303)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None},
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Process login form submission."""
    user_repo = get_user_repo(request)
    session_manager = get_session_manager(request)
    templates = request.app.state.templates

    user = user_repo.get_by_username(username)
    if not user or not user_repo.verify_password(user, password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
            status_code=401,
        )

    response = RedirectResponse("/emails", status_code=303)
    session_manager.create_session(response, user.id, user.username)
    return response


@router.post("/logout")
async def logout(request: Request):
    """Log out the current user."""
    session_manager = get_session_manager(request)
    response = RedirectResponse("/login", status_code=303)
    session_manager.destroy_session(response)
    return response


@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to emails page."""
    try:
        require_auth(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)
    return RedirectResponse("/emails", status_code=303)


@router.get("/emails", response_class=HTMLResponse)
async def email_list(request: Request):
    """Display the list of all emails."""
    try:
        session = require_auth(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)

    email_repo = get_email_repo(request)
    templates = request.app.state.templates

    emails = email_repo.get_all()
    email_count = len(emails)

    return templates.TemplateResponse(
        "emails.html",
        {
            "request": request,
            "emails": emails,
            "email_count": email_count,
            "username": session.get("username"),
        },
    )


@router.get("/emails/{email_id}", response_class=HTMLResponse)
async def email_detail(request: Request, email_id: int):
    """Display a single email's details."""
    try:
        session = require_auth(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)

    email_repo = get_email_repo(request)
    templates = request.app.state.templates

    email = email_repo.get_by_id(email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    return templates.TemplateResponse(
        "email_detail.html",
        {
            "request": request,
            "email": email,
            "username": session.get("username"),
        },
    )


@router.post("/emails/{email_id}/mark-read")
async def mark_email_read(request: Request, email_id: int):
    """Mark an email as read."""
    try:
        require_auth(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)

    email_repo = get_email_repo(request)
    email_repo.update_status(email_id, "read")

    return RedirectResponse(f"/emails/{email_id}", status_code=303)


@router.post("/emails/wipe")
async def wipe_emails(request: Request):
    """Delete all emails."""
    try:
        require_auth(request)
    except HTTPException:
        return RedirectResponse("/login", status_code=303)

    email_repo = get_email_repo(request)
    email_repo.delete_all()

    return RedirectResponse("/emails", status_code=303)
