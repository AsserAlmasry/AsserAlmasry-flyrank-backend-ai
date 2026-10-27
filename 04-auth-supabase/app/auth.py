"""The reusable guard: a FastAPI dependency that verifies the bearer token with Supabase."""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthApiError, AuthError

from .supabase_client import new_client

# auto_error=False: we return our own JSON error instead of FastAPI's default 403.
# Declaring HTTPBearer is also what makes Swagger UI show the "Authorize" padlock.
bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token from POST /auth/login")


class Unauthorized(Exception):
    """Turned into a 401 JSON response by an exception handler in main.py."""


class ProviderUnavailable(Exception):
    """Supabase could not be reached: a 503, not the user's fault, so never a 401."""


@dataclass
class AuthenticatedUser:
    id: str
    email: str | None
    created_at: str
    token: str


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    # HTTPBearer gives None when the header is missing or the scheme is not "Bearer".
    if credentials is None or not credentials.credentials.strip():
        raise Unauthorized("Access token required")
    token = credentials.credentials.strip()
    try:
        result = new_client().auth.get_user(token)  # Supabase checks the signature and expiry
    except AuthApiError:
        raise Unauthorized("Invalid or expired token")
    except AuthError as exc:
        raise ProviderUnavailable(f"Auth provider unavailable: {exc.message}")
    if result is None or result.user is None:
        raise Unauthorized("Invalid or expired token")
    user = result.user
    return AuthenticatedUser(id=user.id, email=user.email, created_at=str(user.created_at), token=token)
