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


class IssueTests(LibraryTestCase):
    def test_issue_successful(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/api/issues/",
            {"reader_id": self.reader.id, "copy_id": self.copy.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.ISSUED)
        issue = models.Issue.objects.get()
        self.assertEqual(issue.reader, self.reader)
        self.assertEqual(issue.status, models.Issue.Status.ISSUED)
        self.assertAlmostEqual(
            (issue.due_at - issue.issued_at).total_seconds(),
            14 * 24 * 60 * 60,
            places=0,
        )

    def test_issue_already_issued_copy_returns_409(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/api/issues/",
            {"reader_id": self.other_reader.id, "copy_id": self.copy.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_issue_by_reader_forbidden(self):
        self.client.force_authenticate(self.reader)
        response = self.client.post(
            "/api/issues/",
            {"reader_id": self.other_reader.id, "copy_id": self.copy.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_issue_unknown_copy_returns_404(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/api/issues/",
            {"reader_id": self.reader.id, "copy_id": 99999},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_issue_serializer_returns_nested_book_reader_and_copy(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/api/issues/",
            {"reader_id": self.reader.id, "copy_id": self.copy.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["book"]["id"], self.book.id)
        self.assertEqual(response.data["book"]["title"], "Тестовая книга")
        self.assertEqual(response.data["reader"]["id"], self.reader.id)
        self.assertEqual(response.data["reader"]["full_name"], "Читатель Читалов")
        self.assertEqual(response.data["copy"]["inventory_number"], "INV-1")

    def test_issue_list_due_overdue_and_search_filters(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now() - timedelta(days=30),
            due_at=timezone.now() - timedelta(days=16),
            status=models.Issue.Status.ISSUED,
        )
        other_copy = models.BookCopy.objects.create(
            book=self.book, inventory_number="INV-2", status=models.BookCopy.Status.ISSUED
        )
        models.Issue.objects.create(
            reader=self.other_reader,
            copy=other_copy,
            issued_at=timezone.now() - timedelta(days=30),
            due_at=timezone.now() - timedelta(days=16),
            status=models.Issue.Status.ISSUED,
        )
        future_copy = models.BookCopy.objects.create(
            book=self.book, inventory_number="INV-3", status=models.BookCopy.Status.ISSUED
        )
        models.Issue.objects.create(
            reader=self.reader,
            copy=future_copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.BookCopy.Status.ISSUED,
        )

        self.client.force_authenticate(self.librarian)
        overdue = self.client.get("/api/issues/", {"due": "overdue"})
        self.assertEqual(overdue.status_code, status.HTTP_200_OK)
        self.assertEqual(len(overdue.data["results"]), 2)

        found = self.client.get("/api/issues/", {"search": "Второй Читатель"})
        self.assertEqual(found.status_code, status.HTTP_200_OK)
        self.assertEqual(len(found.data["results"]), 1)

    def test_return_issue_successful(self):
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.post(f"/api/issues/{issue.id}/return/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        issue.refresh_from_db()
        self.assertEqual(issue.status, models.Issue.Status.RETURNED)
        self.assertIsNotNone(issue.returned_at)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.AVAILABLE)

    def test_return_issue_locks_reservation_before_issue(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        reservation = models.Reservation.objects.create(
            reader=self.other_reader,
            book=self.book,
            status=models.Reservation.Status.PENDING,
            queue_date=timezone.now(),
            active_slot=1,
        )
        with CaptureQueriesContext(connection) as captured:
            services.return_issue(issue.id, user=self.librarian)

        queries = [query["sql"] for query in captured.captured_queries]
        reservation_lock = next(
            index
            for index, sql in enumerate(queries)
            if "library_reservation" in sql and "FOR UPDATE" in sql
        )
        issue_lock = next(
            index
            for index, sql in enumerate(queries)
            if "library_issue" in sql and "FOR UPDATE" in sql
        )
        self.assertLess(reservation_lock, issue_lock)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, models.Reservation.Status.ACTIVE)

    def test_return_twice_returns_409(self):
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        self.client.force_authenticate(self.librarian)
        first = self.client.post(f"/api/issues/{issue.id}/return/", {}, format="json")
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.client.post(f"/api/issues/{issue.id}/return/", {}, format="json")
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)

    def test_issue_with_malformed_ids_returns_400(self):
        self.client.force_authenticate(self.librarian)
        for payload in (
            {"reader_id": self.reader.id, "copy_id": "not-a-number"},
            {"reader_id": "not-a-number", "copy_id": self.copy.id},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/issues/", payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
