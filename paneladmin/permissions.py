from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import UserRole


READ_ONLY_ROLES = {UserRole.ROLE_AUDYTOR}
ADMIN_PANEL_ROLES = {UserRole.ROLE_SUPERADMIN, UserRole.ROLE_ADMIN, UserRole.ROLE_AUDYTOR}
ADMIN_WRITE_ROLES = {UserRole.ROLE_SUPERADMIN, UserRole.ROLE_ADMIN}
FINANCE_WRITE_ROLES = {
    UserRole.ROLE_SUPERADMIN,
    UserRole.ROLE_ADMIN,
    UserRole.ROLE_KSIEGOWY,
    UserRole.ROLE_UZYTKOWNIK,
}
AUDIT_VIEW_ROLES = {UserRole.ROLE_SUPERADMIN, UserRole.ROLE_ADMIN, UserRole.ROLE_AUDYTOR}


def get_role_code(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "ANON"
    return getattr(getattr(user, "panel_role", None), "role", UserRole.ROLE_UZYTKOWNIK)


def is_read_only_role(user) -> bool:
    return get_role_code(user) in READ_ONLY_ROLES


def can_access_admin_panel(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_staff or get_role_code(user) in ADMIN_PANEL_ROLES)


def can_manage_admin_panel(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser or user.is_staff or get_role_code(user) in ADMIN_WRITE_ROLES)


def can_manage_finance_data(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return get_role_code(user) in FINANCE_WRITE_ROLES or bool(user.is_staff)


def can_view_audit(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_staff or get_role_code(user) in AUDIT_VIEW_ROLES)


ViewFunc = Callable[..., Any]


def admin_panel_required(view_func: ViewFunc) -> ViewFunc:
    @login_required(login_url="paneladmin_login")
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not can_access_admin_panel(request.user):
            raise PermissionDenied(
                "Dostęp do panelu administratora mają tylko użytkownicy z rolą administracyjną lub audytową."
            )
        return view_func(request, *args, **kwargs)

    return _wrapped  # type: ignore[return-value]


def admin_write_required(view_func: ViewFunc) -> ViewFunc:
    @admin_panel_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not can_manage_admin_panel(request.user):
            raise PermissionDenied(
                "Ta operacja wymaga roli administratora lub superadministratora."
            )
        return view_func(request, *args, **kwargs)

    return _wrapped  # type: ignore[return-value]


def finance_write_required(view_func: ViewFunc) -> ViewFunc:
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not can_manage_finance_data(request.user):
            raise PermissionDenied(
                "To konto ma dostęp tylko do odczytu. Skontaktuj się z administratorem, aby uzyskać możliwość edycji."
            )
        return view_func(request, *args, **kwargs)

    return _wrapped  # type: ignore[return-value]
