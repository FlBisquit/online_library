import base64
import csv
import io
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status

from library import models, roles, services
from library.tests.base import LibraryTestCase, _ensure_group


class ReportsTests(LibraryTestCase):
    """Отчёт по книгам: выдачи, просрочки и отмены за период."""

    @staticmethod
    def _dt(year, month, day, hour=0, minute=0, second=0):
        return datetime(year, month, day, hour, minute, second, tzinfo=dt_timezone.utc)

    def setUp(self):
        super().setUp()
        self.period = {"date_from": "2026-11-01", "date_to": "2026-11-30"}
        self.empty_book = models.Book.objects.create(
            title="Книга без выдач", isbn="978-5-000-000-00-1"
        )
        self.other_book = models.Book.objects.create(
            title="Книга с отменами", isbn="978-5-000-000-00-2"
        )
        self.other_copy = models.BookCopy.objects.create(
            book=self.other_book, inventory_number="INV-REPORT-2"
        )

    def _issue(self, issued_at, status, copy=None):
        return models.Issue.objects.create(
            reader=self.reader,
            copy=copy or self.copy,
            issued_at=issued_at,
            due_at=issued_at + timedelta(days=14),
            status=status,
        )

    def _cancellation(self, book, queue_date, cancelled_at):
        return models.Reservation.objects.create(
            reader=self.reader,
            book=book,
            status=models.Reservation.Status.CANCELLED,
            queue_date=queue_date,
            cancelled_at=cancelled_at,
            active_slot=None,
        )

    def _seed_data(self):
        self._issue(self._dt(2026, 11, 1), models.Issue.Status.OVERDUE)
        self._issue(self._dt(2026, 11, 30, 23, 59, 59), models.Issue.Status.RETURNED)
        self._issue(self._dt(2026, 10, 31, 23, 59), models.Issue.Status.ISSUED)
        self._issue(self._dt(2026, 12, 1), models.Issue.Status.ISSUED)
        # Дата постановки в очередь вне периода, отмена — внутри: считать нужно.
        self._cancellation(
            self.book,
            self._dt(2026, 10, 1),
            self._dt(2026, 11, 15, 12),
        )
        # Дата постановки внутри периода, отмена — вне: в отчёт не попадает.
        self._cancellation(
            self.book,
            self._dt(2026, 11, 5),
            self._dt(2026, 12, 1),
        )
        self._cancellation(
            self.other_book,
            self._dt(2026, 11, 20),
            self._dt(2026, 11, 29, 18),
        )

    def _rows_by_title(self, response):
        return {row["title"]: row for row in response.data}

    def test_report_keeps_books_without_loans_and_aggregates_counts(self):
        self._seed_data()
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reports/books/", self.period)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = self._rows_by_title(response)

        self.assertEqual(rows["Тестовая книга"]["loans"], 2)
        self.assertEqual(rows["Тестовая книга"]["overdue"], 1)
        self.assertEqual(rows["Тестовая книга"]["cancellations"], 1)

        self.assertEqual(rows["Книга без выдач"]["loans"], 0)
        self.assertEqual(rows["Книга без выдач"]["overdue"], 0)
        self.assertEqual(rows["Книга без выдач"]["cancellations"], 0)

        self.assertEqual(rows["Книга с отменами"]["loans"], 0)
        self.assertEqual(rows["Книга с отменами"]["cancellations"], 1)

    def test_period_is_half_open_at_utc_boundaries(self):
        self._seed_data()
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reports/books/", self.period)
        rows = self._rows_by_title(response)
        # 2026-11-01 00:00 и 2026-11-30 23:59:59 попали, 31.10 и 01.12 — нет.
        self.assertEqual(rows["Тестовая книга"]["loans"], 2)

    def test_invalid_dates_return_400(self):
        self.client.force_authenticate(self.librarian)
        for params in [
            {"date_from": "not-a-date", "date_to": "2026-11-30"},
            {"date_from": "2026-11-01", "date_to": "2026-99-99"},
            {"date_from": "2026-11-30", "date_to": "2026-11-01"},
            {"date_to": "2026-11-30"},
            {"date_from": "9999-12-30", "date_to": "9999-12-31"},
        ]:
            with self.subTest(params=params):
                response = self.client.get("/api/reports/books/", params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reader_is_forbidden(self):
        self.client.force_authenticate(self.reader)
        response = self.client.get("/api/reports/books/", self.period)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_query_count_is_constant(self):
        self._seed_data()
        self.client.force_authenticate(self.librarian)
        # Проверка роли + один SQL-запрос с агрегацией по всем книгам.
        with self.assertNumQueries(2):
            response = self.client.get("/api/reports/books/", self.period)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def _parse_csv(self, response):
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_csv_matches_json_and_has_excel_headers(self):
        self._seed_data()
        self.client.force_authenticate(self.librarian)
        json_response = self.client.get("/api/reports/books/", self.period)
        csv_response = self.client.get("/api/reports/books/export/", self.period)

        self.assertEqual(csv_response.status_code, status.HTTP_200_OK)
        self.assertTrue(csv_response["Content-Type"].startswith("text/csv"))
        self.assertEqual(
            csv_response["Content-Disposition"],
            'attachment; filename="report_2026-11-01_2026-11-30.csv"',
        )
        rows = self._parse_csv(csv_response)
        self.assertEqual(rows[0], ["ID", "Книга", "Выдачи", "Просрочено", "Отмены"])
        expected = [
            [str(row["book_id"]), row["title"], str(row["loans"]), str(row["overdue"]), str(row["cancellations"])]
            for row in json_response.data
        ]
        self.assertEqual(rows[1:], expected)

    def test_csv_escapes_formula_prefixes(self):
        for index, title in enumerate(["=SUM(1+1)", "+CMD", "-CMD", "@SUM"]):
            models.Book.objects.create(title=title, isbn=f"978-5-900-000-00-{index}")
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reports/books/export/", self.period)
        rows = self._parse_csv(response)
        titles = {row[1]: row for row in rows[1:]}
        for dangerous in ["=SUM(1+1)", "+CMD", "-CMD", "@SUM"]:
            with self.subTest(title=dangerous):
                self.assertIn(f"'{dangerous}", titles)
                self.assertNotIn(dangerous, [row[1] for row in rows[1:]])

    def test_csv_escapes_formulas_hidden_by_leading_whitespace(self):
        dangerous_titles = ["\t=CMD", "\r@CMD", "\n+CMD", "  -CMD"]
        for index, title in enumerate(dangerous_titles):
            models.Book.objects.create(title=title, isbn=f"978-5-901-000-00-{index}")
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reports/books/export/", self.period)
        rows = self._parse_csv(response)
        titles = {row[1] for row in rows[1:]}
        for title in dangerous_titles:
            with self.subTest(title=repr(title)):
                self.assertIn(f"'{title}", titles)

    def test_export_reader_is_forbidden(self):
        self.client.force_authenticate(self.reader)
        response = self.client.get("/api/reports/books/export/", self.period)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_max_date_returns_400(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.get(
            "/api/reports/books/export/",
            {"date_from": "9999-12-30", "date_to": "9999-12-31"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_invalid_dates_return_400(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.get(
            "/api/reports/books/export/", {"date_from": "garbage", "date_to": "2026-11-30"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_old_report_endpoints_are_removed(self):
        self.client.force_authenticate(self.librarian)
        for path in [
            "/api/reports/issues/",
            "/api/reports/cancellations/",
            "/api/reports/issues/export/",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
