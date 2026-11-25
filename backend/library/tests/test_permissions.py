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


class UserManagementTests(LibraryTestCase):
    """Управление пользователями доступно только администраторам."""

    def _make_user(self, email, role=roles.READER_ROLE, status=None):
        reader = models.Reader.objects.create_user(
            email=email,
            password="ReaderPass123",
            full_name=email.split("@")[0],
            status=status or models.Reader.Status.ACTIVE,
        )
        reader.groups.add(_ensure_group(role))
        return reader

    def _patch(self, target, data, actor=None):
        self.client.force_authenticate(actor or self.admin)
        return self.client.patch(f"/api/users/{target.id}/", data, format="json")

    def test_role_matrix_for_users(self):
        for user in [self.reader, self.librarian]:
            self.client.force_authenticate(user)
            with self.subTest(user=user.email):
                self.assertEqual(self.client.get("/api/users/").status_code, 403)
                self.assertEqual(
                    self.client.post(
                        "/api/users/",
                        {
                            "email": f"new-{user.id}@test.local",
                            "password": "StrongPass123!",
                            "full_name": "Новый",
                            "role": "librarian",
                        },
                        format="json",
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.patch(
                        f"/api/users/{self.reader.id}/", {"status": "BLOCKED"}, format="json"
                    ).status_code,
                    403,
                )
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/users/").status_code, 200)

    def test_admin_can_create_staff_with_explicit_role(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/users/",
            {
                "email": "staff@test.local",
                "password": "StrongPass123!",
                "full_name": "Сотрудник",
                "role": "librarian",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        created = models.Reader.objects.get(email="staff@test.local")
        self.assertTrue(created.groups.filter(name=roles.LIBRARIAN_ROLE).exists())

        invalid = self.client.post(
            "/api/users/",
            {
                "email": "reader-new@test.local",
                "password": "StrongPass123!",
                "full_name": "Читатель",
                "role": "reader",
            },
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)

    def test_search_filters_and_limit(self):
        self._make_user("anna@test.local")
        self._make_user("boris@test.local", role=roles.LIBRARIAN_ROLE)
        self._make_user("victor@test.local", status=models.Reader.Status.BLOCKED)
        self.client.force_authenticate(self.admin)

        response = self.client.get("/api/users/", {"search": "anna"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["email"] for row in response.data["results"]], ["anna@test.local"])

        response = self.client.get("/api/users/", {"role": roles.LIBRARIAN_ROLE})
        emails = {row["email"] for row in response.data["results"]}
        self.assertIn("boris@test.local", emails)
        self.assertNotIn("anna@test.local", emails)

        response = self.client.get("/api/users/", {"status": models.Reader.Status.BLOCKED})
        self.assertEqual(response.data["count"], 1)

        response = self.client.get("/api/users/", {"limit": 2})
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["count"], 7)

    def test_role_change_takes_effect_immediately_and_is_logged(self):
        response = self._patch(self.other_reader, {"role": roles.LIBRARIAN_ROLE})
        self.assertEqual(response.status_code, 200)
        self.other_reader.refresh_from_db()
        self.assertTrue(self.other_reader.groups.filter(name=roles.LIBRARIAN_ROLE).exists())
        self.assertFalse(self.other_reader.groups.filter(name=roles.READER_ROLE).exists())

        self.client.force_authenticate(self.other_reader)
        created = self.client.post(
            "/api/books/",
            {"title": "После смены роли", "isbn": "978-5-999-000-00-1"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)

        log = models.ActionLog.objects.filter(
            action="user.role_change", entity_id=self.other_reader.id
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.details["old_role"], roles.READER_ROLE)
        self.assertEqual(log.details["new_role"], roles.LIBRARIAN_ROLE)

    def test_status_change_validates_and_is_logged(self):
        response = self._patch(self.reader, {"status": models.Reader.Status.BLOCKED})
        self.assertEqual(response.status_code, 200)
        self.reader.refresh_from_db()
        self.assertEqual(self.reader.status, models.Reader.Status.BLOCKED)
        log = models.ActionLog.objects.filter(
            action="user.status_change", entity_id=self.reader.id
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_status, models.Reader.Status.ACTIVE)
        self.assertEqual(log.new_status, models.Reader.Status.BLOCKED)

        invalid = self._patch(self.reader, {"status": models.Reader.Status.SUSPENDED})
        self.assertEqual(invalid.status_code, 400)

    def test_cannot_block_or_demote_self(self):
        self.assertEqual(
            self._patch(self.admin, {"status": models.Reader.Status.BLOCKED}).status_code,
            409,
        )
        self.assertEqual(
            self._patch(self.admin, {"role": roles.LIBRARIAN_ROLE}).status_code,
            409,
        )
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.status, models.Reader.Status.ACTIVE)
        self.assertTrue(self.admin.groups.filter(name=roles.ADMIN_ROLE).exists())

    def test_last_admin_cannot_be_demoted_or_blocked(self):
        second = self._make_user("admin2@test.local", role=roles.ADMIN_ROLE)
        self.assertEqual(
            self._patch(second, {"role": roles.LIBRARIAN_ROLE}).status_code, 200
        )
        # Остался один активный администратор — попытка заблокировать его даёт 409.
        self.assertEqual(
            self._patch(self.admin, {"status": models.Reader.Status.BLOCKED}).status_code,
            409,
        )

    def test_duplicate_readers_route_is_removed(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/readers/").status_code, 404)
        self.assertEqual(
            self.client.get(f"/api/readers/{self.reader.id}/").status_code, 200
        )
        self.assertEqual(
            self.client.get(f"/api/readers/{self.reader.id}/issues/").status_code, 200
        )


class LibrarianReaderSearchTests(LibraryTestCase):
    """Библиотекарь ищет читателей для формы выдачи книги."""

    def test_librarian_can_search_readers_by_email_and_name(self):
        self.client.force_authenticate(self.librarian)

        by_email = self.client.get("/api/readers/search/", {"search": "reader2@test.local"})
        self.assertEqual(by_email.status_code, 200)
        self.assertEqual([row["id"] for row in by_email.data["results"]], [self.other_reader.id])
        self.assertEqual(by_email.data["results"][0]["full_name"], self.other_reader.full_name)

        by_name = self.client.get("/api/readers/search/", {"search": "Читалов"})
        self.assertEqual(by_name.status_code, 200)
        self.assertEqual([row["id"] for row in by_name.data["results"]], [self.reader.id])

    def test_plain_reader_cannot_search_readers(self):
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get("/api/readers/search/").status_code, 403)


class EndpointRoleMatrixTests(LibraryTestCase):
    """Матрица ролей для ключевых эндпоинтов."""

    def test_endpoint_role_matrix(self):
        cases = {
            "/api/books/": {None: 200, self.reader: 200, self.librarian: 200, self.admin: 200},
            "/api/issues/": {None: 401, self.reader: 403, self.librarian: 200, self.admin: 200},
            "/api/reservations/": {
                None: 401,
                self.reader: 403,
                self.librarian: 200,
                self.admin: 200,
            },
            "/api/users/": {None: 401, self.reader: 403, self.librarian: 403, self.admin: 200},
            "/api/action-log/": {
                None: 401,
                self.reader: 403,
                self.librarian: 200,
                self.admin: 200,
            },
            "/api/reports/books/?date_from=2026-01-01&date_to=2026-12-31": {
                None: 401,
                self.reader: 403,
                self.librarian: 200,
                self.admin: 200,
            },
            "/api/auth/me/": {None: 401, self.reader: 200, self.librarian: 200, self.admin: 200},
        }
        for path, expected in cases.items():
            for user, code in expected.items():
                with self.subTest(path=path, user=getattr(user, "email", "anonymous")):
                    self.client.force_authenticate(user)
                    self.assertEqual(self.client.get(path).status_code, code)


class ReaderAccessTests(LibraryTestCase):
    """Читатель не видит чужие выдачи и брони."""

    def test_reader_cannot_read_other_reader_history(self):
        self.client.force_authenticate(self.reader)
        response = self.client.get(f"/api/readers/{self.other_reader.id}/issues/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reader_can_read_own_history(self):
        self.client.force_authenticate(self.reader)
        response = self.client.get(f"/api/readers/{self.reader.id}/issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
