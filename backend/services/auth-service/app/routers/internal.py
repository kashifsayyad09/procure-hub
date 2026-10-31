"""Internal API for other ProcureHub services. Not reachable through the public ingress; every call needs a service token."""
from fastapi import APIRouter, Depends, Query, Request
from procurehub_common.contracts.approval import ManagerRef
from procurehub_common.fastapi_support import service_caller
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Role, User


def _secret(request: Request) -> str | None:
    s = request.app.state.settings.internal_jwt_secret
    return s.get_secret_value() if s else None


router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)


@router.get("/users", response_model=list[ManagerRef])
def list_users_by_role(role: Role = Query(default=Role.MANAGER), _: str = Depends(service_caller(_secret, {"approval-service"})), db: Session = Depends(get_db)):
    """Active users with a role. The Approval service uses this to check who a delegation may go to."""
    rows = db.scalars(select(User).where(User.role == role.value, User.is_active.is_(True)).order_by(User.full_name).limit(200)).all()
    return [ManagerRef(id=u.id, full_name=u.full_name, email=u.email) for u in rows]
