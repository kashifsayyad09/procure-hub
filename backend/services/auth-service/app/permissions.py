"""Role -> permission matrix. The backend enforces these; hiding UI controls is not authorization.

Permissions for services that do not exist yet are declared now so every later service uses the
same names. Each service checks the permission it needs from the verified token's role.
"""
from .models import Role

PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.EMPLOYEE: frozenset({
        "purchase_request:create", "purchase_request:read_own", "purchase_request:submit",
        "document:upload", "notification:read", "si_talker:use",
    }),
    Role.MANAGER: frozenset({
        "approval:read", "approval:decide", "approval:delegate", "purchase_request:read_department",
        "spend:read_department", "notification:read", "si_talker:use",
    }),
    Role.PROCUREMENT: frozenset({
        "purchase_request:read_approved", "rfq:manage", "vendor:read", "quotation:compare",
        "purchase_order:create", "purchase_order:read", "analytics:read", "notification:read", "si_talker:use",
    }),
    Role.VENDOR: frozenset({
        "vendor_profile:manage", "rfq:read_invited", "quotation:submit", "purchase_order:read_assigned",
        "purchase_order:confirm", "invoice:submit", "notification:read",
    }),
    Role.FINANCE: frozenset({
        "invoice:read", "invoice:match", "payment:track", "receipt:read", "report:generate", "notification:read",
    }),
    Role.ADMIN: frozenset({
        "user:read", "user:manage", "role:assign", "audit:read", "settings:manage", "health:read", "notification:read",
    }),
}


def permissions_for(role: str) -> list[str]:
    try:
        return sorted(PERMISSIONS[Role(role)])
    except ValueError:
        return []
