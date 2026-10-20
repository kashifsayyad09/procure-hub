import hashlib
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import Settings
from .models import User

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters
# Verified against when the email is unknown so that response time does not reveal which emails exist.
DUMMY_HASH = _hasher.hash("not-a-real-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_policy_errors(password: str, email: str = "") -> list[str]:
    errors = []
    if len(password) < 12:
        errors.append("Use at least 12 characters.")
    if len(password) > 128:
        errors.append("Use at most 128 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errors.append("Include at least one letter and one number.")
    local = email.split("@")[0].lower()
    if local and len(local) >= 4 and local in password.lower():
        errors.append("Do not include your email name in the password.")
    return errors


# ---- access tokens (JWT, HS256) ----------------------------------------------------------------
def create_access_token(settings: Settings, user: User) -> tuple[str, int]:
    now = datetime.now(UTC)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    claims = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": user.id,
        "role": user.role,
        "typ": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    return token, int(ttl.total_seconds())


def decode_access_token(settings: Settings, token: str) -> dict:
    """Raises jwt.PyJWTError for any invalid, expired or wrongly-scoped token. Only HS256 is accepted."""
    claims = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
    )
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return claims


# ---- refresh tokens (opaque, random, stored hashed) ---------------------------------------------
def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
