from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone

from library import models, roles
from library.tests.base import _ensure_group


class LoadDemoDataTests(TransactionTestCase):
    """Тесты management command load_demo_data."""

    def setUp(self):
        self.librarian_group = _ensure_group(roles.LIBRARIAN_ROLE)
        self.reader_group = _ensure_group(roles.READER_ROLE)
        self.admin_group = _ensure_group(roles.ADMIN_ROLE)

    def _load_demo_data(self):
        from django.core.management import call_command

        call_command("load_demo_data")

    # ---------- Базовая загрузка демо-набора ----------

    def test_demo_data_loads_catalog_with_covers(self):
        self._load_demo_data()
        self.assertEqual(models.Book.objects.count(), 24)
        self.assertEqual(models.Genre.objects.count(), 8)
        self.assertGreaterEqual(models.Author.objects.count(), 8)
        self.assertEqual(models.Book.objects.filter(cover_url__isnull=False).count(), 24)

    def test_demo_data_books_have_authors_and_genres(self):
        self._load_demo_data()
        for book in models.Book.objects.all():
            self.assertGreaterEqual(book.authors.count(), 1)
            self.assertLessEqual(book.authors.count(), 3)
            self.assertGreaterEqual(book.genres.count(), 1)
            self.assertLessEqual(book.genres.count(), 2)
            self.assertGreaterEqual(book.copies.count(), 1)
            self.assertLessEqual(book.copies.count(), 4)

    def test_demo_data_creates_issues_with_all_statuses(self):
        self._load_demo_data()
        issues = models.Issue.objects.all()
        self.assertGreaterEqual(issues.count(), 30)
        for status_value in (
            models.Issue.Status.RETURNED,
            models.Issue.Status.ISSUED,
            models.Issue.Status.OVERDUE,
            models.Issue.Status.LOST,
        ):
            self.assertTrue(issues.filter(status=status_value).exists())

    def test_demo_data_users_and_blocked_reader(self):
        self._load_demo_data()
        self.assertTrue(models.Reader.objects.filter(email="admin@library.local").exists())
        self.assertTrue(models.Reader.objects.filter(email="librarian@library.local").exists())
        for index in range(8):
            self.assertTrue(models.Reader.objects.filter(email=f"reader{index}@library.local").exists())
        blocked = models.Reader.objects.filter(email="reader7@library.local").first()
        self.assertEqual(blocked.status, models.Reader.Status.BLOCKED)

    # ---------- Идемпотентность ----------

    def test_demo_data_rerun_does_not_duplicate(self):
        self._load_demo_data()
        before = {
            "books": models.Book.objects.count(),
            "copies": models.BookCopy.objects.count(),
            "issues": models.Issue.objects.count(),
            "reservations": models.Reservation.objects.count(),
            "authors": models.Author.objects.count(),
            "genres": models.Genre.objects.count(),
            "readers": models.Reader.objects.count(),
        }
        self._load_demo_data()
        after = {
            "books": models.Book.objects.count(),
            "copies": models.BookCopy.objects.count(),
            "issues": models.Issue.objects.count(),
            "reservations": models.Reservation.objects.count(),
            "authors": models.Author.objects.count(),
            "genres": models.Genre.objects.count(),
            "readers": models.Reader.objects.count(),
        }
        self.assertEqual(before, after)

    # ---------- Инварианты консистентности ----------

    def test_demo_data_issued_copies_match_open_issues(self):
        self._load_demo_data()
        issued_copies = models.BookCopy.objects.filter(status=models.BookCopy.Status.ISSUED).count()
        open_issues = models.Issue.objects.filter(
            status__in=[models.Issue.Status.ISSUED, models.Issue.Status.OVERDUE],
        ).count()
        self.assertEqual(issued_copies, open_issues)

    def test_demo_data_reserved_copy_has_active_reservation(self):
        self._load_demo_data()
        reserved_copies = models.BookCopy.objects.filter(status=models.BookCopy.Status.RESERVED)
        self.assertTrue(reserved_copies.exists())
        for copy in reserved_copies:
            self.assertTrue(
                models.Reservation.objects.filter(
                    copy=copy,
                    status=models.Reservation.Status.ACTIVE,
                    active_slot=1,
                ).exists(),
            )

    # ---------- Сценарий очереди ----------

    def test_demo_data_queue_scenario(self):
        self._load_demo_data()
        book = models.Book.objects.get(title="451 градус по Фаренгейту")
        self.assertEqual(book.copies.count(), 2)
        self.assertEqual(
            book.copies.filter(status=models.BookCopy.Status.ISSUED).count(),
            book.copies.count(),
        )
        queue_reservations = models.Reservation.objects.filter(
            book=book,
            status=models.Reservation.Status.PENDING,
        )
        self.assertEqual(queue_reservations.count(), 3)

        reserved_book = models.Book.objects.get(title="Мастер и Маргарита")
        reserved_copies = reserved_book.copies.filter(status=models.BookCopy.Status.RESERVED)
        self.assertEqual(reserved_copies.count(), 1)
        reservation = models.Reservation.objects.filter(
            book=reserved_book,
            status=models.Reservation.Status.ACTIVE,
            copy__isnull=False,
        )
        self.assertEqual(reservation.count(), 1)
        self.assertEqual(reservation.first().reader.email, "reader0@library.local")

    def test_demo_data_reset_clears_and_reloads(self):
        self._load_demo_data()
        models.BookCopy.objects.create(
            book=models.Book.objects.first(),
            inventory_number="STRAY-COPY-1",
            status=models.BookCopy.Status.AVAILABLE,
        )
        from django.core.management import call_command

        call_command("load_demo_data", reset=True)
        self.assertEqual(models.BookCopy.objects.filter(inventory_number="STRAY-COPY-1").count(), 0)
        self.assertEqual(models.Book.objects.count(), 24)

    def test_demo_data_cancelled_and_expired_reservations_dates(self):
        from django.core.management import call_command

        call_command("load_demo_data")
        cancelled = models.Reservation.objects.filter(status=models.Reservation.Status.CANCELLED).first()
        self.assertIsNotNone(cancelled)
        self.assertNotEqual(cancelled.cancelled_at, None)
        self.assertGreater(
            timezone.now() - cancelled.cancelled_at,
            timedelta(days=20),
        )
        expired = models.Reservation.objects.filter(status=models.Reservation.Status.EXPIRED).first()
        self.assertIsNotNone(expired)
        self.assertNotEqual(expired.expires_at, None)
        self.assertLess(expired.expires_at, timezone.now())
