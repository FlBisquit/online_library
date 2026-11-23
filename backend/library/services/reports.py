"""SQL-агрегации для отчётов библиотеки.

Все условия периода находятся внутри агрегатов: книги без выдач остаются
в выборке с нулевыми счётчиками, а подсчёт делается базой данных, не Python.
"""
from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.db.models import Count, Q

from library import models

CSV_HEADERS = ["ID", "Книга", "Выдачи", "Просрочено", "Отмены"]
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def safe_csv_value(value):
    """Значения, начинающиеся с формулы, экранируются апострофом для Excel."""
    text = "" if value is None else str(value)
    if text.startswith(CSV_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def write_books_report_csv(rows, writer):
    """Записать тот же отчёт, что отдаёт JSON, в CSV с русскими заголовками."""
    writer.writerow(CSV_HEADERS)
    for row in rows:
        writer.writerow(
            [
                safe_csv_value(row["id"]),
                safe_csv_value(row["title"]),
                safe_csv_value(row["loans"]),
                safe_csv_value(row["overdue"]),
                safe_csv_value(row["cancellations"]),
            ]
        )


def period_bounds(date_from, date_to):
    """Полуоткрытый интервал [дата_с, дата_по + 1 день) в UTC."""
    start = datetime.combine(date_from, time.min, tzinfo=dt_timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=dt_timezone.utc)
    return start, end


def books_report(date_from, date_to):
    """Один SQL-запрос: по каждой книге выдачи, просрочки и отмены за период."""
    start, end = period_bounds(date_from, date_to)
    issued_in_period = Q(
        copies__issues__issued_at__gte=start,
        copies__issues__issued_at__lt=end,
    )
    cancelled_in_period = Q(
        reservations__status=models.Reservation.Status.CANCELLED,
        reservations__cancelled_at__gte=start,
        reservations__cancelled_at__lt=end,
    )
    return (
        models.Book.objects.annotate(
            loans=Count(
                "copies__issues",
                filter=issued_in_period,
                distinct=True,
            ),
            overdue=Count(
                "copies__issues",
                filter=issued_in_period
                & Q(copies__issues__status=models.Issue.Status.OVERDUE),
                distinct=True,
            ),
            cancellations=Count(
                "reservations",
                filter=cancelled_in_period,
                distinct=True,
            ),
        )
        .values("id", "title", "loans", "overdue", "cancellations")
        .order_by("id")
    )
