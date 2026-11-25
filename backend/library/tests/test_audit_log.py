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


class ActionLogApiTests(LibraryTestCase):
    """Эндпоинт журнала действий: права, фильтры, формат и N+1."""

    def _log(self, **kwargs):
        defaults = {
            "user": self.librarian,
            "action": "issue.status_change",
            "entity_type": "Issue",
            "entity_id": 1,
            "old_status": models.Issue.Status.ISSUED,
            "new_status": models.Issue.Status.RETURNED,
            "details": {},
        }
        defaults.update(kwargs)
        return models.ActionLog.objects.create(**defaults)

    def test_reader_is_forbidden(self):
        self.client.force_authenticate(self.reader)
        response = self.client.get("/api/action-log/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_read_paginated_list_sorted_by_created_at(self):
        logs = [self._log(entity_id=i) for i in range(3)]
        for offset, log in enumerate(logs):
            models.ActionLog.objects.filter(pk=log.pk).update(
                created_at=timezone.now() + timedelta(minutes=offset)
            )
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/action-log/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(
            [row["id"] for row in response.data["results"]],
            [log.id for log in reversed(logs)],
        )

    def test_filters(self):
        first = self._log(
            user=self.librarian,
            action="issue.create",
            entity_type="Issue",
            entity_id=10,
        )
        second = self._log(
            user=self.admin,
            action="queue.join",
            entity_type="Reservation",
            entity_id=20,
        )
        self.client.force_authenticate(self.librarian)
        cases = [
            ({"user": self.librarian.id}, [first.id]),
            ({"entity_type": "Reservation"}, [second.id]),
            ({"entity_id": 20}, [second.id]),
            ({"action": "issue.create"}, [first.id]),
        ]
        for params, expected in cases:
            with self.subTest(params=params):
                response = self.client.get("/api/action-log/", params)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual([row["id"] for row in response.data["results"]], expected)

        models.ActionLog.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        yesterday = (timezone.now() - timedelta(days=1)).date().isoformat()
        old_date = (timezone.now() - timedelta(days=10)).date().isoformat()
        response = self.client.get("/api/action-log/", {"date_from": yesterday})
        self.assertEqual([row["id"] for row in response.data["results"]], [second.id])
        response = self.client.get("/api/action-log/", {"date_to": old_date})
        self.assertEqual([row["id"] for row in response.data["results"]], [first.id])

    def test_invalid_filters_return_400(self):
        self.client.force_authenticate(self.librarian)
        for params in [
            {"date_from": "not-a-date"},
            {"date_to": "2026-99-99"},
            {"user": "abc"},
            {"entity_id": "abc"},
        ]:
            with self.subTest(params=params):
                response = self.client.get("/api/action-log/", params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_serializer_shape_and_system_user(self):
        system = self._log(user=None, details={"reason": "cron"})
        user_log = self._log(user=self.librarian, entity_id=2)
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/action-log/")
        rows = {row["id"]: row for row in response.data["results"]}

        self.assertEqual(
            set(rows[system.id].keys()),
            {
                "id",
                "user",
                "action",
                "entity_type",
                "entity_id",
                "old_status",
                "new_status",
                "created_at",
                "details",
            },
        )
        self.assertIsNone(rows[system.id]["user"])
        self.assertEqual(rows[system.id]["details"], {"reason": "cron"})
        self.assertEqual(
            rows[user_log.id]["user"],
            {
                "id": self.librarian.id,
                "full_name": self.librarian.full_name,
                "email": self.librarian.email,
            },
        )

    def test_logs_after_issue_return_and_cancel(self):
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
        issue = services.issue_copy(self.reader.id, self.copy.id, user=self.librarian)
        services.return_issue(issue.id, user=self.librarian)
        waiting = models.Reservation.objects.create(
            reader=self.other_reader,
            book=self.book,
            status=models.Reservation.Status.PENDING,
            active_slot=1,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=48),
        )
        services.cancel_reservation(waiting.id, user=self.other_reader)

        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/action-log/")
        rows = {
            (row["entity_type"], row["entity_id"], row["old_status"], row["new_status"])
            for row in response.data["results"]
        }
        self.assertIn(
            (
                "Reservation",
                active.id,
                models.Reservation.Status.ACTIVE,
                models.Reservation.Status.FULFILLED,
            ),
            rows,
        )
        self.assertIn(
            (
                "Issue",
                issue.id,
                models.Issue.Status.ISSUED,
                models.Issue.Status.RETURNED,
            ),
            rows,
        )
        self.assertIn(
            (
                "Reservation",
                waiting.id,
                models.Reservation.Status.PENDING,
                models.Reservation.Status.CANCELLED,
            ),
            rows,
        )

    def test_no_n_plus_1_queries(self):
        for index in range(5):
            self._log(user=self.librarian, entity_id=index)
        self.client.force_authenticate(self.librarian)
        # Проверка роли + COUNT + SELECT с JOIN пользователя; без запросов на строку.
        with self.assertNumQueries(3):
            self.client.get("/api/action-log/")
