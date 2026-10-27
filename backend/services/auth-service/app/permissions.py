"""Role -> permission matrix now lives in procurehub_common so every service uses the same one."""
from procurehub_common.permissions import PERMISSIONS, has_permission, permissions_for

__all__ = ["PERMISSIONS", "has_permission", "permissions_for"]
