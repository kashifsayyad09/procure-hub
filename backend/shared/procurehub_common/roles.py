from enum import StrEnum


class Role(StrEnum):
    # Same identifiers the frontend uses in src/types/roles.ts
    EMPLOYEE = "employee"
    MANAGER = "manager"
    PROCUREMENT = "procurement"
    VENDOR = "vendor"
    FINANCE = "finance"
    ADMIN = "admin"
