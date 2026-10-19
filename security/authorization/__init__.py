from .dangerous_permissions import DANGEROUS_PERMISSIONS, is_dangerous_role
from .hierarchy import is_privilege_escalation, is_owner_targeted

try:
    from .permission_guard import PermissionGuard
    from .role_guard import RoleGuard
except ImportError:
    PermissionGuard = None
    RoleGuard = None

__all__ = [
    "DANGEROUS_PERMISSIONS",
    "is_dangerous_role",
    "is_privilege_escalation",
    "is_owner_targeted",
    "PermissionGuard",
    "RoleGuard",
]
