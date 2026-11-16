"""Вспомогательные бизнес-константы библиотеки."""
from datetime import timedelta

# Стандартный срок выдачи книги читателем (в днях).
LOAN_PERIOD = timedelta(days=14)

# Срок действия резерва читателя в очереди ожидания (в часах).
RESERVATION_PERIOD = timedelta(hours=48)
