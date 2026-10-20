import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..config import Settings
from ..database import get_db
from ..deps import get_current_user, get_settings_dep
from ..models import RefreshToken, User, later, new_id, utcnow
from ..permissions import permissions_for
from ..schemas import ChangePasswordRequest, LoginRequest, SessionUser, TokenResponse, UserOut
from ..security import (
    DUMMY_HASH,
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    password_policy_errors,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
log = logging.getLogger("auth")

BAD_LOGIN = "Incorrect email or password."
COOKIE_PATH = "/api/v1/auth"


def _session_user(user: User) -> SessionUser:
    return SessionUser(**UserOut.model_validate(user).model_dump(), permissions=permissions_for(user.role))


def _set_cookie(response: Response, settings: Settings, raw: str) -> None:
    response.set_cookie(
        settings.cookie_name, raw,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True, secure=settings.cookie_secure, samesite="strict", path=COOKIE_PATH,
    )


def _clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.cookie_name, path=COOKIE_PATH, httponly=True, secure=settings.cookie_secure, samesite="strict")


def _issue(db: Session, settings: Settings, user: User, request: Request, response: Response, family_id: str | None = None) -> tuple[TokenResponse, RefreshToken]:
    raw, digest = new_refresh_token()
    row = RefreshToken(
        id=new_id(), user_id=user.id, family_id=family_id or new_id(), token_hash=digest,
        expires_at=later(days=settings.refresh_token_ttl_days),
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
    )
    db.add(row)
    access, ttl = create_access_token(settings, user)
    _set_cookie(response, settings, raw)
    return TokenResponse(access_token=access, expires_in=ttl, user=_session_user(user)), row


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow()))


def revoke_all_for_user(db: Session, user_id: str) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=utcnow()))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    email = body.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(body.password, DUMMY_HASH)  # equalise timing
        log.info("login_failed", extra={"event": "login_failed", "reason": "unknown_email"})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_LOGIN)

    now = utcnow()
    if user.locked_until and user.locked_until > now:
        retry = int((user.locked_until - now).total_seconds()) + 1
        log.warning("login_blocked", extra={"event": "login_blocked", "user_id": user.id})
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again later.", headers={"Retry-After": str(retry)})

    if not verify_password(body.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_attempts = 0
            log.warning("account_locked", extra={"event": "account_locked", "user_id": user.id})
        db.commit()
        log.info("login_failed", extra={"event": "login_failed", "reason": "bad_password", "user_id": user.id})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_LOGIN)

    if not user.is_active:  # password was correct, so naming the reason leaks nothing
        log.info("login_failed", extra={"event": "login_failed", "reason": "suspended", "user_id": user.id})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is suspended. Contact your administrator.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    result, _ = _issue(db, settings, user, request, response)
    db.commit()
    log.info("login_succeeded", extra={"event": "login_succeeded", "user_id": user.id, "role": user.role})
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    def deny(reason: str) -> JSONResponse:
        log.info("refresh_denied", extra={"event": "refresh_denied", "reason": reason})
        out = JSONResponse({"detail": "Your session has ended. Sign in again."}, status_code=status.HTTP_401_UNAUTHORIZED)
        _clear_cookie(out, settings)
        return out

    raw = request.cookies.get(settings.cookie_name)
    if not raw:
        return deny("no_cookie")
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    if token is None:
        return deny("unknown_token")
    now = utcnow()
    if token.revoked_at is not None:
        # A rotated token coming back means two parties hold it. A near-simultaneous retry (two tabs) is tolerated;
        # a late replay is treated as theft and the whole family is revoked.
        if token.replaced_by and now - token.revoked_at <= timedelta(seconds=settings.refresh_reuse_grace_seconds):
            return deny("concurrent_rotation")
        _revoke_family(db, token.family_id)
        db.commit()
        log.warning("refresh_reuse_detected", extra={"event": "refresh_reuse_detected", "user_id": token.user_id})
        return deny("reuse")
    if token.expires_at <= now:
        return deny("expired")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        return deny("inactive_user")

    result, new_row = _issue(db, settings, user, request, response, family_id=token.family_id)
    token.revoked_at = now
    token.replaced_by = new_row.id
    db.commit()
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    raw = request.cookies.get(settings.cookie_name)
    if raw:
        token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
        if token:
            _revoke_family(db, token.family_id)
            db.commit()
            log.info("logout", extra={"event": "logout", "user_id": token.user_id})
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(out, settings)
    return out


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    revoke_all_for_user(db, user.id)
    db.commit()
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(out, settings)
    return out


@router.get("/me", response_model=SessionUser)
def me(user: User = Depends(get_current_user)):
    return _session_user(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(body: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Your current password is incorrect.")
    problems = password_policy_errors(body.new_password, user.email)
    if problems:
        raise HTTPException(422, problems)
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    revoke_all_for_user(db, user.id)  # every device must sign in again
    db.commit()
    log.info("password_changed", extra={"event": "password_changed", "user_id": user.id})
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_cookie(out, settings)
    return out
