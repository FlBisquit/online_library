"""Management command для отметки просроченных выдач (cron)."""
from django.core.management.base import BaseCommand

from library import services


class Command(BaseCommand):
    help = "Mark issued books with a past due date as OVERDUE."

    def handle(self, *args, **options):
        processed = services.mark_overdue()
        self.stdout.write(
            self.style.SUCCESS(f"Overdue issues processed: {len(processed)}")
        )
