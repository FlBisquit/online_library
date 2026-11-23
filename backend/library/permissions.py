"""DRF permission-классы для разграничения прав доступа по ролям."""
from rest_framework import permissions

from library import roles


class IsAdmin(permissions.BasePermission):
    """Доступ только для администраторов."""

    message = "Только администраторы могут выполнять это действие."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_role(roles.ADMIN_ROLE)
        )


class IsLibrarianOrAdmin(permissions.BasePermission):
    """Доступ для библиотекарей и администраторов."""

    message = "Доступ запрещён для этой роли."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.has_role(roles.LIBRARIAN_ROLE) or request.user.has_role(roles.ADMIN_ROLE))
        )


class IsCatalogEditor(IsLibrarianOrAdmin):
    """Изменять каталог могут библиотекарь и администратор."""

    message = "Изменять каталог могут только библиотекарь или администратор."
