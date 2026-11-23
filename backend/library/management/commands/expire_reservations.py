"""Management command для истечения просроченных резервов."""
from django.core.management.base import BaseCommand

from library import models, services


class Command(BaseCommand):
    help = "Expire overdue reservations and release reserved copies."

    def handle(self, *args, **options):
        expired = services.expire_reservations()
        self.stdout.write(
            self.style.SUCCESS(f"Expired reservations processed: {expired}")
        )
