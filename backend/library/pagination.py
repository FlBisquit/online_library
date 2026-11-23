"""Пагинация списков с поддержкой параметра `limit`."""
from rest_framework.pagination import PageNumberPagination


class CatalogPagination(PageNumberPagination):
    """Стандартная page-based пагинация с настраиваемым размером страницы."""

    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 100
