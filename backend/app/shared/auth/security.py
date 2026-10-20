"""Security utilities: Argon2id password hashing, JWT token handling, and login rate limiting.

Component: Shared Platform Authentication & Authorization
"""

import threading
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
)

from app.config import Settings

# Standard Argon2id password hasher with secure defaults
_hasher = PasswordHasher()

# Precomputed dummy Argon2id hash for constant-time comparison on unknown email attempts
_DUMMY_ARGON2_HASH = _hasher.hash("dummy_mitigation_password_for_timing")


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _hasher.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify_password(password: str) -> None:
    """Perform dummy verification to mitigate user-enumeration timing discrepancies."""
    verify_password(password, _DUMMY_ARGON2_HASH)


def create_access_token(
    user_id: int | str,
    settings: Settings,
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """Create a signed JWT access token.

    Claims:
    - sub: stable string representation of user ID
    - exp: expiration timestamp (UTC)
    - iat: issued-at timestamp (UTC)
    - iss: optional issuer
    - aud: optional audience

    Returns:
        tuple[str, int]: (encoded_jwt_token, expires_in_seconds)
    """
    secret = settings.auth_secret_key.get_secret_value().strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service is misconfigured: AUTH_SECRET_KEY is missing.",
        )

    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
        expires_in = int(expires_delta.total_seconds())
    else:
        minutes = max(1, settings.auth_access_token_expire_minutes)
        expire = now + timedelta(minutes=minutes)
        expires_in = minutes * 60

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    if settings.auth_jwt_issuer:
        payload["iss"] = settings.auth_jwt_issuer
    if settings.auth_jwt_audience:
        payload["aud"] = settings.auth_jwt_audience

    encoded_token = jwt.encode(
        payload,
        secret,
        algorithm=settings.auth_jwt_algorithm,
    )
    return encoded_token, expires_in


def decode_access_token(
    token: str,
    settings: Settings,
) -> dict[str, Any]:
    """Verify and decode a JWT access token.

    Validates:
    - Signature using configured AUTH_SECRET_KEY
    - Algorithm strictly matching configured AUTH_JWT_ALGORITHM (never derived from token)
    - Required claims: 'sub', 'exp', 'iat'
    - Configured issuer and audience if present
    """
    secret = settings.auth_secret_key.get_secret_value().strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service is misconfigured: AUTH_SECRET_KEY is missing.",
        )

    options = {
        "require": ["sub", "exp", "iat"],
        "verify_signature": True,
        "verify_exp": True,
        "verify_iat": True,
    }

    kwargs: dict[str, Any] = {
        "algorithms": [settings.auth_jwt_algorithm],
        "options": options,
    }

    if settings.auth_jwt_issuer:
        kwargs["issuer"] = settings.auth_jwt_issuer
    if settings.auth_jwt_audience:
        kwargs["audience"] = settings.auth_jwt_audience

    try:
        payload = jwt.decode(token, secret, **kwargs)
        return payload
    except (
        ExpiredSignatureError,
        ImmatureSignatureError,
        InvalidAlgorithmError,
        InvalidAudienceError,
        InvalidIssuerError,
        InvalidSignatureError,
        DecodeError,
        InvalidTokenError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


class InMemoryLoginRateLimiter:
    """Thread-safe bounded in-memory login attempt limiter.

    Deployment Scope Notice:
    This rate limiter operates in process memory for the current worker.
    It does not share state across multiple processes or distributed cluster nodes.
    For horizontal multi-worker/multi-container deployments, a distributed store
    (such as Redis) is required to enforce global rate limits.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 60,
        max_tracked_keys: int = 10000,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_tracked_keys = max_tracked_keys
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _cleanup_unlocked(self, now: float) -> None:
        """Purge expired timestamps and stale keys while holding the lock."""
        cutoff = now - self.window_seconds
        keys_to_remove = []
        for key, timestamps in self._failures.items():
            valid_ts = [ts for ts in timestamps if ts > cutoff]
            if valid_ts:
                self._failures[key] = valid_ts
            else:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            self._failures.pop(key, None)

        # Evict oldest keys if table capacity is reached
        if len(self._failures) > self.max_tracked_keys:
            sorted_keys = sorted(
                self._failures.keys(),
                key=lambda k: self._failures[k][-1] if self._failures[k] else 0,
            )
            for k in sorted_keys[: len(self._failures) - self.max_tracked_keys]:
                self._failures.pop(k, None)

    def check_rate_limit(self, key: str) -> None:
        """Check if the given key has exceeded the maximum allowed failed attempts."""
        now = datetime.now(UTC).timestamp()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._failures.get(key, [])
            recent = [ts for ts in timestamps if ts > cutoff]
            if len(recent) >= self.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Please try again later.",
                )

    def record_failure(self, key: str) -> None:
        """Record a failed login attempt for the key."""
        now = datetime.now(UTC).timestamp()
        with self._lock:
            self._cleanup_unlocked(now)
            self._failures[key].append(now)

    def reset(self, key: str) -> None:
        """Reset failures for the key upon a successful login."""
        with self._lock:
            self._failures.pop(key, None)


login_rate_limiter = InMemoryLoginRateLimiter()
