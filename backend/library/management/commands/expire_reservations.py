"""Management command для истечения просроченных резервов (cron)."""
from django.core.management.base import BaseCommand

from library import services


class Command(BaseCommand):
    help = "Expire overdue reservations and release reserved copies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--book-id",
            type=int,
            dest="book_id",
            default=None,
            help="Обработать только бронирования этой книги.",
        )

    def handle(self, *args, **options):
        expired = services.expire_reservations(options["book_id"])
        self.stdout.write(
            self.style.SUCCESS(f"Expired reservations processed: {len(expired)}")
        )
