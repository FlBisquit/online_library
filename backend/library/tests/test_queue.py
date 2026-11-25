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


class WaitingQueueTests(LibraryTestCase):
    def test_reader_joins_queue(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        self.client.force_authenticate(self.reader)
        response = self.client.post(
            f"/api/books/{self.book.id}/queue/",
            {"reader_id": self.reader.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reservation = models.Reservation.objects.get()
        self.assertEqual(reservation.status, models.Reservation.Status.PENDING)
        self.assertEqual(reservation.active_slot, 1)

    def test_duplicate_queue_entry_returns_409(self):
        reservation = models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=models.Reservation.Status.PENDING,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=48),
        )
        self.client.force_authenticate(self.reader)
        response = self.client.post(
            f"/api/books/{self.book.id}/queue/",
            {"reader_id": self.reader.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_queue_position(self):
        reservation = models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=models.Reservation.Status.PENDING,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=48),
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.get(f"/api/books/{self.book.id}/queue/{self.reader.id}/position/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["position"], 1)


class QueueBehaviorTests(LibraryTestCase):
    """Регрессионные тесты очереди и бронирования."""

    def _make_copy_unavailable(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])

    def _reservation(self, reader, status, copy=None, offset=0):
        now = timezone.now() + timedelta(seconds=offset)
        return models.Reservation.objects.create(
            reader=reader,
            book=self.book,
            status=status,
            copy=copy,
            queue_date=now,
            expires_at=now + timedelta(hours=48),
            active_slot=1 if status in (
                models.Reservation.Status.PENDING,
                models.Reservation.Status.ACTIVE,
            ) else None,
        )

    def test_queue_list_reader_sees_only_own_position_and_total(self):
        self._make_copy_unavailable()
        self._reservation(self.reader, models.Reservation.Status.PENDING)
        self._reservation(self.other_reader, models.Reservation.Status.PENDING, offset=1)

        self.client.force_authenticate(self.reader)
        response = self.client.get(f"/api/books/{self.book.id}/queue/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["position"], 1)
        self.assertEqual(response.data["total"], 2)
        self.assertNotIn("reader2@test.local", str(response.data))

        self.client.force_authenticate(self.librarian)
        staff_response = self.client.get(f"/api/books/{self.book.id}/queue/")
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)
        self.assertEqual(staff_response.data["total"], 2)
        self.assertEqual([row["position"] for row in staff_response.data["results"]], [1, 2])

    def test_staff_reservations_waiting_list_includes_position(self):
        self._make_copy_unavailable()
        self._reservation(self.reader, models.Reservation.Status.ACTIVE, copy=self.copy)
        self._reservation(self.other_reader, models.Reservation.Status.PENDING, offset=1)

        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reservations/", {"status": "ACTIVE"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], models.Reservation.Status.ACTIVE)
        self.assertEqual(response.data["results"][0]["position"], 1)
        self.assertEqual(response.data["results"][0]["book"]["title"], self.book.title)
        self.assertEqual(response.data["results"][0]["copy"]["inventory_number"], "INV-1")
        self.assertEqual(
            response.data["results"][0]["reader"]["full_name"],
            self.reader.full_name,
        )

    def test_me_reservations_returns_own_reservation_with_position(self):
        self._make_copy_unavailable()
        self._reservation(self.reader, models.Reservation.Status.PENDING)

        self.client.force_authenticate(self.reader)
        response = self.client.get("/api/auth/me/reservations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["book"]["title"], self.book.title)
        self.assertEqual(response.data[0]["position"], 1)
        self.assertIsNotNone(response.data[0]["expires_at"])

    def test_join_queue_missing_book_returns_404(self):
        self._make_copy_unavailable()
        self.client.force_authenticate(self.reader)
        response = self.client.post(
            "/api/books/9999/queue/", {"reader_id": self.reader.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_join_queue_with_available_copy_returns_409(self):
        self.client.force_authenticate(self.reader)
        response = self.client.post(
            f"/api/books/{self.book.id}/queue/", {"reader_id": self.reader.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("свободн", response.data["detail"].lower())
        self.assertEqual(models.Reservation.objects.count(), 0)

    def test_join_cancel_cycle_can_repeat_five_times(self):
        self._make_copy_unavailable()
        self.client.force_authenticate(self.reader)
        for _ in range(5):
            join = self.client.post(
                f"/api/books/{self.book.id}/queue/", {"reader_id": self.reader.id}, format="json"
            )
            self.assertEqual(join.status_code, status.HTTP_201_CREATED)
            cancel = self.client.post(
                f"/api/reservations/{join.data['id']}/cancel/", {}, format="json"
            )
            self.assertEqual(cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(
            models.Reservation.objects.filter(status=models.Reservation.Status.CANCELLED).count(),
            5,
        )

    def test_return_reserves_copy_for_first_in_queue_then_fulfils(self):
        holder = models.Reader.objects.create_user(
            email="holder@test.local", password="HolderPass123", full_name="Держатель"
        )
        holder.groups.add(_ensure_group(roles.READER_ROLE))
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        issue = models.Issue.objects.create(
            reader=holder,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        first = self._reservation(self.reader, models.Reservation.Status.PENDING)
        second = self._reservation(self.other_reader, models.Reservation.Status.PENDING, offset=1)

        self.client.force_authenticate(self.librarian)
        returned = self.client.post(f"/api/issues/{issue.id}/return/", {}, format="json")
        self.assertEqual(returned.status_code, status.HTTP_200_OK)

        self.copy.refresh_from_db()
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.RESERVED)
        self.assertEqual(first.status, models.Reservation.Status.ACTIVE)
        self.assertEqual(first.copy_id, self.copy.id)
        self.assertEqual(second.status, models.Reservation.Status.PENDING)

        denied = self.client.post(
            "/api/issues/",
            {"reader_id": self.other_reader.id, "copy_id": self.copy.id},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_409_CONFLICT)

        granted = self.client.post(
            "/api/issues/",
            {"reader_id": self.reader.id, "copy_id": self.copy.id},
            format="json",
        )
        self.assertEqual(granted.status_code, status.HTTP_201_CREATED)
        first.refresh_from_db()
        self.copy.refresh_from_db()
        self.assertEqual(first.status, models.Reservation.Status.FULFILLED)
        self.assertIsNone(first.active_slot)
        self.assertEqual(self.copy.status, models.BookCopy.Status.ISSUED)

    def test_cancel_active_reservation_frees_only_its_own_copy(self):
        other_copy = models.BookCopy.objects.create(
            book=self.book, inventory_number="INV-2", status=models.BookCopy.Status.RESERVED
        )
        self.copy.status = models.BookCopy.Status.RESERVED
        self.copy.save(update_fields=["status"])
        reservation = self._reservation(
            self.reader, models.Reservation.Status.ACTIVE, copy=self.copy
        )

        self.client.force_authenticate(self.reader)
        response = self.client.post(
            f"/api/reservations/{reservation.id}/cancel/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.copy.refresh_from_db()
        other_copy.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.AVAILABLE)
        self.assertEqual(other_copy.status, models.BookCopy.Status.RESERVED)

    def test_cancelling_foreign_reservation_returns_403(self):
        reservation = self._reservation(self.reader, models.Reservation.Status.PENDING)
        self.client.force_authenticate(self.other_reader)
        response = self.client.post(
            f"/api/reservations/{reservation.id}/cancel/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        detail = self.client.get(f"/api/reservations/{reservation.id}/")
        self.assertEqual(detail.status_code, status.HTTP_403_FORBIDDEN)

    def test_integrity_error_handler_returns_409(self):
        from django.db import IntegrityError

        from config.exceptions import api_exception_handler

        response = api_exception_handler(IntegrityError("duplicate"), {})
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_reader_cannot_query_other_reader_queue_position(self):
        self._make_copy_unavailable()
        self._reservation(self.other_reader, models.Reservation.Status.PENDING)
        self.client.force_authenticate(self.reader)
        response = self.client.get(
            f"/api/books/{self.book.id}/queue/{self.other_reader.id}/position/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reader_cannot_view_other_reader_reservation(self):
        reservation = self._reservation(self.other_reader, models.Reservation.Status.PENDING)
        self.client.force_authenticate(self.reader)
        response = self.client.get(f"/api/reservations/{reservation.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
