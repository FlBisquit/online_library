"""Глобальные обработчики исключений DRF."""
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Превращает гонки за уникальные записи в 409 вместо 500."""
    if isinstance(exc, IntegrityError):
        return Response(
            {
                "detail": "Конфликт при сохранении: запись уже существует или изменена параллельным запросом."
            },
            status=status.HTTP_409_CONFLICT,
        )
    return exception_handler(exc, context)
