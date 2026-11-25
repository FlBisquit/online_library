"""Concurrent API tests with real database transactions."""
import threading
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from library import models, roles
from library.tests.base import LibraryTransactionTestCase


class ConcurrentIssueTests(LibraryTransactionTestCase):
    """Ten clients compete for a single copy and a single queue slot."""

    def _readers(self, count):
        readers = [self.reader, self.other_reader]
        while len(readers) < count:
            index = len(readers)
            reader = models.Reader.objects.create_user(
                email=f"concurrent{index}@test.local",
                password="ReaderPass123",
                full_name=f"Читатель {index}",
            )
            reader.groups.add(self.reader_group)
            readers.append(reader)
        return readers[:count]

    def _run_concurrently(self, workers, count):
        """Start ``count`` workers at the same moment and collect their results."""
        barrier = threading.Barrier(count)
        results = [None] * count

        def runner(index, target):
            client = APIClient()
            barrier.wait()
            results[index] = target(client)

        threads = [
            threading.Thread(target=runner, args=(index, workers[index]))
            for index in range(count)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        for thread in threads:
            self.assertFalse(thread.is_alive(), "A concurrent request hung")
        return results

    def test_ten_parallel_issues_give_one_created_and_nine_conflicts(self):
        readers = self._readers(10)

        def worker(reader):
            def request(client):
                client.force_authenticate(self.librarian)
                response = client.post(
                    "/api/issues/",
                    {"reader_id": reader.id, "copy_id": self.copy.id},
                    format="json",
                )
                return response.status_code

            return request

        results = self._run_concurrently([worker(reader) for reader in readers], 10)

        self.assertEqual(results.count(status.HTTP_201_CREATED), 1, results)
        self.assertEqual(results.count(status.HTTP_409_CONFLICT), 9, results)
        self.assertEqual(models.Issue.objects.filter(copy=self.copy).count(), 1)
        self.copy.refresh_from_db()
        self.assertEqual(self.copy.status, models.BookCopy.Status.ISSUED)

    def test_ten_parallel_joins_give_one_created_and_nine_conflicts(self):
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])

        def request(client):
            client.force_authenticate(self.reader)
            response = client.post(
                f"/api/books/{self.book.id}/queue/",
                {"reader_id": self.reader.id},
                format="json",
            )
            return response.status_code

        results = self._run_concurrently([request] * 10, 10)

        self.assertEqual(results.count(status.HTTP_201_CREATED), 1, results)
        self.assertEqual(results.count(status.HTTP_409_CONFLICT), 9, results)
        self.assertEqual(models.Reservation.objects.filter(book=self.book).count(), 1)

    def test_parallel_return_and_join_do_not_conflict_or_hang(self):
        now = timezone.now()
        self.copy.status = models.BookCopy.Status.ISSUED
        self.copy.save(update_fields=["status"])
        issue = models.Issue.objects.create(
            reader=self.reader,
            copy=self.copy,
            issued_at=now,
            due_at=now + timedelta(days=14),
            status=models.Issue.Status.ISSUED,
        )
        models.Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=models.Reservation.Status.PENDING,
            queue_date=now,
            expires_at=now + timedelta(hours=48),
            active_slot=1,
        )

        def return_request(client):
            client.force_authenticate(self.librarian)
            return client.post(f"/api/issues/{issue.id}/return/", {}, format="json").status_code

        def join_request(client):
            client.force_authenticate(self.other_reader)
            return client.post(
                f"/api/books/{self.book.id}/queue/",
                {"reader_id": self.other_reader.id},
                format="json",
            ).status_code

        results = self._run_concurrently([return_request, join_request], 2)

        self.assertNotIn(status.HTTP_500_INTERNAL_SERVER_ERROR, results)
        self.assertEqual(results[0], status.HTTP_200_OK, results)
        self.assertEqual(results[1], status.HTTP_201_CREATED, results)
        self.assertEqual(
            models.Reservation.objects.filter(
                book=self.book, status=models.Reservation.Status.ACTIVE
            ).count(),
            1,
        )
        self.assertEqual(
            models.Reservation.objects.filter(
                book=self.book, status=models.Reservation.Status.PENDING
            ).count(),
            1,
        )
