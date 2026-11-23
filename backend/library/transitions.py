"""Единая карта переходов статусов и транзакционное изменение статуса.

Все сервисные функции меняют статусы только через ``change_status``:
это гарантирует проверку допустимости перехода и запись ActionLog
со старым и новым статусом в той же транзакции.
"""
from django.db import transaction
from rest_framework.exceptions import APIException

from library import models


class Conflict(APIException):
    """Недопустимый переход или другой конфликт состояния."""

    status_code = 409
    default_detail = "Запрос конфликтует с текущим состоянием ресурса."


ISSUE_TRANSITIONS = {
    models.Issue.Status.ISSUED: {
        models.Issue.Status.RETURNED,
        models.Issue.Status.OVERDUE,
        models.Issue.Status.LOST,
    },
    models.Issue.Status.OVERDUE: {
        models.Issue.Status.RETURNED,
        models.Issue.Status.LOST,
    },
    models.Issue.Status.LOST: {
        models.Issue.Status.RETURNED,  # книга найдена
    },
    models.Issue.Status.RETURNED: set(),
}

RESERVATION_TRANSITIONS = {
    models.Reservation.Status.PENDING: {
        models.Reservation.Status.ACTIVE,
        models.Reservation.Status.CANCELLED,
    },
    models.Reservation.Status.ACTIVE: {
        models.Reservation.Status.FULFILLED,
        models.Reservation.Status.CANCELLED,
        models.Reservation.Status.EXPIRED,
    },
    models.Reservation.Status.FULFILLED: set(),
    models.Reservation.Status.CANCELLED: set(),
    models.Reservation.Status.EXPIRED: set(),
}

# ISSUED и RESERVED выставляются только сервисами (выдача и продвижение очереди),
# но не вручную через API.
BOOK_COPY_TRANSITIONS = {
    models.BookCopy.Status.AVAILABLE: {
        models.BookCopy.Status.ISSUED,
        models.BookCopy.Status.RESERVED,
        models.BookCopy.Status.LOST,
        models.BookCopy.Status.RETIRED,
    },
    models.BookCopy.Status.ISSUED: {
        models.BookCopy.Status.AVAILABLE,
        models.BookCopy.Status.LOST,
        models.BookCopy.Status.RETIRED,
    },
    models.BookCopy.Status.RESERVED: {
        models.BookCopy.Status.AVAILABLE,
        models.BookCopy.Status.ISSUED,
        models.BookCopy.Status.LOST,
        models.BookCopy.Status.RETIRED,
    },
    models.BookCopy.Status.LOST: {
        models.BookCopy.Status.AVAILABLE,  # книга найдена
        models.BookCopy.Status.RETIRED,
    },
    models.BookCopy.Status.RETIRED: set(),
}

_TRANSITIONS = {
    models.Issue: ISSUE_TRANSITIONS,
    models.Reservation: RESERVATION_TRANSITIONS,
    models.BookCopy: BOOK_COPY_TRANSITIONS,
}


def change_status(obj, new_status, user=None, **extra_fields):
    """Проверить переход, сохранить объект и записать ActionLog одной транзакцией."""
    old_status = obj.status
    transitions = _TRANSITIONS.get(type(obj))
    if transitions is None or new_status not in transitions.get(old_status, set()):
        raise Conflict(f"Переход из {old_status} в {new_status} нельзя.")

    entity_type = type(obj).__name__
    with transaction.atomic():
        obj.status = new_status
        for field, value in extra_fields.items():
            setattr(obj, field, value)
        obj.save()
        models.ActionLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            action=f"{entity_type.lower()}.status_change",
            entity_type=entity_type,
            entity_id=obj.pk,
            old_status=old_status,
            new_status=new_status,
            details={
                "model": entity_type,
                "entity_id": obj.pk,
                "old_status": old_status,
                "new_status": new_status,
            },
        )
    return obj
