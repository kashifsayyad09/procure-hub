import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_permission
from ..models import Role, User
from ..permissions import permissions_for
from ..routers.auth import revoke_all_for_user
from ..schemas import UserCreate, UserOut, UserPage, UserUpdate
from ..security import hash_password, password_policy_errors

router = APIRouter(prefix="/api/v1/users", tags=["users"])
log = logging.getLogger("users")


@router.get("", response_model=UserPage)
def list_users(
    q: str | None = Query(default=None, max_length=100),
    role: Role | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("user:read")),
    db: Session = Depends(get_db),
):
    stmt = select(User)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.full_name).like(like)))
    if role:
        stmt = stmt.where(User.role == role.value)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(User.created_at.desc(), User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return UserPage(items=[UserOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, actor: User = Depends(require_permission("user:manage")), db: Session = Depends(get_db)):
    problems = password_policy_errors(body.password, body.email)
    if problems:
        raise HTTPException(422, problems)
    user = User(email=body.email.lower(), full_name=body.full_name, role=body.role.value, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.") from None
    log.info("user_created", extra={"event": "user_created", "actor_id": actor.id, "user_id": user.id, "role": user.role})
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: str, _: User = Depends(require_permission("user:read")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, actor: User = Depends(require_permission("user:manage")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    role_changed = body.role is not None and body.role.value != user.role
    suspending = body.is_active is False and user.is_active
    if role_changed and "role:assign" not in permissions_for(actor.role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to assign roles.")
    if user.id == actor.id and (role_changed or suspending):
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot change your own role or suspend your own account.")
    if body.full_name is not None:
        user.full_name = body.full_name.strip()
    if body.role is not None:
        user.role = body.role.value
    if body.is_active is not None:
        user.is_active = body.is_active
    if role_changed or suspending:
        revoke_all_for_user(db, user.id)  # force a fresh sign-in under the new state
    db.commit()
    log.info("user_updated", extra={"event": "user_updated", "actor_id": actor.id, "user_id": user.id, "fields": sorted(changes)})
    return user
