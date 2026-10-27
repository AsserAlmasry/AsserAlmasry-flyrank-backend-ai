"""Auth API: sign up / log in / log out through Supabase, plus routes protected by a bearer token."""
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from supabase_auth.errors import AuthApiError, AuthError

from .auth import AuthenticatedUser, ProviderUnavailable, Unauthorized, current_user
from .supabase_client import get_settings, new_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    url, _key = get_settings()
    new_client()  # fails fast if the URL/key are malformed
    print(f"Server running and connected to Supabase ({url})")
    yield


app = FastAPI(
    title="Auth API (Supabase)",
    version="1.0",
    description="Sign up and log in with Supabase Auth, then click **Authorize** and paste your `access_token` "
    "to call the `/protected/*` routes.",
    lifespan=lifespan,
)


class Credentials(BaseModel):
    email: str | None = Field(default=None, examples=["test@example.com"])
    password: str | None = Field(default=None, examples=["password123"])


class ErrorBody(BaseModel):
    error: str


E400 = {400: {"model": ErrorBody, "description": "Missing or invalid input"}}
E401 = {401: {"model": ErrorBody, "description": "Missing, invalid or expired token / bad credentials"}}


def error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, __: RequestValidationError):
    return error(400, "Request body must be JSON with 'email' and 'password'")


@app.exception_handler(Unauthorized)
async def unauthorized(_: Request, exc: Unauthorized):
    return JSONResponse(status_code=401, content={"error": str(exc)}, headers={"WWW-Authenticate": "Bearer"})


@app.exception_handler(ProviderUnavailable)
async def provider_unavailable(_: Request, exc: ProviderUnavailable):
    return error(503, str(exc))


def missing_fields(body: Credentials) -> JSONResponse | None:
    missing = [f for f in ("email", "password") if not (getattr(body, f) or "").strip()]
    return error(400, f"Missing required field(s): {', '.join(missing)}") if missing else None


# ---------------------------------------------------------------- open routes

@app.get("/health", tags=["public"])
def health():
    return {"status": "ok"}


@app.get("/public/info", tags=["public"], summary="Public data, no token needed")
def public_info():
    return {"message": "Welcome stranger! This info is public."}


@app.post("/auth/signup", status_code=201, tags=["auth"], responses=E400, summary="Create an account")
def signup(body: Credentials):
    if (resp := missing_fields(body)) is not None:
        return resp
    try:
        result = new_client().auth.sign_up({"email": body.email.strip(), "password": body.password})
    except AuthApiError as exc:  # weak password, invalid email, rate limit...
        return error(400, exc.message)
    except AuthError as exc:
        return error(503, f"Auth provider unavailable: {exc.message}")
    user = result.user
    return {
        "id": user.id if user else None,
        "email": user.email if user else body.email,
        "created_at": str(user.created_at) if user else None,
        # With "Confirm email" switched on in Supabase there is no session until the user clicks the email link.
        "email_confirmation_required": result.session is None,
    }


@app.post("/auth/login", tags=["auth"], responses={**E400, **E401}, summary="Log in, get an access token (JWT)")
def login(body: Credentials):
    if (resp := missing_fields(body)) is not None:
        return resp
    try:
        result = new_client().auth.sign_in_with_password({"email": body.email.strip(), "password": body.password})
    except AuthApiError:
        return error(401, "Invalid login credentials")
    except AuthError as exc:
        return error(503, f"Auth provider unavailable: {exc.message}")
    session = result.session
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "token_type": "bearer",
        "expires_in": session.expires_in,
    }


# ---------------------------------------------------------- protected routes
# Every route below declares `Depends(current_user)`. The dependency runs first; the route body only runs
# for a verified user. That is the FastAPI version of Express middleware.

CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]


@app.post("/auth/logout", status_code=204, tags=["auth"], responses=E401, summary="End the session")
def logout(user: CurrentUser):
    try:
        new_client().auth.admin.sign_out(user.token)  # POST /logout with the user's own JWT
    except AuthApiError:
        pass  # session already gone: the result the client wanted
    return Response(status_code=204)


@app.get("/protected/profile", tags=["protected"], responses=E401, summary="Your private profile")
def profile(user: CurrentUser):
    return {"id": user.id, "email": user.email, "created_at": user.created_at}


@app.get("/protected/dashboard", tags=["protected"], responses=E401, summary="A second protected door")
def dashboard(user: CurrentUser):
    return {"message": f"Welcome back, {user.email}!", "user_id": user.id}
