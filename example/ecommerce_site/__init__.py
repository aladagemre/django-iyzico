"""
E-commerce site package with django-iyzico integration.
"""

# Import Celery app for Django integration
from .celery import app as celery_app

__all__ = ('celery_app',)
