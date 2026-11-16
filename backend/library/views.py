"""API views for the library app."""
import csv
from datetime import datetime

from django.http import Http404, HttpResponse
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from library import models, services
from library.permissions import IsLibrarian, IsLibrarianOrAdmin
from library.serializers import BookCopySerializer, BookSerializer, IssueSerializer, ReaderSerializer, ReservationSerializer


def _get_reader_or_none(reader_id):
    try:
        return models.Reader.objects.get(pk=reader_id)
    except models.Reader.DoesNotExist:
        return None


def _can_access_reader(user, reader):
    if user.has_role("librarian") or user.has_role("admin"):
        return True
    return bool(user and user.is_authenticated and user.id == reader.id)


def _can_access_issue(user, issue):
    if user.has_role("librarian") or user.has_role("admin"):
        return True
    return bool(user and user.is_authenticated and user.id == issue.reader_id)


def _can_access_reservation(user, reservation):
    if user.has_role("librarian") or user.has_role("admin"):
        return True
    return bool(user and user.is_authenticated and user.id == reservation.reader_id)


class BookListCreateView(generics.ListCreateAPIView):
    """Список книг каталога (поиск / фильтрация / пагинация) и создание книги."""

    serializer_class = BookSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsLibrarian()]
        return [AllowAny()]

    def get_queryset(self):
        queryset = models.Book.objects.all()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(title__icontains=search)
                | models.Q(isbn__icontains=search)
                | models.Q(description__icontains=search)
                | models.Q(publisher__icontains=search)
            )
        author_id = self.request.query_params.get("author")
        if author_id:
            queryset = queryset.filter(bookauthor__author_id=author_id).distinct()
        genre_id = self.request.query_params.get("genre")
        if genre_id:
            queryset = queryset.filter(bookgenre__genre_id=genre_id).distinct()
        publication_year = self.request.query_params.get("publication_year")
        if publication_year:
            queryset = queryset.filter(publication_year=publication_year)
        return queryset


class BookDetailView(generics.RetrieveAPIView):
    """Получение книги каталога."""

    serializer_class = BookSerializer

    def get_permissions(self):
        return [AllowAny()]

    def get_queryset(self):
        return models.Book.objects.all()


class BookCopyListCreateView(generics.ListCreateAPIView):
    """Список физических экземпляров книги и их добавление."""

    serializer_class = BookCopySerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsLibrarian()]
        return [AllowAny()]

    def get_queryset(self):
        book_id = self.kwargs.get("book_id")
        queryset = models.BookCopy.objects.select_related("book").all()
        if book_id is not None:
            queryset = queryset.filter(book_id=book_id)
        return queryset

    def perform_create(self, serializer):
        book = models.Book.objects.get(pk=self.kwargs.get("book_id"))
        serializer.save(book=book)


class ReaderCreateView(generics.CreateAPIView):
    """Регистрация читателя."""

    serializer_class = ReaderSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ReaderDetailView(generics.RetrieveAPIView):
    """Получение данных читателя (сам или библиотекарь/администратор)."""

    serializer_class = ReaderSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_object(self):
        reader = _get_reader_or_none(self.kwargs.get("pk"))
        if reader is None:
            raise Http404
        if not _can_access_reader(self.request.user, reader):
            self.permission_denied(self.request, message="Недостаточно прав доступа.")
        return reader

    def get_queryset(self):
        return models.Reader.objects.all()


class ReaderIssuesView(APIView):
    """История выдач читателя (сам читатель или библиотекарь/администратор)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        reader = _get_reader_or_none(self.kwargs.get("pk"))
        if reader is None or not _can_access_reader(request.user, reader):
            return Response(
                {"detail": "Недостаточно прав доступа."},
                status=status.HTTP_403_FORBIDDEN,
            )
        issues = models.Issue.objects.filter(reader=reader).order_by("-issued_at")
        serializer = IssueSerializer(issues, many=True, context={"request": request})
        return Response(serializer.data)


class IssueCreateView(APIView):
    """Выдача экземпляра читателю."""

    permission_classes = [IsLibrarianOrAdmin]

    def post(self, request, *args, **kwargs):
        reader_id = request.data.get("reader_id")
        copy_id = request.data.get("copy_id")
        if not reader_id or not copy_id:
            return Response(
                {"detail": "Необходимо передать reader_id и copy_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        issue = services.issue_copy(reader_id, copy_id, user=request.user)
        serializer = IssueSerializer(issue, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IssueReturnView(APIView):
    """Возврат экземпляра по активной выдаче."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        issue_id = self.kwargs.get("pk")
        user = request.user
        issue = models.Issue.objects.select_related("reader").filter(pk=issue_id).first()
        if issue is None:
            return Response({"detail": "Выдача не найдена."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_issue(user, issue):
            return Response(
                {"detail": "Недостаточно прав доступа."},
                status=status.HTTP_403_FORBIDDEN,
            )
        updated = services.return_issue(issue_id, user=user)
        serializer = IssueSerializer(updated, context={"request": request})
        return Response(serializer.data)


class BookQueueListCreateView(APIView):
    """Получение очереди книги и добавление читателя в неё."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        book_id = self.kwargs.get("book_id")
        reservations = (
            list(
                models.Reservation.objects.filter(book_id=book_id)
                .select_related("reader")
                .order_by("queue_date", "id")
            )
        )
        serializer = ReservationSerializer(reservations, many=True, context={"request": request})
        results = []
        for position, reservation in enumerate(reservations, start=1):
            data = serializer.to_representation(reservation)
            data["position"] = position
            results.append(data)
        return Response(results)

    def post(self, request, *args, **kwargs):
        book_id = self.kwargs.get("book_id")
        reader_id = request.data.get("reader_id")
        if not reader_id:
            return Response(
                {"detail": "Необходимо передать reader_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        reader = _get_reader_or_none(reader_id)
        if reader is None:
            return Response({"detail": "Читатель не найден."}, status=status.HTTP_404_NOT_FOUND)
        if not (user.has_role("librarian") or user.has_role("admin")) and not (
            user.is_authenticated and user.id == reader.id
        ):
            return Response(
                {"detail": "Недостаточно прав доступа."},
                status=status.HTTP_403_FORBIDDEN,
            )
        reservation = services.join_queue(reader_id, book_id, user=user)
        serializer = ReservationSerializer(reservation, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BookQueuePositionView(APIView):
    """Текущая позиция читателя в очереди книги."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        book_id = self.kwargs.get("book_id")
        reader_id = self.kwargs.get("reader_id")
        reader = _get_reader_or_none(reader_id)
        if reader is None:
            return Response({"detail": "Читатель не найден."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_reader(request.user, reader):
            return Response(
                {"detail": "Недостаточно прав доступа."},
                status=status.HTTP_403_FORBIDDEN,
            )
        reservations = models.Reservation.objects.filter(
            book_id=book_id,
            status__in=[models.Reservation.Status.PENDING, models.Reservation.Status.ACTIVE],
        ).order_by("queue_date", "id")
        position = None
        status_value = None
        for index, reservation in enumerate(reservations, start=1):
            if reservation.reader_id == reader.id:
                position = index
                status_value = reservation.status
                break
        if position is None:
            return Response(
                {"book_id": book_id, "reader_id": reader_id, "position": None, "status": None},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "book_id": book_id,
                "reader_id": reader_id,
                "position": position,
                "status": status_value,
            }
        )


class ReservationDetailView(APIView):
    """Состояние бронирования."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        reservation = (
            models.Reservation.objects.select_related("reader", "book")
            .filter(pk=self.kwargs.get("pk"))
            .first()
        )
        if reservation is None:
            return Response({"detail": "Бронирование не найдено."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_reservation(request.user, reservation):
            return Response(
                {"detail": "Недостаточно прав доступа."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ReservationSerializer(reservation, context={"request": request})
        return Response(serializer.data)


class ReservationCancelView(APIView):
    """Отмена бронирования читателем / библиотекарем."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        reservation = (
            models.Reservation.objects.select_related("reader", "book")
            .filter(pk=self.kwargs.get("pk"))
            .first()
        )
        if reservation is None:
            return Response({"detail": "Бронирование не найдено."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_reservation(request.user, reservation):
            return Response(
                {"detail": "Недостаточно прав доступа."},
                status=status.HTTP_403_FORBIDDEN,
            )
        reservation, _copy = services.cancel_reservation(reservation.pk, user=request.user)
        serializer = ReservationSerializer(reservation, context={"request": request})
        return Response(serializer.data)


class IssuesReportView(APIView):
    """Отчёт: количество выдач по объектам (SQL-агрегация)."""

    permission_classes = [IsLibrarianOrAdmin]

    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Q as DjangoQ

        rows = (
            models.Issue.objects
            .values("copy__book_id")
            .annotate(
                total=Count("id"),
                issued=Count("id", filter=DjangoQ(status=models.Issue.Status.ISSUED)),
                returned=Count("id", filter=DjangoQ(status=models.Issue.Status.RETURNED)),
                lost=Count("id", filter=DjangoQ(status=models.Issue.Status.LOST)),
                overdue=Count("id", filter=DjangoQ(status=models.Issue.Status.OVERDUE)),
            )
            .order_by("copy__book_id")
        )
        return Response(
            [
                {
                    "book_id": row["copy__book_id"],
                    "total": row["total"],
                    "issued": row["issued"],
                    "returned": row["returned"],
                    "lost": row["lost"],
                    "overdue": row["overdue"],
                }
                for row in rows
            ]
        )


class CancellationsReportView(APIView):
    """Отчёт: количество отмен бронирований за выбранный период."""

    permission_classes = [IsLibrarianOrAdmin]

    def get(self, request, *args, **kwargs):
        period_start = request.query_params.get("period_start")
        period_end = request.query_params.get("period_end")
        queryset = models.Reservation.objects.filter(status=models.Reservation.Status.CANCELLED)
        if period_start:
            start = datetime.fromisoformat(period_start).date()
            queryset = queryset.filter(queue_date__date__gte=start)
        if period_end:
            end = datetime.fromisoformat(period_end).date()
            queryset = queryset.filter(queue_date__date__lte=end)
        return Response(
            {
                "period_start": period_start,
                "period_end": period_end,
                "cancelled_count": queryset.count(),
            }
        )


class IssuesExportView(APIView):
    """Экспорт отчёта о выдачах в CSV."""

    permission_classes = [IsLibrarianOrAdmin]

    def get(self, request, *args, **kwargs):
        issues = (
            models.Issue.objects.select_related("reader", "copy", "copy__book")
            .order_by("-issued_at")
        )
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="issues_export.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "id",
                "reader_id",
                "reader_full_name",
                "copy_id",
                "inventory_number",
                "book_id",
                "book_title",
                "issued_at",
                "due_at",
                "returned_at",
                "status",
            ]
        )
        for issue in issues:
            writer.writerow(
                [
                    issue.id,
                    issue.reader_id,
                    issue.reader.full_name,
                    issue.copy_id,
                    issue.copy.inventory_number,
                    issue.copy.book_id,
                    issue.copy.book.title,
                    issue.issued_at,
                    issue.due_at,
                    issue.returned_at,
                    issue.status,
                ]
            )
        return response
