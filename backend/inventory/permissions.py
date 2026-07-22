from rest_framework.permissions import BasePermission


def role_for(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return "ADMIN"
    profile = getattr(user, "inventory_profile", None)
    return profile.role if profile and profile.active else None


class IsInventoryUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and role_for(request.user))


class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        return role_for(request.user) == "ADMIN"


class RoleBasedPermission(IsInventoryUser):
    hidden_for_operator = {
        "UserViewSet",
        "StockAdjustmentViewSet",
        "SystemSettingViewSet",
        "AuditLogViewSet",
    }
    read_only_for_operator = {
        "CategoryViewSet",
        "SupplierViewSet",
        "ProductViewSet",
        "LotViewSet",
        "AlertViewSet",
        "MovementViewSet",
    }

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        role = role_for(request.user)
        if role == "ADMIN":
            return True
        view_name = view.__class__.__name__
        action = getattr(view, "action", None)
        if view_name in self.hidden_for_operator:
            return False
        if view_name in self.read_only_for_operator:
            return request.method in {"GET", "HEAD", "OPTIONS"}
        if action in {"destroy", "cancel", "conclude", "reverse", "refresh", "reset_password"}:
            return False
        return True
