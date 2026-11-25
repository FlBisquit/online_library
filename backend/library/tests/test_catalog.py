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


class CatalogManagementTests(LibraryTestCase):
    """Управление каталогом: права, CRUD, переходы и ограничения удаления."""

    def catalog_write_cases(self):
        return [
            ("post", "/api/books/", {"title": "Новая", "isbn": "978-5-777-000-00-1"}),
            ("patch", f"/api/books/{self.book.id}/", {"title": "Переименовано"}),
            ("delete", f"/api/books/{self.book.id}/", None),
            (
                "post",
                f"/api/books/{self.book.id}/copies/",
                {"inventory_number": "CAT-NEW-1"},
            ),
            ("patch", f"/api/copies/{self.copy.id}/", {"status": "LOST"}),
            ("delete", f"/api/copies/{self.copy.id}/", None),
            ("post", "/api/authors/", {"full_name": "Автор"}),
            ("patch", "/api/authors/1/", {"full_name": "Автор 2"}),
            ("delete", "/api/authors/1/", None),
            ("post", "/api/genres/", {"name": "Жанр"}),
            ("patch", "/api/genres/1/", {"name": "Жанр 2"}),
            ("delete", "/api/genres/1/", None),
        ]

    def _request(self, method, path, data):
        if data is None:
            return getattr(self.client, method)(path)
        return getattr(self.client, method)(path, data, format="json")

    def test_reader_cannot_write_catalog(self):
        self.client.force_authenticate(self.reader)
        for method, path, data in self.catalog_write_cases():
            with self.subTest(method=method, path=path):
                self.assertEqual(self._request(method, path, data).status_code, 403)

    def test_librarian_and_admin_can_write_catalog(self):
        for index, user in enumerate([self.librarian, self.admin], start=1):
            self.client.force_authenticate(user)
            book = self.client.post(
                "/api/books/",
                {"title": f"Книга {index}", "isbn": f"978-5-777-000-01-{index}"},
                format="json",
            )
            self.assertEqual(book.status_code, 201)

            patch = self.client.patch(
                f"/api/books/{book.data['id']}/", {"publisher": "Издатель"}, format="json"
            )
            self.assertEqual(patch.status_code, 200)

            author = self.client.post(
                "/api/authors/", {"full_name": f"Автор {index}"}, format="json"
            )
            self.assertEqual(author.status_code, 201)
            genre = self.client.post(
                "/api/genres/", {"name": f"Жанр {index}"}, format="json"
            )
            self.assertEqual(genre.status_code, 201)

            copy = self.client.post(
                f"/api/books/{book.data['id']}/copies/",
                {"inventory_number": f"CAT-{index}"},
                format="json",
            )
            self.assertEqual(copy.status_code, 201)
            updated = self.client.patch(
                f"/api/copies/{copy.data['id']}/", {"status": "LOST"}, format="json"
            )
            self.assertEqual(updated.status_code, 200)

            self.assertEqual(
                self.client.delete(f"/api/copies/{copy.data['id']}/").status_code, 204
            )
            self.assertEqual(
                self.client.delete(f"/api/books/{book.data['id']}/").status_code, 204
            )
            self.assertEqual(
                self.client.delete(f"/api/authors/{author.data['id']}/").status_code, 204
            )
            self.assertEqual(
                self.client.delete(f"/api/genres/{genre.data['id']}/").status_code, 204
            )

    def test_catalog_read_is_available_to_everyone(self):
        paths = [
            "/api/books/",
            f"/api/books/{self.book.id}/",
            f"/api/books/{self.book.id}/copies/",
            "/api/authors/",
            "/api/genres/",
        ]
        for user in [None, self.reader, self.librarian, self.admin]:
            self.client.force_authenticate(user)
            for path in paths:
                with self.subTest(user=user, path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_delete_book_with_issue_returns_409(self):
        models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
        )
        self.client.force_authenticate(self.admin)
        response = self.client.delete(f"/api/books/{self.book.id}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(models.Book.objects.filter(pk=self.book.id).exists())

    def test_delete_book_with_live_reservation_returns_409(self):
        models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=models.Reservation.Status.PENDING,
            queue_date=timezone.now(),
            active_slot=1,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.delete(f"/api/books/{self.book.id}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(models.Book.objects.filter(pk=self.book.id).exists())

    def test_copy_patch_uses_transitions_and_logs(self):
        self.client.force_authenticate(self.librarian)
        response = self.client.patch(
            f"/api/copies/{self.copy.id}/", {"status": "LOST"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.LOST)
        log = models.ActionLog.objects.get(entity_type="BookCopy", entity_id=self.copy.id)
        self.assertEqual(log.old_status, models.BookCopy.Status.AVAILABLE)
        self.assertEqual(log.new_status, models.BookCopy.Status.LOST)

        forbidden = self.client.patch(
            f"/api/copies/{self.copy.id}/", {"status": "ISSUED"}, format="json"
        )
        self.assertEqual(forbidden.status_code, 409)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.LOST)

    def test_manual_available_from_issued_or_reserved_returns_409(self):
        for locked_status in (
            models.BookCopy.Status.ISSUED,
            models.BookCopy.Status.RESERVED,
        ):
            with self.subTest(status=locked_status):
                self.copy.status = locked_status
                self.copy.save(update_fields=["status"])
                issue = models.Issue.objects.create(
                    reader=self.reader,
                    copy=self.copy,
                    issued_at=timezone.now(),
                    due_at=timezone.now() + timedelta(days=14),
                )
                self.client.force_authenticate(self.librarian)
                response = self.client.patch(
                    f"/api/copies/{self.copy.id}/", {"status": "AVAILABLE"}, format="json"
                )
                self.assertEqual(response.status_code, 409)
                self.copy.refresh_from_db()
                self.assertEqual(self.copy.status, locked_status)
                issue.refresh_from_db()
                self.assertEqual(issue.status, models.Issue.Status.ISSUED)

    def test_delete_copy_with_issue_returns_409(self):
        models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=14),
        )
        self.client.force_authenticate(self.admin)
        response = self.client.delete(f"/api/copies/{self.copy.id}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(models.BookCopy.objects.filter(pk=self.copy.id).exists())

    def test_delete_copy_with_live_reservation_returns_409(self):
        reservation = models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            copy=self.copy,
            status=models.Reservation.Status.ACTIVE,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(days=1),
            active_slot=1,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.delete(f"/api/copies/{self.copy.id}/")
        self.assertEqual(response.status_code, 409)
        self.assertTrue(models.BookCopy.objects.filter(pk=self.copy.id).exists())
        reservation.refresh_from_db()
        self.assertEqual(reservation.copy_id, self.copy.id)

    def test_limit_query_param_controls_page_size(self):
        for index in range(3):
            models.Book.objects.create(
                title=f"Доп. книга {index}", isbn=f"978-5-888-000-00-{index}"
            )
        self.client.force_authenticate(self.reader)
        response = self.client.get("/api/books/", {"limit": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)
