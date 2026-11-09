from django.db import models
from django.db.models import CheckConstraint, F, Q


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


class Reader(models.Model):
    """Читатель."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE"
        BLOCKED = "BLOCKED"
        SUSPENDED = "SUSPENDED"

    full_name = models.CharField(max_length=300)
    email = models.CharField(max_length=254, unique=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

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

    def __str__(self):
        return self.full_name


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
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    queue_date = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ["queue_date", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["reader", "book", "status"],
                name="unique_reservation_per_reader_book_status",
            ),
            CheckConstraint(
                condition=Q(status__in=["PENDING", "ACTIVE", "FULFILLED", "CANCELLED", "EXPIRED"]),
                name="check_reservation_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.reader.full_name} → {self.book.title} ({self.status})"
