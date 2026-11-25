"""Serializers for the library app."""
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from library import constants, models, roles
from library.services import Conflict


class AuthorSerializer(serializers.ModelSerializer):
    """Сериализатор автора книги."""

    class Meta:
        model = models.Author
        fields = ["id", "full_name"]


class GenreSerializer(serializers.ModelSerializer):
    """Сериализатор жанра книги."""

    class Meta:
        model = models.Genre
        fields = ["id", "name"]


class BookSerializer(serializers.ModelSerializer):
    """Сериализатор книги каталога."""

    isbn = serializers.CharField(max_length=20)
    authors = serializers.PrimaryKeyRelatedField(
        many=True, queryset=models.Author.objects.all(), required=False
    )
    genres = serializers.PrimaryKeyRelatedField(
        many=True, queryset=models.Genre.objects.all(), required=False
    )

    class Meta:
        model = models.Book
        fields = [
            "id",
            "title",
            "description",
            "isbn",
            "publication_year",
            "publisher",
            "cover_url",
            "authors",
            "genres",
        ]

    def validate(self, attrs):
        isbn = attrs.get("isbn")
        instance_pk = self.instance.pk if self.instance else None
        if isbn and models.Book.objects.filter(isbn=isbn).exclude(pk=instance_pk).exists():
            raise Conflict("Книга с таким ISBN уже существует.")
        return attrs

    def create(self, validated_data):
        authors = validated_data.pop("authors", [])
        genres = validated_data.pop("genres", [])
        book = models.Book.objects.create(**validated_data)
        book.authors.set(authors)
        book.genres.set(genres)
        return book

    def update(self, instance, validated_data):
        authors = validated_data.pop("authors", None)
        genres = validated_data.pop("genres", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if authors is not None:
            instance.authors.set(authors)
        if genres is not None:
            instance.genres.set(genres)
        return instance


class BookCopySerializer(serializers.ModelSerializer):
    """Сериализатор физического экземпляра книги."""

    book = serializers.PrimaryKeyRelatedField(queryset=models.Book.objects.all(), required=False)
    inventory_number = serializers.CharField(max_length=64)

    class Meta:
        model = models.BookCopy
        fields = ["id", "book", "inventory_number", "status"]

    def validate(self, attrs):
        inventory_number = attrs.get("inventory_number")
        instance_pk = self.instance.pk if self.instance else None
        if inventory_number and models.BookCopy.objects.filter(
            inventory_number=inventory_number
        ).exclude(pk=instance_pk).exists():
            raise Conflict("Инвентарный номер уже используется.")
        if attrs.get("status") in (
            models.BookCopy.Status.ISSUED,
            models.BookCopy.Status.RESERVED,
        ):
            raise Conflict(
                "Статусы ISSUED и RESERVED выставляются только сервисами библиотеки."
            )
        return attrs


class BookCopyUpdateSerializer(serializers.ModelSerializer):
    """Редактирование экземпляра: инвентарный номер и статус."""

    class Meta:
        model = models.BookCopy
        fields = ["inventory_number", "status"]

    def validate(self, attrs):
        inventory_number = attrs.get("inventory_number")
        instance_pk = self.instance.pk if self.instance else None
        if inventory_number and models.BookCopy.objects.filter(
            inventory_number=inventory_number
        ).exclude(pk=instance_pk).exists():
            raise Conflict("Инвентарный номер уже используется.")
        if attrs.get("status") in (
            models.BookCopy.Status.ISSUED,
            models.BookCopy.Status.RESERVED,
        ):
            raise Conflict(
                "Статусы ISSUED и RESERVED выставляются только сервисами библиотеки."
            )
        return attrs


class ReaderSerializer(serializers.ModelSerializer):
    """Сериализатор читателя / регистрации читателя."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    groups = serializers.SerializerMethodField()

    class Meta:
        model = models.Reader
        fields = ["id", "email", "password", "full_name", "phone", "status", "registered_at", "date_joined", "groups"]
        read_only_fields = ["id", "status", "registered_at", "date_joined"]

    def get_groups(self, obj):
        return [group.name for group in obj.groups.all()]

    def validate_email(self, value):
        instance = self.instance
        if models.Reader.objects.filter(email=value).exclude(pk=instance.pk if instance else None).exists():
            raise Conflict("Пользователь с таким email уже зарегистрирован.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return models.Reader.objects.create_user(
            email=validated_data["email"],
            password=password,
            full_name=validated_data.get("full_name") or "",
            phone=validated_data.get("phone"),
        )


class UserSerializer(serializers.ModelSerializer):
    """Пользователь в админке: роль и статус."""

    groups = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = models.Reader
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "status",
            "registered_at",
            "groups",
            "role",
        ]

    def get_groups(self, obj):
        return [group.name for group in obj.groups.all()]

    def get_role(self, obj):
        from library.services import users as user_services

        return user_services.role_of(obj)


class UserCreateSerializer(serializers.ModelSerializer):
    """Создание сотрудника или администратора с явной ролью."""

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    role = serializers.ChoiceField(choices=[roles.LIBRARIAN_ROLE, roles.ADMIN_ROLE])

    class Meta:
        model = models.Reader
        fields = ["email", "password", "full_name", "phone", "role"]

    def validate_email(self, value):
        if models.Reader.objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value


class UserUpdateSerializer(serializers.Serializer):
    """Разрешённые к изменению поля пользователя."""

    role = serializers.ChoiceField(choices=roles.ALL_ROLES, required=False)
    status = serializers.ChoiceField(
        choices=[models.Reader.Status.ACTIVE, models.Reader.Status.BLOCKED],
        required=False,
    )

    def __init__(self, *args, require_all=False, **kwargs):
        super().__init__(*args, **kwargs)
        if require_all:
            for name in ("role", "status"):
                self.fields[name].required = True

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Укажите role или status.")
        return attrs


class IssueSerializer(serializers.ModelSerializer):
    """Сериализатор выдачи книги: человекочитаемые вложенные данные."""

    reader_id = serializers.PrimaryKeyRelatedField(
        source="reader", queryset=models.Reader.objects.all()
    )
    copy_id = serializers.PrimaryKeyRelatedField(source="copy", queryset=models.BookCopy.objects.all())
    book = serializers.SerializerMethodField(source="copy")
    reader = serializers.SerializerMethodField(source="reader")
    copy = serializers.SerializerMethodField(source="copy")

    class Meta:
        model = models.Issue
        fields = ["id", "reader_id", "copy_id", "book", "reader", "copy", "issued_at", "due_at", "returned_at", "status"]
        read_only_fields = ["id", "issued_at", "due_at", "returned_at", "status"]

    def get_book(self, obj):
        return {"id": obj.copy.book_id, "title": obj.copy.book.title}

    def get_reader(self, obj):
        return {"id": obj.reader_id, "full_name": obj.reader.full_name}

    def get_copy(self, obj):
        return {"inventory_number": obj.copy.inventory_number}

    def create(self, validated_data):
        reader = validated_data["reader"]
        copy = validated_data["copy"]
        issued_at = validated_data.get("issued_at") or timezone.now()
        return models.Issue.objects.create(
            reader=reader,
            copy=copy,
            issued_at=issued_at,
            due_at=issued_at + constants.LOAN_PERIOD,
            status=models.Issue.Status.ISSUED,
        )


class ReservationSerializer(serializers.ModelSerializer):
    """Сериализатор бронирования / очереди ожидания."""

    reader_id = serializers.PrimaryKeyRelatedField(
        source="reader", queryset=models.Reader.objects.all()
    )
    book_id = serializers.PrimaryKeyRelatedField(source="book", queryset=models.Book.objects.all())
    book = serializers.SerializerMethodField(source="book")
    reader = serializers.SerializerMethodField(source="reader")
    copy = serializers.SerializerMethodField(source="copy")
    position = serializers.SerializerMethodField(source="pk")
    total = serializers.SerializerMethodField(source="pk")
    expires_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = models.Reservation
        fields = [
            "id",
            "reader_id",
            "reader",
            "book_id",
            "book",
            "copy",
            "status",
            "queue_date",
            "expires_at",
            "active_slot",
            "position",
            "total",
        ]
        read_only_fields = ["id", "status", "queue_date", "expires_at", "copy", "active_slot"]

    def get_reader(self, obj):
        return {"id": obj.reader_id, "full_name": obj.reader.full_name}

    def get_book(self, obj):
        return {"id": obj.book_id, "title": obj.book.title}

    def get_copy(self, obj):
        if obj.copy is None:
            return None
        return {"inventory_number": obj.copy.inventory_number}

    def get_position(self, obj):
        if obj.status not in (
            models.Reservation.Status.PENDING,
            models.Reservation.Status.ACTIVE,
        ):
            return None
        reservations = (
            models.Reservation.objects.filter(
                book_id=obj.book_id,
                status__in=[
                    models.Reservation.Status.PENDING,
                    models.Reservation.Status.ACTIVE,
                ],
            )
            .order_by("queue_date", "id")
        )
        position = 0
        for reservation in reservations:
            position += 1
            if reservation.pk == obj.pk:
                return position
        return None

    def get_total(self, obj):
        if obj.status not in (
            models.Reservation.Status.PENDING,
            models.Reservation.Status.ACTIVE,
        ):
            return None
        return (
            models.Reservation.objects.filter(
                book_id=obj.book_id,
                status__in=[
                    models.Reservation.Status.PENDING,
                    models.Reservation.Status.ACTIVE,
                ],
            ).count()
        )

    def create(self, validated_data):
        reader = validated_data["reader"]
        book = validated_data["book"]
        queue_date = validated_data.get("queue_date") or timezone.now()
        return models.Reservation.objects.create(
            reader=reader,
            book=book,
            status=models.Reservation.Status.PENDING,
            queue_date=queue_date,
            expires_at=queue_date + constants.RESERVATION_PERIOD,
        )


class ActionLogUserSerializer(serializers.ModelSerializer):
    """Краткие данные пользователя в журнале действий."""

    class Meta:
        model = models.Reader
        fields = ["id", "full_name", "email"]


class ActionLogSerializer(serializers.ModelSerializer):
    """Запись журнала: кто, когда и какой статус изменил."""

    user = ActionLogUserSerializer(read_only=True)

    class Meta:
        model = models.ActionLog
        fields = [
            "id",
            "user",
            "action",
            "entity_type",
            "entity_id",
            "old_status",
            "new_status",
            "created_at",
            "details",
        ]
