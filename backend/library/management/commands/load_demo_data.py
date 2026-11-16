"""Management command для загрузки демо-данных библиотеки."""
from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from library import models, roles


class Command(BaseCommand):
    help = "Load demo data: books, copies, readers, issues and reservations."

    def handle(self, *args, **options):
        librarian_group, _ = Group.objects.get_or_create(name=roles.LIBRARIAN_ROLE)
        reader_group, _ = Group.objects.get_or_create(name=roles.READER_ROLE)
        admin_group, _ = Group.objects.get_or_create(name=roles.ADMIN_ROLE)

        admin = models.Reader.objects.create_user(
            email="admin@library.local",
            password="AdminPass123",
            full_name="Администратор",
        )
        admin.groups.add(admin_group)

        librarian = models.Reader.objects.create_user(
            email="librarian@library.local",
            password="LibrarianPass123",
            full_name="Библиотекарь",
        )
        librarian.groups.add(librarian_group)

        readers = []
        for index in range(8):
            reader = models.Reader.objects.create_user(
                email=f"reader{index}@library.local",
                password="ReaderPass123",
                full_name=f"Читатель {index + 1}",
            )
            reader.groups.add(reader_group)
            readers.append(reader)

        books = []
        for index in range(24):
            book = models.Book.objects.create(
                title=f"Demo Book {index + 1}",
                description=f"Демонстрационная книга № {index + 1}",
                isbn=f"978-5-{index + 1:04d}-{index + 1:05d}-7",
                publication_year=1995 + (index % 25),
                publisher=f"Demo Publisher {index % 6 + 1}",
            )
            book.authors.add(
                models.Author.objects.create(
                    full_name=f"Demo Author {index + 1}",
                )
            )
            book.genres.add(
                models.Genre.objects.create(
                    name=f"Demo Genre {index % 8 + 1}",
                )
            )
            books.append(book)

        copies_by_book = {}
        for book in books:
            copies = []
            for copy_index in range(2):
                copy = models.BookCopy.objects.create(
                    book=book,
                    inventory_number=f"DEMO-{book.id:04d}-{copy_index + 1}",
                    status=models.BookCopy.Status.AVAILABLE,
                )
                copies.append(copy)
            copies_by_book[book.id] = copies

        issues_created = 0
        issue_status_cycle = [
            models.Issue.Status.RETURNED,
            models.Issue.Status.RETURNED,
            models.Issue.Status.OVERDUE,
            models.Issue.Status.ISSUED,
            models.Issue.Status.LOST,
        ]
        for book in books:
            for copy in copies_by_book[book.id]:
                status_value = issue_status_cycle[issues_created % len(issue_status_cycle)]
                issued_at = timezone.now() - timedelta(days=issues_created * 3)
                issue = models.Issue.objects.create(
                    reader=readers[issues_created % len(readers)],
                    copy=copy,
                    issued_at=issued_at,
                    due_at=issued_at + timedelta(days=14),
                    returned_at=(
                        issued_at + timedelta(days=10)
                        if status_value == models.Issue.Status.RETURNED
                        else None
                    ),
                    status=status_value,
                )
                if status_value == models.Issue.Status.ISSUED:
                    copy.status = models.BookCopy.Status.ISSUED
                    copy.save(update_fields=["status"])
                issues_created += 1

        models.Reservation.objects.create(
            reader=readers[0],
            book=books[0],
            status=models.Reservation.Status.PENDING,
            queue_date=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=48),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data loaded: {len(books)} books, {len(copies_by_book) * 2} copies, "
                f"{issues_created} issues, {len(readers)} readers, 1 reservation."
            )
        )
