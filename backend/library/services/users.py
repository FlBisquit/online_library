"""Управление пользователями и ролями."""
from django.contrib.auth.models import Group
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from library import models, roles
from library.transitions import Conflict

ROLE_RANK = {
    roles.READER_ROLE: 0,
    roles.LIBRARIAN_ROLE: 1,
    roles.ADMIN_ROLE: 2,
}
ASSIGNABLE_ROLES = (roles.LIBRARIAN_ROLE, roles.ADMIN_ROLE)


def role_of(reader):
    """Основная роль пользователя (самая привилегированная при нескольких)."""
    names = set(reader.groups.values_list("name", flat=True)) & set(ROLE_RANK)
    if not names:
        return roles.READER_ROLE
    return max(names, key=lambda name: ROLE_RANK[name])


def _set_role(reader, role):
    group, _created = Group.objects.get_or_create(name=role)
    reader.groups.set([group])


def _log(actor, action, target, details=None, old_status=None, new_status=None):
    models.ActionLog.objects.create(
        user=actor,
        action=action,
        entity_type="Reader",
        entity_id=target.pk,
        old_status=old_status,
        new_status=new_status,
        details=details or {},
    )


def create_staff_user(*, actor, email, password, full_name, phone=None, role):
    """Создать сотрудника или администратора с явной ролью."""
    if role not in ASSIGNABLE_ROLES:
        raise ValidationError({"role": "Допустимые роли: librarian или admin."})
    with transaction.atomic():
        reader = models.Reader.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
        )
        _set_role(reader, role)
        _log(
            actor,
            "user.create",
            reader,
            {"target_user_id": reader.pk, "role": role},
        )
    return reader


def update_user(*, target_id, actor, role=None, status=None):
    """Изменить роль и/или статус пользователя с защитой себя и последнего админа."""
    with transaction.atomic():
        target = models.Reader.objects.select_for_update().filter(pk=target_id).first()
        if target is None:
            raise NotFound("Пользователь не найден.")
        old_role = role_of(target)
        old_status = target.status

        if role is not None and role not in ROLE_RANK:
            raise ValidationError({"role": "Неизвестная роль."})
        if status is not None and status not in (
            models.Reader.Status.ACTIVE,
            models.Reader.Status.BLOCKED,
        ):
            raise ValidationError({"status": "Допустимые статусы: ACTIVE или BLOCKED."})

        if target.pk == actor.pk:
            if role is not None and ROLE_RANK[role] < ROLE_RANK[old_role]:
                raise Conflict("Нельзя понизить свою роль.")
            if status == models.Reader.Status.BLOCKED and old_status != status:
                raise Conflict("Нельзя заблокировать самого себя.")

        losing_admin = old_role == roles.ADMIN_ROLE and (
            (role is not None and role != roles.ADMIN_ROLE)
            or (
                status == models.Reader.Status.BLOCKED
                and old_status != models.Reader.Status.BLOCKED
            )
        )
        if losing_admin:
            other_admins = (
                models.Reader.objects.filter(
                    groups__name=roles.ADMIN_ROLE,
                    status=models.Reader.Status.ACTIVE,
                )
                .exclude(pk=target.pk)
                .distinct()
                .count()
            )
            if other_admins == 0:
                raise Conflict(
                    "Нельзя понизить или заблокировать последнего администратора."
                )

        if role is not None and role != old_role:
            _set_role(target, role)
            _log(
                actor,
                "user.role_change",
                target,
                {"target_user_id": target.pk, "old_role": old_role, "new_role": role},
            )

        if status is not None and status != old_status:
            target.status = status
            target.save(update_fields=["status"])
            _log(
                actor,
                "user.status_change",
                target,
                {"target_user_id": target.pk},
                old_status=old_status,
                new_status=status,
            )

    return target
