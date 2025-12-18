"""
URL configuration for shop API (Django REST Framework).
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

# Create router for ViewSets
router = DefaultRouter()
router.register(r'products', api_views.ProductViewSet, basename='api-product')
router.register(r'orders', api_views.OrderViewSet, basename='api-order')

# API URL patterns
urlpatterns = [
    # Router URLs (ViewSets)
    path('', include(router.urls)),

    # Custom API endpoints
    path('payments/create/', api_views.create_payment, name='api-payment-create'),
    path('payments/stats/', api_views.payment_stats, name='api-payment-stats'),
    path('installments/options/', api_views.get_installment_options, name='api-installment-options'),
]
