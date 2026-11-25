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


class StatusTransitionTests(LibraryTestCase):
    """Единая карта переходов статусов и журнал с old_status/new_status."""

    inventory_counter = 0

    def _make_issue(self, status, due_at=None, returned_at=None):
        StatusTransitionTests.inventory_counter += 1
        copy = models.BookCopy.objects.create(
            book=self.book,
            inventory_number=f"TRANS-{StatusTransitionTests.inventory_counter}",
            status=models.BookCopy.Status.ISSUED,
        )
        return models.Issue.objects.create(
            reader=self.reader,
            copy=copy,
            issued_at=timezone.now() - timedelta(days=30),
            due_at=due_at or timezone.now() + timedelta(days=14),
            returned_at=returned_at,
            status=status,
        )

    def _make_reservation(self, status):
        return models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=status,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=48),
            active_slot=None,
        )

    def _make_copy(self, status):
        StatusTransitionTests.inventory_counter += 1
        return models.BookCopy.objects.create(
            book=self.book,
            inventory_number=f"TRANS-{StatusTransitionTests.inventory_counter}",
            status=status,
        )

    def _assert_matrix(self, model, enum, transition_map, factory, entity_type):
        for old_status in [item.value for item in enum]:
            for new_status in [item.value for item in enum]:
                with self.subTest(model=entity_type, old=old_status, new=new_status):
                    obj = factory(old_status)
                    logs_before = models.ActionLog.objects.count()
                    allowed = new_status in transition_map[old_status]

                    if allowed:
                        services.change_status(obj, new_status, user=self.librarian)
                        obj.refresh_from_db()
                        self.assertEqual(obj.status, new_status)
                        log = models.ActionLog.objects.get(
                            entity_type=entity_type, entity_id=obj.id
                        )
                        self.assertEqual(log.old_status, old_status)
                        self.assertEqual(log.new_status, new_status)
                        self.assertEqual(log.user, self.librarian)
                    else:
                        with self.assertRaises(services.Conflict) as ctx:
                            services.change_status(obj, new_status, user=self.librarian)
                        detail = str(ctx.exception.detail)
                        self.assertIn("из", detail)
                        self.assertIn("нельзя", detail)
                        obj.refresh_from_db()
                        self.assertEqual(obj.status, old_status)
                        self.assertEqual(models.ActionLog.objects.count(), logs_before)

    def test_issue_transition_matrix(self):
        from library import transitions

        self._assert_matrix(
            models.Issue,
            models.Issue.Status,
            transitions.ISSUE_TRANSITIONS,
            self._make_issue,
            "Issue",
        )

    def test_reservation_transition_matrix(self):
        from library import transitions

        self._assert_matrix(
            models.Reservation,
            models.Reservation.Status,
            transitions.RESERVATION_TRANSITIONS,
            self._make_reservation,
            "Reservation",
        )

    def test_copy_transition_matrix(self):
        from library import transitions

        self._assert_matrix(
            models.BookCopy,
            models.BookCopy.Status,
            transitions.BOOK_COPY_TRANSITIONS,
            self._make_copy,
            "BookCopy",
        )

    def test_status_and_log_roll_back_together(self):
        issue = self._make_issue(models.Issue.Status.ISSUED)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                services.change_status(
                    issue, models.Issue.Status.RETURNED, user=self.librarian
                )
                raise RuntimeError("failure after status change")
        issue.refresh_from_db()
        self.assertEqual(issue.status, models.Issue.Status.ISSUED)
        self.assertEqual(models.ActionLog.objects.count(), 0)

    def test_reader_cannot_return_issue(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        self.client.force_authenticate(self.reader)
        response = self.client.post(f"/api/issues/{issue.id}/return/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        issue.refresh_from_db()
        self.assertEqual(issue.status, models.Issue.Status.ISSUED)

    def test_mark_overdue_sets_status_and_logs_transition(self):
        overdue = self._make_issue(
            models.Issue.Status.ISSUED, due_at=timezone.now() - timedelta(days=1)
        )
        fresh = self._make_issue(
            models.Issue.Status.ISSUED, due_at=timezone.now() + timedelta(days=1)
        )

        processed = services.mark_overdue()

        self.assertEqual([item.id for item in processed], [overdue.id])
        overdue.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(overdue.status, models.Issue.Status.OVERDUE)
        self.assertEqual(fresh.status, models.Issue.Status.ISSUED)
        log = models.ActionLog.objects.get(entity_type="Issue", entity_id=overdue.id)
        self.assertEqual(log.old_status, models.Issue.Status.ISSUED)
        self.assertEqual(log.new_status, models.Issue.Status.OVERDUE)

    def test_issue_list_triggers_mark_overdue(self):
        issue = self._make_issue(
            models.Issue.Status.ISSUED, due_at=timezone.now() - timedelta(days=1)
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        issue.refresh_from_db()
        self.assertEqual(issue.status, models.Issue.Status.OVERDUE)

    def test_return_overdue_issue_is_allowed(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now() - timedelta(days=30),
            due_at=timezone.now() - timedelta(days=1),
            status=models.Issue.Status.OVERDUE,
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.post(f"/api/issues/{issue.id}/return/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        issue.refresh_from_db()
        self.copy.refresh_from_db()
        self.assertEqual(issue.status, models.Issue.Status.RETURNED)
        self.assertEqual(self.copy.status, models.BookCopy.Status.AVAILABLE)

    def test_mark_lost_endpoint_marks_issue_and_copy(self):
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
        response = self.client.post(f"/api/issues/{issue.id}/mark-lost/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        issue.refresh_from_db()
        self.copy.refresh_from_db()
        self.assertEqual(issue.status, models.Issue.Status.LOST)
        self.assertEqual(self.copy.status, models.BookCopy.Status.LOST)
        issue_log = models.ActionLog.objects.get(entity_type="Issue", entity_id=issue.id)
        copy_log = models.ActionLog.objects.get(entity_type="BookCopy", entity_id=self.copy.id)
        self.assertEqual(
            (issue_log.old_status, issue_log.new_status),
            (models.Issue.Status.ISSUED, models.Issue.Status.LOST),
        )
        self.assertEqual(
            (copy_log.old_status, copy_log.new_status),
            (models.BookCopy.Status.ISSUED, models.BookCopy.Status.LOST),
        )

    def test_reader_cannot_mark_issue_lost(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        self.client.force_authenticate(self.reader)
        response = self.client.post(f"/api/issues/{issue.id}/mark-lost/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        issue.refresh_from_db()
        self.assertEqual(issue.status, models.Issue.Status.ISSUED)

    def test_fulfilled_and_expired_transitions_write_status_logs(self):
        self.copy.status = models.BookCopy.Status.RESERVED
        self.copy.save(update_fields=["status"])
        active = models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            copy=self.copy,
            status=models.Reservation.Status.ACTIVE,
            active_slot=1,
            queue_date=timezone.now() - timedelta(hours=2),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        services.issue_copy(self.reader.id, self.copy.id, user=self.librarian)
        active.refresh_from_db()
        self.assertEqual(active.status, models.Reservation.Status.FULFILLED)
        fulfilled_log = models.ActionLog.objects.get(
            entity_type="Reservation", entity_id=active.id
        )
        self.assertEqual(fulfilled_log.old_status, models.Reservation.Status.ACTIVE)
        self.assertEqual(fulfilled_log.new_status, models.Reservation.Status.FULFILLED)

        expired = models.Reservation.objects.create(
            reader=self.other_reader,
            book=self.book,
            copy=self.copy,
            status=models.Reservation.Status.ACTIVE,
            active_slot=None,
            queue_date=timezone.now() - timedelta(hours=3),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        services.mark_overdue()
        services.expire_reservations(self.book.id)
        expired.refresh_from_db()
        self.assertEqual(expired.status, models.Reservation.Status.EXPIRED)
        expired_log = models.ActionLog.objects.get(
            entity_type="Reservation", entity_id=expired.id
        )
        self.assertEqual(expired_log.old_status, models.Reservation.Status.ACTIVE)
        self.assertEqual(expired_log.new_status, models.Reservation.Status.EXPIRED)


class CancellationTimestampTests(LibraryTestCase):
    """Момент отмены брони фиксируется в cancelled_at."""

    def _reservation(self, status):
        return models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=status,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=48),
            active_slot=None,
        )

    def test_change_status_sets_cancelled_at(self):
        reservation = self._reservation(models.Reservation.Status.PENDING)
        before = timezone.now()
        services.change_status(
            reservation, models.Reservation.Status.CANCELLED, user=self.librarian
        )
        reservation.refresh_from_db()
        self.assertIsNotNone(reservation.cancelled_at)
        self.assertGreaterEqual(reservation.cancelled_at, before)

    def test_other_transitions_leave_cancelled_at_empty(self):
        reservation = self._reservation(models.Reservation.Status.ACTIVE)
        services.change_status(
            reservation, models.Reservation.Status.FULFILLED, user=self.librarian
        )
        reservation.refresh_from_db()
        self.assertIsNone(reservation.cancelled_at)

    def test_cancel_service_sets_cancelled_at(self):
        reservation = self._reservation(models.Reservation.Status.PENDING)
        services.cancel_reservation(reservation.id, user=self.reader)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, models.Reservation.Status.CANCELLED)
        self.assertIsNotNone(reservation.cancelled_at)
