from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import validate_email
from django.db import models
from django.db.models import CheckConstraint, F, Q
from django.utils import timezone


class ReaderManager(BaseUserManager):
    """Менеджер пользователей библиотеки (Reader) с авторизацией по email."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("status", Reader.Status.ACTIVE)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("status", Reader.Status.ACTIVE)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)


class Reader(AbstractBaseUser, PermissionsMixin):
    """Читатель — пользователь библиотеки (учётная запись для JWT)."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        BLOCKED = "BLOCKED"
        SUSPENDED = "SUSPENDED"

    email = models.EmailField(unique=True, max_length=254)
    password = models.CharField(max_length=128, blank=True, default="")
    full_name = models.CharField(max_length=300)
    phone = models.CharField(max_length=30, null=True, blank=True)
    registered_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = ReaderManager()

    class Meta:
        verbose_name = "Читатель"
        verbose_name_plural = "Читатели"
        ordering = ["id"]
        constraints = [
            CheckConstraint(
                condition=Q(status__in=["ACTIVE", "BLOCKED", "SUSPENDED"]),
                name="check_reader_status_valid",
            ),
        ]

    def clean(self):
        super().clean()
        validate_email(self.email)

    def has_role(self, role_name):
        """Проверка принадлежности пользователя к роли (группе)."""
        return self.groups.filter(name=role_name).exists()

    @property
    def is_active(self):
        """Reader считается активным только при статусе ACTIVE."""
        return self.status == self.Status.ACTIVE

    def is_reader(self):
        return self.has_role("reader")

    def is_librarian(self):
        return self.has_role("librarian")

    def is_admin(self):
        return self.has_role("admin")

    def __str__(self):
        return self.full_name or self.email


class Author(models.Model):
    """Автор книги."""

    full_name = models.CharField(max_length=300)

    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Genre(models.Model):
    """Жанр книги."""

    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(models.Model):
    """Книга в каталоге."""

    title = models.CharField(max_length=500)
    description = models.TextField(null=True, blank=True)
    isbn = models.CharField(max_length=20, unique=True)
    publication_year = models.IntegerField(null=True, blank=True)
    publisher = models.CharField(max_length=200, null=True, blank=True)

    authors = models.ManyToManyField(Author, through="BookAuthor")
    genres = models.ManyToManyField(Genre, through="BookGenre")

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ["id"]

    def __str__(self):
        return self.title


class BookAuthor(models.Model):
    """Связь «книга — автор»."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Книга-Автор"
        verbose_name_plural = "Книги-Авторы"
        unique_together = ("book", "author")

    def __str__(self):
        return f"{self.book.title} — {self.author.full_name}"


class BookGenre(models.Model):
    """Связь «книга — жанр»."""

    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Книга-Жанр"
        verbose_name_plural = "Книги-Жанры"
        unique_together = ("book", "genre")

    def __str__(self):
        return f"{self.book.title} — {self.genre.name}"


class BookCopy(models.Model):
    """Физический экземпляр книги."""

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE"
        ISSUED = "ISSUED"
        RESERVED = "RESERVED"
        LOST = "LOST"
        RETIRED = "RETIRED"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    inventory_number = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    class Meta:
        verbose_name = "Экземпляр"
        verbose_name_plural = "Экземпляры"
        ordering = ["id"]
        constraints = [
            CheckConstraint(
                condition=Q(status__in=["AVAILABLE", "ISSUED", "RESERVED", "LOST", "RETIRED"]),
                name="check_book_copy_status_valid",
            ),
        ]

    def __str__(self):
        return self.inventory_number


class Issue(models.Model):
    """Выдача книги читателем."""

    class Status(models.TextChoices):
        ISSUED = "ISSUED"
        RETURNED = "RETURNED"
        OVERDUE = "OVERDUE"
        LOST = "LOST"

    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="issues")
    copy = models.ForeignKey(BookCopy, on_delete=models.CASCADE, related_name="issues")
    issued_at = models.DateTimeField()
    due_at = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED)

    class Meta:
        verbose_name = "Выдача"
        verbose_name_plural = "Выдачи"
        ordering = ["-issued_at"]
        constraints = [
            CheckConstraint(
                condition=Q(due_at__gte=F("issued_at")),
                name="check_issue_due_at_after_issued_at",
            ),
            CheckConstraint(
                condition=Q(status__in=["ISSUED", "RETURNED", "OVERDUE", "LOST"]),
                name="check_issue_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.reader.full_name} — {self.copy.inventory_number}"


class Reservation(models.Model):
    """Бронирование / очередь ожидания книги."""
    class Status(models.TextChoices):
        PENDING = "PENDING"
        ACTIVE = "ACTIVE"
        FULFILLED = "FULFILLED"
        CANCELLED = "CANCELLED"
        EXPIRED = "EXPIRED"

    reader = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="reservations")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reservations")
    copy = models.ForeignKey(
        BookCopy,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    queue_date = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    # 1 для живых броней (PENDING/ACTIVE), NULL для завершённых.
    # В MySQL несколько NULL в unique-индексе не конфликтуют.
    active_slot = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ["queue_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["reader", "book", "active_slot"],
                name="unique_active_reservation_per_reader_book",
            ),
            CheckConstraint(
                condition=Q(status__in=["PENDING", "ACTIVE", "FULFILLED", "CANCELLED", "EXPIRED"]),
                name="check_reservation_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.reader.full_name} → {self.book.title} ({self.status})"


class ActionLog(models.Model):
    """Журнал действий пользователей библиотеки."""

    user = models.ForeignKey(Reader, on_delete=models.CASCADE, related_name="action_logs")
    action = models.CharField(max_length=64)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Журнал действия"
        verbose_name_plural = "Журналы действий"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.action}"
