"""Management command for loading demo data."""
from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from library import constants, models, roles, services

ADMIN_EMAIL = "admin@library.local"
LIBRARIAN_EMAIL = "librarian@library.local"
ADMIN_PASSWORD = "AdminPass123"
LIBRARIAN_PASSWORD = "LibrarianPass123"
READER_PASSWORD = "ReaderPass123"
DEMO_READERS_COUNT = 8
BLOCKED_READER_INDEX = 7
LOAN_PERIOD = constants.LOAN_PERIOD
RESERVATION_PERIOD = constants.RESERVATION_PERIOD


def _demo_isbn(index: int) -> str:
    """Смоделированный ISBN-13 для демо-книги."""
    digits = f"978{5}{10000000 + index:08d}"
    checksum = sum(int(d) * (1 if position % 2 == 0 else 3) for position, d in enumerate(digits))
    check = (10 - checksum % 10) % 10
    return f"{digits}{check}"


def _demo_cover_url(isbn: str) -> str:
    """Обложка по открытым каталогам OCLC по ISBN."""
    return f"https://covers.openlibrary.org/isbn/{isbn}-L.jpg"


DEMO_GENRES = [
    "Фантастика",
    "Фэнтези",
    "Роман",
    "Приключения",
    "Научная фантастика",
    "История",
    "Детектив",
    "Мистика",
]

DEMO_AUTHORS = [
    "Герман Гёте",
    "Михаил Булгаков",
    "Фома Достоевский",
    "Дэниел Дефо",
    "Джоан Роулинг",
    "Джон Толкин",
    "Герберт Уэллс",
    "Николай Гоголь",
    "Лев Толстой",
    "Стивен Кинг",
]

DEMO_BOOKS = [
    {
        "title": "451 градус по Фаренгейту",
        "authors": ("Герман Гёте",),
        "genres": ("Фантастика",),
        "year": 1953,
        "publisher": "Corgi",
        "description": "Антиутопия о тотальном контроле над сознанием.",
        "copies": 2,
        "scenario": "queue",
    },
    {
        "title": "Мастер и Маргарита",
        "authors": ("Михаил Булгаков",),
        "genres": ("Фантастика",),
        "year": 1967,
        "publisher": "Художественная литература",
        "description": "Философско-религиозная фантастика о добре и зле.",
        "copies": 1,
        "scenario": "reserved",
    },
    {
        "title": "Преступление и наказание",
        "authors": ("Фома Достоевский",),
        "genres": ("Детектив",),
        "year": 1866,
        "publisher": "Эксмо",
        "description": "Психологический роман о преступлении и искуплении.",
        "copies": 2,
        "scenario": None,
    },
    {
        "title": "Робинзон Крузо",
        "authors": ("Дэниел Дефо",),
        "genres": ("Приключения",),
        "year": 1719,
        "publisher": "Премьер",
        "description": "Приключенческий роман о добродетели и выживании.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Гарри Поттер и философский камень",
        "authors": ("Джоан Роулинг",),
        "genres": ("Фэнтези",),
        "year": 1997,
        "publisher": "Bloomsbury",
        "description": "Первый год обучения в школе чародеев.",
        "copies": 3,
        "scenario": None,
    },
    {
        "title": "Властелин колец",
        "authors": ("Джон Толкин",),
        "genres": ("Фэнтези",),
        "year": 1954,
        "publisher": "Хобб",
        "description": "Эпическая сага о борьбе добра и зла.",
        "copies": 2,
        "scenario": None,
    },
    {
        "title": "Война миров",
        "authors": ("Герберт Уэллс",),
        "genres": ("Научная фантастика",),
        "year": 1898,
        "publisher": "АСТ",
        "description": "Пришествие марсиан к Земле.",
        "copies": 2,
        "scenario": None,
    },
    {
        "title": "Мёртвые души",
        "authors": ("Николай Гоголь",),
        "genres": ("Роман",),
        "year": 1842,
        "publisher": "Захаров",
        "description": "Русская проза о душе и служении.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Война и мир",
        "authors": ("Лев Толстой",),
        "genres": ("История",),
        "year": 1869,
        "publisher": "Художественная литература",
        "description": "Исторический роман о войне 1812 года.",
        "copies": 2,
        "scenario": None,
    },
    {
        "title": "Оно",
        "authors": ("Стивен Кинг",),
        "genres": ("Фантастика",),
        "year": 1986,
        "publisher": "Дерри Бук",
        "description": "Дети борются с культовой силой.",
        "copies": 2,
        "scenario": None,
    },
    {
        "title": "Дозоры",
        "authors": ("Стивен Кинг",),
        "genres": ("Фантастика",),
        "year": 1977,
        "publisher": "Дерри Бук",
        "description": "Современный ужас в маленьком городке.",
        "copies": 2,
        "scenario": None,
    },
    {
        "title": "Анна Каренина",
        "authors": ("Лев Толстой",),
        "genres": ("Роман",),
        "year": 1877,
        "publisher": "Художественная литература",
        "description": "Литературный классик о любви и обществе.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Фауст",
        "authors": ("Герман Гёте",),
        "genres": ("Роман",),
        "year": 1772,
        "publisher": "Художественная литература",
        "description": "Многовековая трагедия учёбы и власти.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Кэрри",
        "authors": ("Стивен Кинг",),
        "genres": ("Фэнтези",),
        "year": 1974,
        "publisher": "Дерри Бук",
        "description": "Первая книга эпопеи ужасов.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Гад",
        "authors": ("Стивен Кинг",),
        "genres": ("Фэнтези",),
        "year": 1979,
        "publisher": "Дерри Бук",
        "description": "Дети против древнего существа.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Секретный клад",
        "authors": ("Джоан Роулинг",),
        "genres": ("Фэнтези",),
        "year": 1998,
        "publisher": "Bloomsbury",
        "description": "Волшебный мир и тайна старого клада.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Ночь и туман",
        "authors": ("Николай Гоголь",),
        "genres": ("Мистика",),
        "year": 1845,
        "publisher": "Эксмо",
        "description": "Ночное похищение и духовный поиск.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Отцы и дети",
        "authors": ("Лев Толстой",),
        "genres": ("Роман",),
        "year": 1862,
        "publisher": "Художественная литература",
        "description": "Противостояние поколений в русской деревне.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Трагик",
        "authors": ("Герман Гёте",),
        "genres": ("Роман",),
        "year": 1789,
        "publisher": "Художественная литература",
        "description": "Лирика о тёмных сторонах жизни.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Семнадцать мгновений весны",
        "authors": ("Михаил Булгаков",),
        "genres": ("История",),
        "year": 1973,
        "publisher": "Художественная литература",
        "description": "Историческая сага о партизанском движении.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Идиот",
        "authors": ("Фома Достоевский",),
        "genres": ("Роман",),
        "year": 1872,
        "publisher": "Художественная литература",
        "description": "Психологическая проза о нравственном выборе.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Гарри Поттер и тайная комната",
        "authors": ("Джоан Роулинг",),
        "genres": ("Фэнтези",),
        "year": 1998,
        "publisher": "Bloomsbury",
        "description": "Волшебная школа и тайна прошлого.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Тёмная башня",
        "authors": ("Стивен Кинг",),
        "genres": ("Фэнтези",),
        "year": 1977,
        "publisher": "Дерри Бук",
        "description": "Эпопея о борьбе с древним злом.",
        "copies": 1,
        "scenario": None,
    },
    {
        "title": "Сияние",
        "authors": ("Стивен Кинг",),
        "genres": ("Фантастика",),
        "year": 1977,
        "publisher": "Дерри Бук",
        "description": "Эксперименты над сознанием и технологией.",
        "copies": 1,
        "scenario": None,
    },
]

# (reader_index, book_index, copy_number, status, issued_days_ago, returned_days_ago)
DEMO_ISSUES = [
    # Сценарий «451 градус по Фаренгейту»: оба экземпляра уже выданы.
    (1, 1, 1, "OVERDUE", 45, None),
    (2, 1, 2, "ISSUED", 5, None),
    # Сценарий «Мастер и Маргарита»: читатель вернул книгу, она зарезервирована.
    (0, 2, 1, "RETURNED", 35, 14),
    # Обычные выдачи библиотеки.
    (3, 3, 1, "RETURNED", 25, 5),
    (1, 3, 2, "ISSUED", 8, None),
    (5, 5, 1, "LOST", 12, None),
    (6, 5, 2, "ISSUED", 3, None),
    (1, 4, 1, "RETURNED", 50, 38),
    (3, 5, 3, "RETURNED", 22, 12),
    (4, 6, 1, "ISSUED", 6, None),
    (5, 6, 2, "RETURNED", 40, 30),
    (0, 7, 1, "OVERDUE", 55, None),
    (2, 7, 2, "RETURNED", 33, 20),
    (1, 8, 1, "LOST", 15, None),
    (3, 9, 1, "RETURNED", 28, 18),
    (4, 9, 2, "OVERDUE", 19, None),
    (5, 10, 1, "ISSUED", 2, None),
    (6, 10, 2, "RETURNED", 44, 25),
    (0, 11, 1, "ISSUED", 9, None),
    (1, 11, 2, "RETURNED", 55, 42),
    (2, 12, 1, "OVERDUE", 27, None),
    (3, 13, 1, "ISSUED", 7, None),
    (4, 14, 1, "RETURNED", 36, 25),
    (5, 15, 1, "OVERDUE", 18, None),
    (6, 16, 1, "LOST", 10, None),
    (0, 17, 1, "RETURNED", 48, 33),
    (1, 18, 1, "ISSUED", 4, None),
    (2, 19, 1, "RETURNED", 29, 16),
    (3, 20, 1, "OVERDUE", 21, None),
    (4, 21, 1, "ISSUED", 11, None),
    (5, 22, 1, "RETURNED", 52, 39),
    (6, 23, 1, "OVERDUE", 25, None),
    (0, 24, 1, "ISSUED", 6, None),
]


