"""
Authentication endpoints and helpers for demo password login.

Phase 0 implementation:
- Single password from settings.demo_password (local or Secrets Manager in AWS)
- Issues an HMAC-signed session token stored in an HttpOnly cookie
- Stateless verification (no database/session store)

Future phases can replace the token generator with a managed identity provider
without changing the route contract.
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, TypedDict, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Auth"],
    responses={
        200: {"description": "Login successful"},
        401: {"description": "Invalid credentials"},
        204: {"description": "Logout successful"},
    },
)


class LoginRequest(BaseModel):
    """Login request payload."""

    password: str = Field(..., min_length=4, max_length=256)


class LoginResponse(BaseModel):
    """Login success response."""

    message: str = Field(..., examples=["Login successful"])


class MeResponse(BaseModel):
    """Session validation response."""

    status: str = Field(..., examples=["ok"])
    subject: str = Field(..., examples=["demo-user"])


class SessionPayload(TypedDict):
    """Payload stored inside the signed session token."""

    sub: str
    exp: int
    iat: int


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign_payload(payload: SessionPayload, secret: str) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    encoded_payload = _b64url_encode(payload_json)
    signature = hmac.new(
        secret.encode("utf-8"), encoded_payload.encode("utf-8"), sha256
    )
    encoded_sig = _b64url_encode(signature.digest())
    return f"{encoded_payload}.{encoded_sig}"


def _verify_token(token: str, secret: str) -> SessionPayload:
    try:
        encoded_payload, encoded_sig = token.split(".", maxsplit=1)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token."
        ) from exc

    expected_sig = _b64url_encode(
        hmac.new(
            secret.encode("utf-8"), encoded_payload.encode("utf-8"), sha256
        ).digest()
    )

    if not hmac.compare_digest(encoded_sig, expected_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token."
        )

    try:
        payload_bytes = _b64url_decode(encoded_payload)
        payload = cast(dict[str, Any], json.loads(payload_bytes))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token."
        ) from exc

    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token."
        )

    if datetime.now(timezone.utc).timestamp() > exp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired."
        )

    return SessionPayload(
        sub=str(payload.get("sub", "demo")),
        exp=exp,
        iat=int(payload.get("iat", exp)),
    )


def _issue_session_token(settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.auth_token_expires_minutes)
    payload: SessionPayload = {
        "sub": "demo-user",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return _sign_payload(payload, settings.auth_token_secret.get_secret_value())


def _cookie_params(settings: Settings) -> dict[str, Any]:
    if settings.is_aws():
        return {"secure": True, "samesite": "none"}
    return {"secure": False, "samesite": "lax"}


@router.post(
    "/api/login",
    response_model=LoginResponse,
    summary="Login with demo password",
    description="Authenticate using the demo password and receive an HttpOnly session cookie.",
)
async def login(
    request: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    """Authenticate the user via demo password and set a session cookie."""
    expected_password = settings.demo_password.get_secret_value()
    if request.password != expected_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password."
        )

    token = _issue_session_token(settings)

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        max_age=int(
            timedelta(minutes=settings.auth_token_expires_minutes).total_seconds()
        ),
        path="/",
        **_cookie_params(settings),
    )

    logger.info("User authenticated via demo password.")
    return LoginResponse(message="Login successful")


async def require_session(
    request: Request, settings: Settings = Depends(get_settings)
) -> SessionPayload:
    """
    Dependency that validates the session cookie.

    Raises 401 if the cookie is missing or invalid. Returns the session payload
    for use in protected routes.
    """
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return _verify_token(token, settings.auth_token_secret.get_secret_value())


@router.get(
    "/api/me",
    response_model=MeResponse,
    summary="Validate current session",
    description="Returns 200 if the session cookie is valid.",
)
async def me(
    session: SessionPayload = Depends(require_session),
) -> MeResponse:
    """Validate the current session cookie."""
    return MeResponse(status="ok", subject=session["sub"])


@router.post(
    "/api/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Logout and clear session",
    description="Clears the session cookie.",
)
async def logout(
    response: Response, settings: Settings = Depends(get_settings)
) -> Response:
    """Clear the session cookie to log out."""
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        **_cookie_params(settings),
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


__all__ = [
    "router",
    "require_session",
    "SessionPayload",
    "LoginRequest",
    "LoginResponse",
]
