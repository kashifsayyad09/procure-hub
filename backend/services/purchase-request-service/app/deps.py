from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from procurehub_common.permissions import has_permission
from procurehub_common.tokens import TokenClaims, verify_access_token

from .config import Settings

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_principal(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), settings: Settings = Depends(get_settings_dep)) -> TokenClaims:
    """Verifies the signed token. The role comes from the token, so a role change reaches this service within the token lifetime (15 minutes)."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify_access_token(creds.credentials, secret=settings.jwt_secret.get_secret_value(), issuer=settings.jwt_issuer, audience=settings.jwt_audience)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session is not valid. Sign in again.", headers={"WWW-Authenticate": "Bearer"}) from None


def require_any_permission(*permissions: str) -> Callable[[TokenClaims], TokenClaims]:
    def checker(principal: TokenClaims = Depends(get_principal)) -> TokenClaims:
        if not any(has_permission(principal.role, p) for p in permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
        return principal

    return checker
