"""FastAPI dependencies for services that accept signed user access tokens (every service except the auth service,
which also looks the user up in its own database)."""
from collections.abc import Callable
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .permissions import has_permission
from .tokens import TokenClaims, verify_access_token

_bearer = HTTPBearer(auto_error=False)


def make_user_auth(get_settings: Callable[[Request], Any]):
    """`get_settings(request)` returns an object with jwt_secret (SecretStr), jwt_issuer and jwt_audience.
    Returns (get_principal, require_any_permission).

    The role comes from the signed token, so a role change reaches a service within the token lifetime (15 minutes)."""

    def get_principal(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> TokenClaims:
        if creds is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
        s = get_settings(request)
        try:
            return verify_access_token(creds.credentials, secret=s.jwt_secret.get_secret_value(), issuer=s.jwt_issuer, audience=s.jwt_audience)
        except jwt.PyJWTError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session is not valid. Sign in again.", headers={"WWW-Authenticate": "Bearer"}) from None

    def require_any_permission(*permissions: str) -> Callable[[TokenClaims], TokenClaims]:
        def checker(principal: TokenClaims = Depends(get_principal)) -> TokenClaims:
            if not any(has_permission(principal.role, p) for p in permissions):
                raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
            return principal

        return checker

    return get_principal, require_any_permission
