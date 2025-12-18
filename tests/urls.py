"""URL configuration for tests."""

from django.urls import include, path

urlpatterns = [
    path("iyzico/", include("django_iyzico.urls")),
]
