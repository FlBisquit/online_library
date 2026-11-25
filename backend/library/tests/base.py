"""Shared fixtures for the library test package.

The mixin intentionally contains no ``test_*`` methods: every test is defined
exactly once in a focused module, so the number reported by ``manage.py test``
matches the number of unique test methods in the package.
"""
from django.contrib.auth.models import Group
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APITestCase

from library import models, roles


def _ensure_group(name):
    group, _created = Group.objects.get_or_create(name=name)
    return group


class LibraryFixtureMixin:
    """Database fixtures shared by all library tests."""

    def setUp(self):
        super().setUp()
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


@override_settings(DEFAULT_THROTTLE_RATES={"token": "1000/min"})
class LibraryTestCase(LibraryFixtureMixin, APITestCase):
    """Base case for isolated API tests."""


@override_settings(DEFAULT_THROTTLE_RATES={"token": "1000/min"})
class LibraryTransactionTestCase(LibraryFixtureMixin, TransactionTestCase):
    """Base case for tests that need real transactions across threads."""
