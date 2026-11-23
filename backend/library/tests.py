"""Tests for the library app."""
import base64
import json
from datetime import timedelta

from django.contrib.auth.models import Group
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from library import models, services
from library import roles


def _ensure_group(name):
    group, _created = Group.objects.get_or_create(name=name)
    return group


@override_settings(DEFAULT_THROTTLE_RATES={"token": "1000/min"})
class LibraryTestCase(APITestCase):
    def setUp(self):
        self.librarian_group = _ensure_group(roles.LIBRARIAN_ROLE)
        self.reader_group = _ensure_group(roles.READER_ROLE)
        self.admin_group = _ensure_group(roles.ADMIN_ROLE)

        self.librarian = models.Reader.objects.create_user(
            email="librarian@test.local",
            password="LibrarianPass123",
            full_name="Библиотекарь",
        )
        self.librarian.groups.add(self.librarian_group)

        self.admin = models.Reader.objects.create_user(
            email="admin@test.local",
            password="AdminPass123",
            full_name="Администратор",
        )
        self.admin.groups.add(self.admin_group)

        self.reader = models.Reader.objects.create_user(
            email="reader@test.local",
            password="ReaderPass123",
            full_name="Читатель Читалов",
        )
        self.reader.groups.add(self.reader_group)

        self.other_reader = models.Reader.objects.create_user(
            email="reader2@test.local",
            password="ReaderPass123",
            full_name="Второй Читатель",
        )
        self.other_reader.groups.add(self.reader_group)

        self.book = models.Book.objects.create(
            title="Тестовая книга",
            isbn="978-5-000-000-00-0",
            publication_year=2020,
            publisher="Издательство",
        )
        self.copy = models.BookCopy.objects.create(
            book=self.book,
            inventory_number="INV-1",
        )

    # ---------- Аутентификация и JWT ----------

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


class BookCatalogTests(LibraryTestCase):
    def test_create_book_as_librarian(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/api/books/",
            {
                "title": "Новая книга",
                "description": "Описание",
                "isbn": "978-5-222-222-22-2",
                "publication_year": 2022,
                "publisher": "Издательство",
                "authors": [],
                "genres": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(models.Book.objects.count(), 2)

    def test_create_book_duplicate_isbn_returns_409(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            "/api/books/",
            {"title": "Дубль", "isbn": "978-5-000-000-00-0", "publication_year": 2020},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_book_detail(self):
        self.client.force_authenticate(self.reader)
        response = self.client.get(f"/api/books/{self.book.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Тестовая книга")

    def test_book_list_search_and_pagination(self):
        models.Book.objects.create(title="Другая книга", isbn="978-5-333-333-33-3")
        self.client.force_authenticate(self.reader)
        response = self.client.get("/api/books/", {"search": "Тестовая"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["count"], 1)

    def test_book_list_requires_no_auth(self):
        response = self.client.get("/api/books/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BookCopyTests(LibraryTestCase):
    def test_add_copy_and_list_copies(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            f"/api/books/{self.book.id}/copies/",
            {"inventory_number": "INV-2", "status": "AVAILABLE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(f"/api/books/{self.book.id}/copies/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_add_copy_duplicate_inventory_number_returns_409(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.post(
            f"/api/books/{self.book.id}/copies/",
            {"inventory_number": "INV-1", "status": "AVAILABLE"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


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


class WaitingQueueTests(LibraryTestCase):
    def test_reader_joins_queue(self):
        self.client.force_authenticate(self.reader)
        response = self.client.post(
            f"/api/books/{self.book.id}/queue/",
            {"reader_id": self.reader.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reservation = models.Reservation.objects.get()
        self.assertEqual(reservation.status, models.Reservation.Status.PENDING)

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


class ReportsTests(LibraryTestCase):
    def test_issues_report_aggregation(self):
        models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.RETURNED,
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reports/issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["total"], 1)
        self.assertEqual(response.data[0]["returned"], 1)

    def test_cancellations_report(self):
        models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=models.Reservation.Status.CANCELLED,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=48),
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reports/cancellations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["cancelled_count"], 1)

    def test_issues_export_csv(self):
        models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        self.client.force_authenticate(self.librarian)
        response = self.client.get("/api/reports/issues/export/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")


class ConcurrentIssueTests(TransactionTestCase):
    """Тест конкурентной выдачи последнего экземпляра (транзакции + select_for_update)."""

    def setUp(self):
        super().setUp()
        self.librarian_group = _ensure_group(roles.LIBRARIAN_ROLE)
        self.reader_group = _ensure_group(roles.READER_ROLE)

        self.librarian = models.Reader.objects.create_user(
            email="librarian@test.local",
            password="LibrarianPass123",
            full_name="Библиотекарь",
        )
        self.librarian.groups.add(self.librarian_group)

        self.reader = models.Reader.objects.create_user(
            email="reader@test.local",
            password="ReaderPass123",
            full_name="Читатель Читалов",
        )
        self.reader.groups.add(self.reader_group)

        self.other_reader = models.Reader.objects.create_user(
            email="reader2@test.local",
            password="ReaderPass123",
            full_name="Второй Читатель",
        )
        self.other_reader.groups.add(self.reader_group)

        self.book = models.Book.objects.create(
            title="Тестовая книга",
            isbn="978-5-000-000-00-0",
            publication_year=2020,
            publisher="Издательство",
        )
        self.copy = models.BookCopy.objects.create(
            book=self.book,
            inventory_number="INV-1",
        )

    def test_concurrent_issue_of_last_copy(self):
        from threading import Thread

        from rest_framework.test import APIClient

        results = []

        def worker(librarian, reader):
            client = APIClient()
            client.force_authenticate(librarian)
            response = client.post(
                "/api/issues/",
                {"reader_id": reader.id, "copy_id": self.copy.id},
                format="json",
            )
            results.append(response.status_code)

        thread1 = Thread(target=worker, args=(self.librarian, self.reader))
        thread2 = Thread(target=worker, args=(self.librarian, self.other_reader))
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        self.assertEqual(sorted(results), [status.HTTP_201_CREATED, status.HTTP_409_CONFLICT])
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.ISSUED)


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


class QueueConcurrencyTests(TransactionTestCase):
    """Параллельное вступление в очередь на одного читателя."""

    def setUp(self):
        super().setUp()
        self.librarian_group = _ensure_group(roles.LIBRARIAN_ROLE)
        self.reader_group = _ensure_group(roles.READER_ROLE)
        self.reader = models.Reader.objects.create_user(
            email="reader@test.local", password="ReaderPass123", full_name="Читатель Читалов"
        )
        self.reader.groups.add(self.reader_group)
        self.book = models.Book.objects.create(
            title="Тестовая книга", isbn="978-5-000-000-00-0"
        )
        self.copy = models.BookCopy.objects.create(
            book=self.book,
            inventory_number="INV-1",
            status=models.BookCopy.Status.ISSUED,
        )

    def test_ten_parallel_joins_give_one_created_and_nine_conflicts(self):
        import threading

        from rest_framework.test import APIClient

        barrier = threading.Barrier(10)
        results = []

        def worker():
            client = APIClient()
            client.force_authenticate(self.reader)
            barrier.wait()
            response = client.post(
                f"/api/books/{self.book.id}/queue/",
                {"reader_id": self.reader.id},
                format="json",
            )
            results.append(response.status_code)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(results.count(status.HTTP_201_CREATED), 1, results)
        self.assertEqual(results.count(status.HTTP_409_CONFLICT), 9, results)
        self.assertEqual(models.Reservation.objects.count(), 1)
