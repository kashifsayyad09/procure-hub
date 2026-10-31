"""Service-to-service tokens. Separate secret, audience and token type from user tokens, so a user token can never
call an internal endpoint and a service token can never act as a user."""
import uuid
from collections.abc import Collection
from datetime import UTC, datetime, timedelta

import jwt

INTERNAL_AUDIENCE = "procurehub-internal"


def create_service_token(secret: str, service: str, *, ttl_seconds: int = 60) -> str:
    now = datetime.now(UTC)
    claims = {"iss": service, "sub": service, "aud": INTERNAL_AUDIENCE, "typ": "service", "jti": str(uuid.uuid4()),
              "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
    return jwt.encode(claims, secret, algorithm="HS256")


def verify_service_token(token: str, secret: str, allowed: Collection[str]) -> str:
    """Returns the calling service's name. Raises jwt.PyJWTError for anything invalid or from a service not in `allowed`."""
    claims = jwt.decode(token, secret, algorithms=["HS256"], audience=INTERNAL_AUDIENCE, options={"require": ["exp", "iat", "sub", "iss", "aud"]})
    if claims.get("typ") != "service":
        raise jwt.InvalidTokenError("not a service token")
    if claims["sub"] not in allowed or claims["iss"] != claims["sub"]:
        raise jwt.InvalidTokenError("service not allowed")
    return str(claims["sub"])
