from django.contrib import admin

from library.models import Author, Book, BookAuthor, BookGenre, BookCopy, Genre, Issue, Reader, Reservation


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name")
    search_fields = ("full_name",)


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "isbn", "publication_year", "publisher")
    search_fields = ("title", "isbn")


@admin.register(BookAuthor)
class BookAuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "book_id", "author_id")


@admin.register(BookGenre)
class BookGenreAdmin(admin.ModelAdmin):
    list_display = ("id", "book_id", "genre_id")


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ("id", "book_id", "inventory_number", "status")
    list_filter = ("status", "book_id")
    search_fields = ("inventory_number",)


@admin.register(Reader)
class ReaderAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "full_name", "phone", "status", "is_staff", "is_superuser", "date_joined")
    list_filter = ("status", "is_staff", "is_superuser")
    search_fields = ("email", "full_name")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("id", "reader_id", "copy_id", "issued_at", "due_at", "returned_at", "status")
    list_filter = ("status",)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "reader_id", "book_id", "status", "queue_date", "expires_at")
    list_filter = ("status",)
