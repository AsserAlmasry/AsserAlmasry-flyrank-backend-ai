"""Accounts: passwords hashed with scrypt (Python standard library), sessions as signed JWTs (PyJWT, HS256).

No cryptography is hand-written here: scrypt and HMAC-SHA256 come from vetted libraries; this file only wires them up.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config, db

SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
bearer = HTTPBearer(auto_error=False, description="Paste the access_token from POST /auth/login")


def secret() -> str:
    if len(config.JWT_SECRET) < 32 or config.JWT_SECRET.startswith("change-me"):
        raise RuntimeError("Set JWT_SECRET in .env to a long random string (32+ characters).")
    return config.JWT_SECRET


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), **SCRYPT)
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))  # constant-time compare
    except (ValueError, TypeError):
        return False


def issue_token(user_id: int, email: str) -> dict:
    exp = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_TTL_MINUTES)
    token = jwt.encode({"sub": str(user_id), "email": email, "exp": exp}, secret(), algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "expires_in": config.JWT_TTL_MINUTES * 60}


def current_user(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
    """FastAPI dependency = the guard on every protected route."""
    if creds is None or not creds.credentials:
        raise HTTPException(401, "Access token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = jwt.decode(creds.credentials, secret(), algorithms=["HS256"])  # checks signature AND expiry
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired, log in again", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate": "Bearer"})
    with db.tx() as conn:
        user = conn.execute("SELECT id, email, created_at FROM users WHERE id=?", (int(claims["sub"]),)).fetchone()
    if user is None:
        raise HTTPException(401, "User no longer exists", headers={"WWW-Authenticate": "Bearer"})
    return dict(user)


CurrentUser = Annotated[dict, Depends(current_user)]
