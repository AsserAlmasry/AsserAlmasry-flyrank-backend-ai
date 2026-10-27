from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from supabase_auth.errors import AuthApiError, AuthError

from .supabase_client import get_settings, new_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    url, _key = get_settings()
    new_client()  # fails fast if the URL/key are malformed
    print(f"Server running and connected to Supabase ({url})")
    yield


app = FastAPI(title="Auth API (Supabase)", version="1.0", lifespan=lifespan)


class Credentials(BaseModel):
    email: str | None = None
    password: str | None = None


def error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return error(400, "Request body must be JSON with 'email' and 'password'")


def missing_fields(body: Credentials) -> JSONResponse | None:
    missing = [f for f in ("email", "password") if not (getattr(body, f) or "").strip()]
    return error(400, f"Missing required field(s): {', '.join(missing)}") if missing else None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/signup", status_code=201)
def signup(body: Credentials):
    if (resp := missing_fields(body)) is not None:
        return resp
    try:
        result = new_client().auth.sign_up({"email": body.email.strip(), "password": body.password})
    except AuthApiError as exc:  # e.g. weak password, invalid email, user already exists
        return error(400, exc.message)
    except AuthError as exc:
        return error(502, f"Auth provider error: {exc.message}")
    user = result.user
    return {
        "id": user.id if user else None,
        "email": user.email if user else body.email,
        "created_at": str(user.created_at) if user else None,
        # When "Confirm email" is on in Supabase, there is no session until the user clicks the email link.
        "email_confirmation_required": result.session is None,
    }


@app.post("/auth/login")
def login(body: Credentials):
    if (resp := missing_fields(body)) is not None:
        return resp
    try:
        result = new_client().auth.sign_in_with_password({"email": body.email.strip(), "password": body.password})
    except AuthApiError:
        return error(401, "Invalid login credentials")
    session = result.session
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": "bearer",
        "expires_in": session.expires_in,
    }


def extract_bearer_token(request: Request) -> str | None:
    """Return the token from 'Authorization: Bearer <token>', or None if missing/malformed."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


@app.get("/public/info")
def public_info():
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile")
def profile(request: Request):
    token = extract_bearer_token(request)
    if token is None:
        return error(401, "Access token required")
    try:
        result = new_client().auth.get_user(token)  # Supabase checks signature + expiry
    except AuthApiError:
        return error(401, "Invalid or expired token")
    if result is None or result.user is None:
        return error(401, "Invalid or expired token")
    user = result.user
    return {"id": user.id, "email": user.email, "created_at": str(user.created_at)}
