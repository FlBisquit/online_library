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


class AuthTests(LibraryTestCase):
    """JWT, registration and blocking behaviour."""

    def test_token_obtain_pair_success(self):
        response = self.client.post(
            "/api/token/",
            {"email": "reader@test.local", "password": "ReaderPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_token_refresh_and_blacklist(self):
        token_response = self.client.post(
            "/api/token/",
            {"email": "reader@test.local", "password": "ReaderPass123"},
            format="json",
        )
        refresh = token_response.data["refresh"]
        refresh_response = self.client.post(
            "/api/token/refresh/",
            {"refresh": refresh},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        new_refresh = refresh_response.data.get("refresh", refresh)

        blacklist_response = self.client.post(
            "/api/token/blacklist/",
            {"refresh": new_refresh},
            format="json",
        )
        self.assertEqual(blacklist_response.status_code, status.HTTP_200_OK)

        refreshed_after_blacklist = self.client.post(
            "/api/token/refresh/",
            {"refresh": new_refresh},
            format="json",
        )
        self.assertEqual(refreshed_after_blacklist.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_lifetime_is_15_minutes(self):
        response = self.client.post(
            "/api/token/",
            {"email": "reader@test.local", "password": "ReaderPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_token = response.data["access"]
        payload = json.loads(
            base64.urlsafe_b64decode(
                access_token.split(".")[1] + "=" * (-len(access_token.split(".")[1]) % 4)
            )
        )
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)
        self.assertEqual(payload["exp"] - payload["iat"], 900)

    def test_blocked_reader_cannot_get_token(self):
        self.reader.status = models.Reader.Status.BLOCKED
        self.reader.save(update_fields=["status"])
        response = self.client.post(
            "/api/token/",
            {"email": "reader@test.local", "password": "ReaderPass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blocked_reader_access_token_rejected(self):
        token_response = self.client.post(
            "/api/token/",
            {"email": "reader@test.local", "password": "ReaderPass123"},
            format="json",
        )
        access = token_response.data["access"]
        self.reader.status = models.Reader.Status.BLOCKED
        self.reader.save(update_fields=["status"])
        response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_me_returns_roles(self):
        self.client.force_authenticate(self.reader)
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "reader@test.local")
        self.assertIn("reader", response.data["groups"])

    def test_logout_with_invalid_refresh_token(self):
        response = self.client.post(
            "/api/token/blacklist/",
            {"refresh": "invalid-refresh-token"},
            format="json",
        )
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])

    def test_access_token_required_for_protected_endpoint(self):
        response = self.client.get(f"/api/readers/{self.reader.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)



class ReaderTests(LibraryTestCase):
    def test_register_reader_success_assigns_reader_group(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "full_name": "Новый Читатель",
                "email": "newreader@test.local",
                "password": "Str0ngPass!123",
                "phone": "+79990002222",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reader = models.Reader.objects.get(email="newreader@test.local")
        self.assertEqual(list(reader.groups.values_list("name", flat=True)), ["reader"])
        self.assertEqual(reader.status, models.Reader.Status.ACTIVE)

    def test_register_reader_creates_missing_reader_group(self):
        Group.objects.filter(name=roles.READER_ROLE).delete()
        response = self.client.post(
            "/api/auth/register/",
            {
                "full_name": "Читатель без группы",
                "email": "fresh@test.local",
                "password": "Str0ngPass!123",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reader = models.Reader.objects.get(email="fresh@test.local")
        self.assertEqual(list(reader.groups.values_list("name", flat=True)), ["reader"])

    def test_register_reader_weak_password_returns_400(self):
        response = self.client.post(
            "/api/auth/register/",
            {"full_name": "Слабый Читатель", "email": "weak@test.local", "password": "1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_reader_rejects_groups_and_status(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "full_name": "Читатель с группой",
                "email": "withgroup@test.local",
                "password": "Str0ngPass!123",
                "groups": ["librarian"],
                "status": "BLOCKED",
                "is_staff": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reader = models.Reader.objects.get(email="withgroup@test.local")
        self.assertEqual(list(reader.groups.values_list("name", flat=True)), ["reader"])
        self.assertEqual(reader.status, models.Reader.Status.ACTIVE)

    def test_reader_registration_duplicate_email_returns_409(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/api/auth/register/",
            {"full_name": "Дубль", "email": "reader@test.local", "password": "Str0ngPass!123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
