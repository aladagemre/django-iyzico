"""
URL configuration for shop app (regular Django views).
"""

from django.urls import path
from . import views
from . import views_3ds

app_name = "shop"

urlpatterns = [
    # Product views
    path("products/", views.ProductListView.as_view(), name="product_list"),
    path("products/<int:pk>/", views.ProductDetailView.as_view(), name="product_detail"),
    # Checkout and payment (Direct payment)
    path("checkout/", views.checkout_view, name="checkout"),
    path("installment-options/", views.get_installment_options, name="installment_options"),
    path("order/success/<int:order_id>/", views.order_success_view, name="order_success"),
    # Checkout with 3D Secure (Redirect flow)
    path("checkout/3ds/", views_3ds.checkout_3ds_view, name="checkout_3ds"),
    path(
        "orders/<int:order_id>/success/",
        views_3ds.payment_success_3ds_view,
        name="payment_success_3ds",
    ),
    path("checkout/error/", views_3ds.payment_error_3ds_view, name="payment_error_3ds"),
    # Order management
    path("orders/", views.OrderListView.as_view(), name="order_list"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:order_id>/refund/", views.refund_request_view, name="refund_request"),
    # Subscriptions
    path("subscriptions/", views.subscription_plans_view, name="subscription_plans"),
    path("subscriptions/<int:plan_id>/subscribe/", views.subscribe_view, name="subscribe"),
    path(
        "subscriptions/<int:subscription_id>/",
        views.subscription_detail_view,
        name="subscription_detail",
    ),
]
