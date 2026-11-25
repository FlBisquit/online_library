"""API views for the library app."""
import csv
from datetime import date

from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from library import models, services
from library.pagination import CatalogPagination
from library.permissions import IsAdmin, IsCatalogEditor, IsLibrarianOrAdmin
from library.serializers import (
    ActionLogSerializer,
    AuthorSerializer,
    BookCopySerializer,
    BookCopyUpdateSerializer,
    BookSerializer,
    GenreSerializer,
    IssueSerializer,
    ReaderSerializer,
    ReservationSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from library.services import catalog as catalog_services
from library.services import reports as report_services
from library.services import users as user_services


def _get_reader_or_none(reader_id):
    try:
        return models.Reader.objects.get(pk=reader_id)
    except models.Reader.DoesNotExist:
        return None


def _can_access_reader(user, reader):
    if user.has_role("librarian") or user.has_role("admin"):
        return True
    return bool(user and user.is_authenticated and user.id == reader.id)


def _is_staff(user):
    """Библиотекарь или администратор."""
    return bool(
        user
        and user.is_authenticated
        and (user.has_role("librarian") or user.has_role("admin"))
    )


def _can_access_reservation(user, reservation):
    if _is_staff(user):
        return True
    return bool(user and user.is_authenticated and user.id == reservation.reader_id)


def _parse_int_param(value, name):
    """Целочисленный query-параметр; мусор -> 400."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValidationError({name: "Ожидается целое число."})


def _parse_date_param(value, name):
    """Дата в формате ГГГГ-ММ-ДД; мусор -> 400."""
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({name: "Используйте формат ГГГГ-ММ-ДД."})


def _parse_report_period(params):
    """Обязательные даты отчёта; мусор или перевёрнутый период -> 400."""
    date_from = _parse_date_param(params.get("date_from"), "date_from")
    date_to = _parse_date_param(params.get("date_to"), "date_to")
    if date_from is None:
        raise ValidationError({"date_from": "Обязательный параметр."})
    if date_to is None:
        raise ValidationError({"date_to": "Обязательный параметр."})
    if date_from > date_to:
        raise ValidationError({"date_from": "date_from не может быть позже date_to."})
    return date_from, date_to


class BookListCreateView(generics.ListCreateAPIView):
    """Список книг каталога (поиск / фильтрация / пагинация) и создание книги."""

    serializer_class = BookSerializer
    pagination_class = CatalogPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCatalogEditor()]
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


class BookDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Просмотр, редактирование и удаление книги каталога."""

    serializer_class = BookSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return [IsCatalogEditor()]

    def get_queryset(self):
        return models.Book.objects.all()

    def get(self, request, *args, **kwargs):
        services.expire_reservations(self.kwargs.get("pk"))
        return super().get(request, *args, **kwargs)

    def perform_destroy(self, instance):
        catalog_services.delete_book(instance.pk)


class BookCopyListCreateView(generics.ListCreateAPIView):
    """Список физических экземпляров книги и их добавление."""

    serializer_class = BookCopySerializer
    pagination_class = CatalogPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCatalogEditor()]
        return [AllowAny()]

    def get(self, request, *args, **kwargs):
        services.expire_reservations(self.kwargs.get("book_id"))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        book_id = self.kwargs.get("book_id")
        queryset = models.BookCopy.objects.select_related("book").all()
        if book_id is not None:
            queryset = queryset.filter(book_id=book_id)
        return queryset

    def perform_create(self, serializer):
        book = models.Book.objects.get(pk=self.kwargs.get("book_id"))
        serializer.save(book=book)


class BookCopyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Просмотр и редактирование экземпляра книги."""

    def get_serializer_class(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return BookCopySerializer
        return BookCopyUpdateSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return [IsCatalogEditor()]

    def get_queryset(self):
        return models.BookCopy.objects.select_related("book").all()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get("partial", False))
        serializer.is_valid(raise_exception=True)
        updated = catalog_services.update_copy(
            instance.pk,
            user=request.user,
            inventory_number=serializer.validated_data.get("inventory_number"),
            status=serializer.validated_data.get("status"),
        )
        return Response(self.get_serializer(updated).data)

    def perform_destroy(self, instance):
        catalog_services.delete_copy(instance.pk)


class AuthorListCreateView(generics.ListCreateAPIView):
    """Справочник авторов."""

    serializer_class = AuthorSerializer
    pagination_class = CatalogPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCatalogEditor()]
        return [AllowAny()]

    def get_queryset(self):
        queryset = models.Author.objects.all().order_by("full_name")
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(full_name__icontains=search)
        return queryset


class AuthorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Отдельный автор справочника."""

    serializer_class = AuthorSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return [IsCatalogEditor()]

    def get_queryset(self):
        return models.Author.objects.all()


class GenreListCreateView(generics.ListCreateAPIView):
    """Справочник жанров."""

    serializer_class = GenreSerializer
    pagination_class = CatalogPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCatalogEditor()]
        return [AllowAny()]

    def get_queryset(self):
        queryset = models.Genre.objects.all().order_by("name")
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset


class GenreDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Отдельный жанр справочника."""

    serializer_class = GenreSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [AllowAny()]
        return [IsCatalogEditor()]

    def get_queryset(self):
        return models.Genre.objects.all()


class RegisterView(generics.CreateAPIView):
    """Публичная регистрация читателя (роль reader)."""

    serializer_class = ReaderSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        reader = serializer.save()
        from django.contrib.auth.models import Group

        from library import roles

        group, _created = Group.objects.get_or_create(name=roles.READER_ROLE)
        reader.groups.add(group)
        return reader

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ReaderSearchListView(generics.ListAPIView):
    """Поиск читателей по email или ФИО для формы выдачи книги."""

    serializer_class = UserSerializer
    permission_classes = [IsLibrarianOrAdmin]
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = models.Reader.objects.all()
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(email__icontains=search) | models.Q(full_name__icontains=search)
            )
        return queryset.order_by("id")


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
        services.mark_overdue()
        issues = models.Issue.objects.filter(reader=reader).order_by("-issued_at")
        serializer = IssueSerializer(issues, many=True, context={"request": request})
        return Response(serializer.data)


class MeView(APIView):
    """Данные текущего аутентифицированного пользователя и его ролей."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = ReaderSerializer(request.user)
        return Response(serializer.data)


class MeReservationsView(APIView):
    """Брони и очереди текущего читателя с позицией."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        services.mark_overdue()
        reservations = (
            models.Reservation.objects.filter(
                reader=request.user,
                status__in=[
                    models.Reservation.Status.PENDING,
                    models.Reservation.Status.ACTIVE,
                ],
            )
            .select_related("reader", "book", "copy")
            .order_by("-queue_date", "-id")
        )
        serializer = ReservationSerializer(reservations, many=True, context={"request": request})
        return Response(serializer.data)


class IssueListView(generics.ListCreateAPIView):
    """Список выдач с фильтрацией (GET) и создание выдачи (POST, библиотекарь/администратор)."""

    serializer_class = IssueSerializer
    permission_classes = [IsLibrarianOrAdmin]

    def get(self, request, *args, **kwargs):
        services.mark_overdue()
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = models.Issue.objects.select_related("reader", "copy", "copy__book").all()
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        reader_id = self.request.query_params.get("reader_id")
        if reader_id:
            queryset = queryset.filter(reader_id=reader_id)
        due_value = self.request.query_params.get("due")
        if due_value:
            if due_value == "today":
                queryset = queryset.filter(due_at__date=timezone.now().date())
            elif due_value == "overdue":
                queryset = queryset.filter(due_at__lt=timezone.now())
            else:
                raise ValidationError({"due": "Допустимые значения: today, overdue."})
        search_value = self.request.query_params.get("search")
        if search_value:
            queryset = queryset.filter(
                models.Q(reader__full_name__icontains=search_value)
                | models.Q(reader__email__icontains=search_value)
                | models.Q(copy__book__title__icontains=search_value)
                | models.Q(copy__inventory_number__icontains=search_value)
            )
        return queryset

    def create(self, request, *args, **kwargs):
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


class UserListCreateView(generics.ListCreateAPIView):
    """Список пользователей и создание сотрудников (только администратор)."""

    permission_classes = [IsAdmin]
    pagination_class = CatalogPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        queryset = models.Reader.objects.all()
        params = self.request.query_params
        search = params.get("search")
        if search:
            queryset = queryset.filter(
                models.Q(email__icontains=search) | models.Q(full_name__icontains=search)
            )
        role = params.get("role")
        if role:
            queryset = queryset.filter(groups__name=role)
        user_status = params.get("status")
        if user_status:
            queryset = queryset.filter(status=user_status)
        return queryset.distinct().order_by("id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reader = user_services.create_staff_user(actor=request.user, **serializer.validated_data)
        return Response(UserSerializer(reader).data, status=status.HTTP_201_CREATED)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """Просмотр и изменение роли/статуса пользователя (только администратор)."""

    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return models.Reader.objects.all()

    def update(self, request, *args, **kwargs):
        target = self.get_object()
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = user_services.update_user(
            target_id=target.pk,
            actor=request.user,
            **serializer.validated_data,
        )
        return Response(UserSerializer(updated).data)


class IssueReturnView(APIView):
    """Возврат экземпляра — только библиотекарь или администратор."""

    permission_classes = [IsLibrarianOrAdmin]

    def post(self, request, *args, **kwargs):
        issue_id = self.kwargs.get("pk")
        updated = services.return_issue(issue_id, user=request.user)
        serializer = IssueSerializer(updated, context={"request": request})
        return Response(serializer.data)


class IssueMarkLostView(APIView):
    """Отметить выдачу и экземпляр утерянными — только сотрудники."""

    permission_classes = [IsLibrarianOrAdmin]

    def post(self, request, *args, **kwargs):
        issue = services.mark_issue_lost(self.kwargs.get("pk"), user=request.user)
        serializer = IssueSerializer(issue, context={"request": request})
        return Response(serializer.data)


class BookQueueListCreateView(APIView):
    """Получение очереди книги и добавление читателя в неё."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        book_id = self.kwargs.get("book_id")
        if not models.Book.objects.filter(pk=book_id).exists():
            return Response({"detail": "Книга не найдена."}, status=status.HTTP_404_NOT_FOUND)
        reservations = list(
            models.Reservation.objects.filter(
                book_id=book_id,
                status__in=[models.Reservation.Status.PENDING, models.Reservation.Status.ACTIVE],
            )
            .select_related("reader")
            .order_by("queue_date", "id")
        )
        total = len(reservations)

        if _is_staff(request.user):
            results = []
            for position, reservation in enumerate(reservations, start=1):
                data = ReservationSerializer(reservation, context={"request": request}).data
                data["position"] = position
                data["total"] = total
                results.append(data)
            return Response({"book_id": book_id, "total": total, "results": results})

        # Читатель видит только свою позицию и общее число людей в очереди.
        for position, reservation in enumerate(reservations, start=1):
            if reservation.reader_id == request.user.id:
                return Response(
                    {
                        "book_id": book_id,
                        "reader_id": request.user.id,
                        "position": position,
                        "total": total,
                        "status": reservation.status,
                    }
                )
        return Response(
            {
                "book_id": book_id,
                "reader_id": request.user.id,
                "position": None,
                "total": total,
                "status": None,
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    def post(self, request, *args, **kwargs):
        book_id = self.kwargs.get("book_id")
        if not models.Book.objects.filter(pk=book_id).exists():
            return Response({"detail": "Книга не найдена."}, status=status.HTTP_404_NOT_FOUND)
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
        if not _is_staff(user) and not (
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
        if not models.Book.objects.filter(pk=book_id).exists():
            return Response({"detail": "Книга не найдена."}, status=status.HTTP_404_NOT_FOUND)
        reader = _get_reader_or_none(reader_id)
        if reader is None:
            return Response({"detail": "Читатель не найден."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_access_reader(request.user, reader):
            return Response(
                {"detail": "Недостаточно прав доступа."},
                status=status.HTTP_403_FORBIDDEN,
            )
        reservations = list(
            models.Reservation.objects.filter(
                book_id=book_id,
                status__in=[models.Reservation.Status.PENDING, models.Reservation.Status.ACTIVE],
            ).order_by("queue_date", "id")
        )
        total = len(reservations)
        position = None
        status_value = None
        for index, reservation in enumerate(reservations, start=1):
            if reservation.reader_id == reader.id:
                position = index
                status_value = reservation.status
                break
        if position is None:
            return Response(
                {
                    "book_id": book_id,
                    "reader_id": reader_id,
                    "position": None,
                    "total": total,
                    "status": None,
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "book_id": book_id,
                "reader_id": reader_id,
                "position": position,
                "total": total,
                "status": status_value,
            }
        )


class ReservationListView(generics.ListAPIView):
    """Список бронирований для сотрудников (ожидание выдачи)."""

    serializer_class = ReservationSerializer
    permission_classes = [IsLibrarianOrAdmin]
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = models.Reservation.objects.select_related("reader", "book", "copy").all()
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset.order_by("queue_date", "id")


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


class BooksReportView(APIView):
    """Отчёт по книгам: выдачи, просрочки и отмены за период (SQL-агрегация)."""

    permission_classes = [IsLibrarianOrAdmin]

    def get(self, request, *args, **kwargs):
        date_from, date_to = _parse_report_period(request.query_params)
        rows = report_services.books_report(date_from, date_to)
        return Response(
            [
                {
                    "book_id": row["id"],
                    "title": row["title"],
                    "loans": row["loans"],
                    "overdue": row["overdue"],
                    "cancellations": row["cancellations"],
                }
                for row in rows
            ]
        )


class BooksReportExportView(APIView):
    """CSV-выгрузка отчёта по книгам (utf-8-sig для Excel)."""

    permission_classes = [IsLibrarianOrAdmin]

    def get(self, request, *args, **kwargs):
        date_from, date_to = _parse_report_period(request.query_params)
        rows = report_services.books_report(date_from, date_to)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response.write("\ufeff")
        response["Content-Disposition"] = (
            f'attachment; filename="report_{date_from.isoformat()}_{date_to.isoformat()}.csv"'
        )
        report_services.write_books_report_csv(rows, csv.writer(response))
        return response


class ActionLogListView(generics.ListAPIView):
    """Журнал действий: кто, когда и какой статус изменил (только сотрудники)."""

    serializer_class = ActionLogSerializer
    permission_classes = [IsLibrarianOrAdmin]

    def get_queryset(self):
        params = self.request.query_params
        queryset = models.ActionLog.objects.select_related("user").order_by(
            "-created_at", "-id"
        )

        user_id = _parse_int_param(params.get("user"), "user")
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)

        entity_id = _parse_int_param(params.get("entity_id"), "entity_id")
        if entity_id is not None:
            queryset = queryset.filter(entity_id=entity_id)

        entity_type = params.get("entity_type")
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)

        action = params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        date_from = _parse_date_param(params.get("date_from"), "date_from")
        date_to = _parse_date_param(params.get("date_to"), "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_from": "date_from не может быть позже date_to."})
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset
