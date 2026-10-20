from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import Settings
from .database import get_db
from .models import User
from .permissions import permissions_for
from .security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def _unauthorized(msg: str = "Sign in to continue.") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, msg, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings_dep),
    db: Session = Depends(get_db),
) -> User:
    """Verifies the token, then loads the user so a suspension or role change applies immediately."""
    if creds is None:
        raise _unauthorized()
    try:
        claims = decode_access_token(settings, creds.credentials)
    except jwt.PyJWTError:
        raise _unauthorized("Your session is not valid. Sign in again.") from None
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise _unauthorized("Your session is not valid. Sign in again.")
    return user


def require_permission(permission: str) -> Callable[[User], User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if permission not in permissions_for(user.role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to do this.")
        return user

    return checker
