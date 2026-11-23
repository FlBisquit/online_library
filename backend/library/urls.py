from django.urls import path
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.throttling import ScopedRateThrottle

TokenObtainPairView.throttling_class = ScopedRateThrottle
TokenObtainPairView.throttle_scope = "token"

from library import views

urlpatterns = [
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
    path("auth/register/", views.RegisterView.as_view(), name="auth-register"),
    path("auth/me/", views.MeView.as_view(), name="auth-me"),
    path("books/", views.BookListCreateView.as_view(), name="book-list"),
    path("books/<int:pk>/", views.BookDetailView.as_view(), name="book-detail"),
    path("books/<int:book_id>/copies/", views.BookCopyListCreateView.as_view(), name="book-copies"),
    path("books/<int:book_id>/queue/", views.BookQueueListCreateView.as_view(), name="book-queue"),
    path(
        "books/<int:book_id>/queue/<int:reader_id>/position/",
        views.BookQueuePositionView.as_view(),
        name="book-queue-position",
    ),
    path("readers/", views.ReaderListView.as_view(), name="reader-list"),
    path("readers/<int:pk>/", views.ReaderDetailView.as_view(), name="reader-detail"),
    path("readers/<int:pk>/issues/", views.ReaderIssuesView.as_view(), name="reader-issues"),
    path("issues/", views.IssueListView.as_view(), name="issue-list"),
    path("issues/<int:pk>/return/", views.IssueReturnView.as_view(), name="issue-return"),
    path("issues/<int:pk>/mark-lost/", views.IssueMarkLostView.as_view(), name="issue-mark-lost"),
    path("reservations/<int:pk>/", views.ReservationDetailView.as_view(), name="reservation-detail"),
    path("reservations/<int:pk>/cancel/", views.ReservationCancelView.as_view(), name="reservation-cancel"),
    path("reports/books/", views.BooksReportView.as_view(), name="report-books"),
    path("action-log/", views.ActionLogListView.as_view(), name="action-log-list"),
]
