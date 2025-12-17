"""URL configuration for tests."""

from django.urls import path, include

urlpatterns = [
    path("iyzico/", include("django_iyzico.urls")),
]
