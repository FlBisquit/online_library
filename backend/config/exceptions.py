"""Глобальные обработчики исключений DRF."""
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

UNIQUE_VIOLATION_CODES = {1062, 23505}  # MySQL, PostgreSQL
UNIQUE_VIOLATION_MARKERS = (
    "duplicate entry",
    "unique constraint",
    "unique violation",
)


def _is_unique_violation(exc):
    """Отличить гонку за уникальную запись от других ошибок целостности."""
    cause = exc.__cause__ or exc
    codes = [getattr(cause, "code", None), getattr(cause, "pgcode", None)]
    codes.extend(arg for arg in getattr(cause, "args", ()) if isinstance(arg, int))
    for code in codes:
        try:
            if int(code) in UNIQUE_VIOLATION_CODES:
                return True
        except (TypeError, ValueError):
            continue
    message = str(cause).lower()
    return any(marker in message for marker in UNIQUE_VIOLATION_MARKERS)


def api_exception_handler(exc, context):
    """Только уникальные конфликты превращаются в 409."""
    if isinstance(exc, IntegrityError) and _is_unique_violation(exc):
        return Response(
            {
                "detail": "Конфликт при сохранении: запись уже существует или изменена параллельным запросом."
            },
            status=status.HTTP_409_CONFLICT,
        )
    return exception_handler(exc, context)
