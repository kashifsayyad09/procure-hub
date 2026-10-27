"""Access-token verification used by every service. The auth service issues the tokens."""
from dataclasses import dataclass

import jwt


def decode_access_token_claims(token: str, *, secret: str, issuer: str, audience: str) -> dict:
    """Raises jwt.PyJWTError for any invalid, expired or wrongly-scoped token. Only HS256 is accepted."""
    claims = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=audience,
        issuer=issuer,
        options={"require": ["exp", "iat", "sub", "iss", "aud"]},
    )
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("not an access token")
    return claims


@dataclass(frozen=True)
class TokenClaims:
    sub: str
    role: str
    name: str
    email: str


def verify_access_token(token: str, *, secret: str, issuer: str, audience: str) -> TokenClaims:
    c = decode_access_token_claims(token, secret=secret, issuer=issuer, audience=audience)
    return TokenClaims(sub=c["sub"], role=str(c.get("role", "")), name=str(c.get("name", "")), email=str(c.get("email", "")))
