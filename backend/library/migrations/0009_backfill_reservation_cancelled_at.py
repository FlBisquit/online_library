from django.db import migrations
from django.db.models import F


def backfill_cancelled_at(apps, schema_editor):
    """Заполнить момент отмены у уже существующих отменённых броней.

    Исторического времени отмены нет, поэтому используем доступную отметку
    постановки в очередь как ближайшую верхнюю границу для старых записей.
    """
    Reservation = apps.get_model("library", "Reservation")
    Reservation.objects.filter(
        status="CANCELLED", cancelled_at__isnull=True
    ).update(cancelled_at=F("queue_date"))


class Migration(migrations.Migration):

    dependencies = [
        ("library", "0008_reservation_cancelled_at_issue_issue_issued_at_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_cancelled_at, migrations.RunPython.noop),
    ]