class Command(BaseCommand):
    help = "Load demo data: books, copies, readers, issues and reservations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Clear all library data and load demo data from scratch.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            with transaction.atomic():
                self.clear_library_data()
            self.stdout.write(self.style.WARNING("Demo data reset: library data cleared."))
        self._load_demo_data()
        self._print_summary()

    # ---------- Очистка данных ----------

    def clear_library_data(self):
        """Удалить все данные приложения библиотеки в одной транзакции."""
        models.ActionLog.objects.all().delete()
        models.Reservation.objects.all().delete()
        models.Issue.objects.all().delete()
        models.BookCopy.objects.all().delete()
        models.BookGenre.objects.all().delete()
        models.BookAuthor.objects.all().delete()
        models.Genre.objects.all().delete()
        models.Author.objects.all().delete()
        models.Book.objects.all().delete()
        models.Reader.objects.all().delete()

    # ---------- Загрузка демо-набора ----------

    def _load_demo_data(self):
        librarian_group, _ = Group.objects.get_or_create(name=roles.LIBRARIAN_ROLE)
        reader_group, _ = Group.objects.get_or_create(name=roles.READER_ROLE)
        admin_group, _ = Group.objects.get_or_create(name=roles.ADMIN_ROLE)

        admin = models.Reader.objects.update_or_create(
            email=ADMIN_EMAIL,
            defaults={
                "full_name": "Администратор",
                "status": models.Reader.Status.ACTIVE,
            },
        )[0]
        admin.set_password(ADMIN_PASSWORD)
        admin.groups.add(admin_group)

        librarian = models.Reader.objects.update_or_create(
            email=LIBRARIAN_EMAIL,
            defaults={
                "full_name": "Библиотекарь",
                "status": models.Reader.Status.ACTIVE,
            },
        )[0]
        librarian.set_password(LIBRARIAN_PASSWORD)
        librarian.groups.add(librarian_group)

        readers = []
        for index in range(DEMO_READERS_COUNT):
            reader, _created = models.Reader.objects.update_or_create(
                email=f"reader{index}@library.local",
                defaults={
                    "full_name": f"Читатель {index + 1}",
                    "status": (
                        models.Reader.Status.BLOCKED
                        if index == BLOCKED_READER_INDEX
                        else models.Reader.Status.ACTIVE
                    ),
                },
            )
            reader.set_password(READER_PASSWORD)
            reader.groups.add(reader_group)
            readers.append(reader)

        authors = {}
        for full_name in DEMO_AUTHORS:
            author, _created = models.Author.objects.update_or_create(full_name=full_name, defaults={})
            authors[full_name] = author

        genres = {}
        for name in DEMO_GENRES:
            genre, _created = models.Genre.objects.get_or_create(name=name)
            genres[name] = genre

        self._books_by_index = {}
        self._copies_by_index = {}
        for index, spec in enumerate(DEMO_BOOKS, start=1):
            book, _created = models.Book.objects.update_or_create(
                isbn=_demo_isbn(index),
                defaults={
                    "title": spec["title"],
                    "description": spec.get("description") or "",
                    "publication_year": spec["year"],
                    "publisher": spec.get("publisher") or "",
                    "cover_url": _demo_cover_url(_demo_isbn(index)),
                },
            )
            book.authors.set([authors[name] for name in spec["authors"]])
            book.genres.set([genres[name] for name in spec["genres"]])
            copies = {}
            for copy_number in range(1, spec["copies"] + 1):
                inventory_number = f"DEMO-{index:03d}-{copy_number}"
                copy, _created = models.BookCopy.objects.update_or_create(
                    book=book,
                    inventory_number=inventory_number,
                    defaults={"status": models.BookCopy.Status.AVAILABLE},
                )
                copies[copy_number] = copy
            self._books_by_index[index] = (book, spec)
            self._copies_by_index[index] = copies

        self._librarian = librarian
        self._readers = readers

        self._ensure_issues()
        self._ensure_reservations()

    # ---------- Выдачи ----------

    def _ensure_issues(self):
        for reader_index, book_index, copy_number, status, issued_days_ago, returned_days_ago in DEMO_ISSUES:
            book, _spec = self._books_by_index[book_index]
            copy = self._copies_by_index[book_index][copy_number]
            reader = self._readers[reader_index]
            issued_at = timezone.now() - timedelta(days=issued_days_ago)
            returned_at = issued_at + timedelta(days=returned_days_ago) if returned_days_ago else None
            self._ensure_issue(reader, copy, status, issued_at, returned_at)

    def _ensure_issue(self, reader, copy, status, issued_at, returned_at):
        """Создать выдачу через сервисный слой или согласовать уже существующую."""
        issue = models.Issue.objects.filter(copy=copy, reader=reader).first()
        if issue is None:
            issue = models.Issue.objects.create(
                reader=reader,
                copy=copy,
                issued_at=issued_at,
                due_at=issued_at + LOAN_PERIOD,
                returned_at=returned_at,
                status=models.Issue.Status.ISSUED,
            )
            services.change_status(copy, models.BookCopy.Status.ISSUED, user=self._librarian)
            if status != models.Issue.Status.ISSUED:
                services.change_status(issue, status, user=self._librarian, returned_at=returned_at)
                if status == models.Issue.Status.RETURNED:
                    services.change_status(copy, models.BookCopy.Status.AVAILABLE, user=self._librarian)
                elif status == models.Issue.Status.LOST:
                    services.change_status(copy, models.BookCopy.Status.LOST, user=self._librarian)
            return issue
        if issue.status != status or issue.returned_at != returned_at:
            issue.status = status
            issue.returned_at = returned_at
            issue.save(update_fields=["status", "returned_at"])
        return issue

    # ---------- Бронирования и очереди ----------

    def _get_or_create_reservation(self, reader, book, defaults):
        reservation = models.Reservation.objects.filter(reader=reader, book=book).first()
        if reservation is None:
            return models.Reservation.objects.create(reader=reader, book=book, **defaults)
        for field, value in defaults.items():
            setattr(reservation, field, value)
        reservation.save(update_fields=list(defaults))
        return reservation

    def _ensure_reservation_active(self, reader, book, copy):
        reservation = self._get_or_create_reservation(
            reader,
            book,
            defaults={
                "status": models.Reservation.Status.PENDING,
                "queue_date": timezone.now(),
                "expires_at": timezone.now() + RESERVATION_PERIOD,
                "copy": None,
                "active_slot": 1,
                "cancelled_at": None,
            },
        )
        if reservation.status != models.Reservation.Status.ACTIVE:
            services.change_status(
                reservation,
                models.Reservation.Status.ACTIVE,
                user=self._librarian,
                copy=copy,
                expires_at=timezone.now() + RESERVATION_PERIOD,
            )
            services.change_status(copy, models.BookCopy.Status.RESERVED, user=self._librarian)
        return reservation

    def _ensure_reservation_cancelled(self, reader, book):
        reservation = self._get_or_create_reservation(
            reader,
            book,
            defaults={
                "status": models.Reservation.Status.PENDING,
                "queue_date": timezone.now(),
                "expires_at": timezone.now() + RESERVATION_PERIOD,
                "copy": None,
                "active_slot": 1,
                "cancelled_at": None,
            },
        )
        if reservation.status in (
            models.Reservation.Status.PENDING,
            models.Reservation.Status.ACTIVE,
        ):
            reservation, _copy = services.cancel_reservation(reservation.pk, user=self._librarian)
            # Отмена регистрируется исторически (за последний месяц) для отчёта.
            reservation.cancelled_at = timezone.now() - timedelta(days=30)
            reservation.save(update_fields=["cancelled_at"])

    def _ensure_reservation_expired(self, reader, book, copy):
        reservation = self._get_or_create_reservation(
            reader,
            book,
            defaults={
                "status": models.Reservation.Status.PENDING,
                "queue_date": timezone.now(),
                "expires_at": timezone.now() + RESERVATION_PERIOD,
                "copy": None,
                "active_slot": 1,
                "cancelled_at": None,
            },
        )
        if reservation.status != models.Reservation.Status.ACTIVE:
            services.change_status(
                reservation,
                models.Reservation.Status.ACTIVE,
                user=self._librarian,
                copy=copy,
                expires_at=timezone.now() - timedelta(days=20),
            )
        services.expire_reservations(book.pk)

    def _ensure_reservations(self):
        # Сценарий очереди: «451 градус по Фаренгейту» — все экземпляры выданы,
        # в очереди ожидания находятся три читателя.
        queue_book = self._books_by_index[1][0]
        for reader_index in (3, 4, 5):
            self._get_or_create_reservation(
                self._readers[reader_index],
                queue_book,
                defaults={
                    "status": models.Reservation.Status.PENDING,
                    "queue_date": timezone.now(),
                    "expires_at": timezone.now() + RESERVATION_PERIOD,
                    "copy": None,
                    "active_slot": 1,
                    "cancelled_at": None,
                },
            )

        # Сценарий резерва: «Мастер и Маргарита» — копия зарезервирована
        # и выдана читателю через активную бронь.
        reserved_book = self._books_by_index[2][0]
        reserved_copy = self._copies_by_index[2][1]
        self._ensure_reservation_active(self._readers[0], reserved_book, reserved_copy)

        # Отменённая бронь за последний месяц.
        cancelled_book = self._books_by_index[3][0]
        self._ensure_reservation_cancelled(self._readers[2], cancelled_book)

        # Истёкшая бронь за последний месяц.
        expired_book = self._books_by_index[7][0]
        expired_copy = self._copies_by_index[7][2]
        self._ensure_reservation_expired(self._readers[6], expired_book, expired_copy)

    # ---------- Сводка ----------

    def _print_summary(self):
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data loaded: {models.Book.objects.count()} books, "
                f"{models.BookCopy.objects.count()} copies, "
                f"{models.Issue.objects.count()} issues, "
                f"{models.Reservation.objects.count()} reservations, "
                f"{models.Reader.objects.count()} readers."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Demo logins: admin@library.local / AdminPass123, "
                "librarian@library.local / LibrarianPass123, "
                "reader0..7@library.local / ReaderPass123."
            )
        )
