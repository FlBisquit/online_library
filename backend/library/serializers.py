"""Serializers for the library app."""
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from library import constants, models
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


class BookAuthorSerializer(serializers.ModelSerializer):
    """Сериализатор связи «книга — автор»."""

    class Meta:
        model = models.BookAuthor
        fields = ["id", "book", "author"]


class BookGenreSerializer(serializers.ModelSerializer):
    """Сериализатор связи «книга — жанр»."""

    class Meta:
        model = models.BookGenre
        fields = ["id", "book", "genre"]


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


class IssueSerializer(serializers.ModelSerializer):
    """Сериализатор выдачи книги."""

    reader_id = serializers.PrimaryKeyRelatedField(
        source="reader", queryset=models.Reader.objects.all()
    )
    copy_id = serializers.PrimaryKeyRelatedField(source="copy", queryset=models.BookCopy.objects.all())

    class Meta:
        model = models.Issue
        fields = ["id", "reader", "reader_id", "copy", "copy_id", "issued_at", "due_at", "returned_at", "status"]
        read_only_fields = ["id", "issued_at", "due_at", "returned_at", "status"]

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

    class Meta:
        model = models.Reservation
        fields = [
            "id",
            "reader",
            "reader_id",
            "book",
            "book_id",
            "copy",
            "status",
            "queue_date",
            "expires_at",
            "active_slot",
        ]
        read_only_fields = ["id", "status", "queue_date", "expires_at", "copy", "active_slot"]

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
