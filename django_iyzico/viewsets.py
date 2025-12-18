"""
Django REST Framework viewsets for django-iyzico.

Optional module - only available if DRF is installed.
Provides viewsets for exposing payment data through REST APIs.
"""

try:
    from rest_framework import viewsets, permissions, filters, status
    from rest_framework.decorators import action
    from rest_framework.response import Response

    HAS_DRF = True
except ImportError:
    HAS_DRF = False
    # Create dummy classes
    class viewsets:  # type: ignore
        class ReadOnlyModelViewSet:
            pass


try:
    from django_filters.rest_framework import DjangoFilterBackend

    HAS_DJANGO_FILTERS = True
except ImportError:
    HAS_DJANGO_FILTERS = False
    DjangoFilterBackend = None  # type: ignore


if HAS_DRF:
    from decimal import Decimal
    from django.core.exceptions import ValidationError as DjangoValidationError

    from .serializers import (
        IyzicoPaymentSerializer,
        RefundRequestSerializer,
        PaymentFilterSerializer,
    )
    from .models import PaymentStatus
    from .exceptions import PaymentError
    from .utils import get_client_ip

    class IyzicoPaymentViewSet(viewsets.ReadOnlyModelViewSet):
        """
        Read-only viewset for payment transactions.

        Provides list and retrieve endpoints with filtering, searching, and ordering.

        Features:
        - List all payments (with pagination)
        - Retrieve single payment
        - Filter by status, currency, buyer email
        - Search by payment ID, conversation ID, buyer email
        - Order by created_at, amount, updated_at

        Usage:
            # In your urls.py
            from rest_framework.routers import DefaultRouter
            from django_iyzico.viewsets import IyzicoPaymentViewSet
            from myapp.models import Order

            router = DefaultRouter()

            # Create a custom viewset for your model
            class OrderPaymentViewSet(IyzicoPaymentViewSet):
                queryset = Order.objects.all()

            router.register(r'payments', OrderPaymentViewSet, basename='payment')

            urlpatterns = [
                path('api/', include(router.urls)),
            ]
        """

        serializer_class = IyzicoPaymentSerializer
        permission_classes = [permissions.IsAuthenticated]

        # Filtering
        filter_backends = [filters.OrderingFilter, filters.SearchFilter]
        if HAS_DJANGO_FILTERS and DjangoFilterBackend:
            filter_backends.insert(0, DjangoFilterBackend)

        filterset_fields = ["status", "currency", "buyer_email"]
        search_fields = ["payment_id", "conversation_id", "buyer_email", "buyer_name"]
        ordering_fields = ["created_at", "amount", "paid_amount", "updated_at"]
        ordering = ["-created_at"]

        def get_queryset(self):
            """
            Get queryset for this viewset.

            Override this method or set queryset attribute in your subclass.
            """
            if not hasattr(self, "queryset") or self.queryset is None:
                raise NotImplementedError(
                    "You must set 'queryset' attribute or override get_queryset() method. "
                    "Example: queryset = Order.objects.all()"
                )
            return self.queryset

        def filter_queryset(self, queryset):
            """Apply additional filters."""
            queryset = super().filter_queryset(queryset)

            # Apply custom filters from query params
            serializer = PaymentFilterSerializer(data=self.request.query_params)
            if serializer.is_valid():
                filters = {}
                data = serializer.validated_data

                # Amount range
                if "min_amount" in data:
                    filters["amount__gte"] = data["min_amount"]
                if "max_amount" in data:
                    filters["amount__lte"] = data["max_amount"]

                # Date range
                if "created_after" in data:
                    filters["created_at__gte"] = data["created_after"]
                if "created_before" in data:
                    filters["created_at__lte"] = data["created_before"]

                queryset = queryset.filter(**filters)

            return queryset

        @action(detail=False, methods=["get"])
        def successful(self, request):
            """
            List only successful payments.

            GET /api/payments/successful/
            """
            queryset = self.filter_queryset(self.get_queryset()).successful()
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        @action(detail=False, methods=["get"])
        def failed(self, request):
            """
            List only failed payments.

            GET /api/payments/failed/
            """
            queryset = self.filter_queryset(self.get_queryset()).failed()
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        @action(detail=False, methods=["get"])
        def pending(self, request):
            """
            List only pending payments.

            GET /api/payments/pending/
            """
            queryset = self.filter_queryset(self.get_queryset()).pending()
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        @action(detail=False, methods=["get"])
        def stats(self, request):
            """
            Get payment statistics.

            GET /api/payments/stats/

            Returns:
                {
                    "total": 100,
                    "successful": 80,
                    "failed": 15,
                    "pending": 5,
                    "total_amount": "10000.00",
                    "successful_amount": "8500.00"
                }
            """
            from django.db.models import Count, Sum, Q

            queryset = self.filter_queryset(self.get_queryset())

            stats = queryset.aggregate(
                total=Count("id"),
                successful=Count("id", filter=Q(status=PaymentStatus.SUCCESS)),
                failed=Count("id", filter=Q(status=PaymentStatus.FAILED)),
                pending=Count("id", filter=Q(
                    status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING]
                )),
                total_amount=Sum("amount"),
                successful_amount=Sum(
                    "amount", filter=Q(status=PaymentStatus.SUCCESS)
                ),
            )

            # Convert Decimals to strings for JSON serialization
            if stats["total_amount"]:
                stats["total_amount"] = str(stats["total_amount"])
            if stats["successful_amount"]:
                stats["successful_amount"] = str(stats["successful_amount"])

            return Response(stats)

    class IyzicoPaymentManagementViewSet(viewsets.ReadOnlyModelViewSet):
        """
        Extended viewset with refund management capabilities.

        Extends IyzicoPaymentViewSet with refund action for admins.

        Usage:
            class OrderPaymentViewSet(IyzicoPaymentManagementViewSet):
                queryset = Order.objects.all()
                permission_classes = [permissions.IsAdminUser]
        """

        serializer_class = IyzicoPaymentSerializer
        permission_classes = [permissions.IsAdminUser]

        # Inherit all features from IyzicoPaymentViewSet
        filter_backends = IyzicoPaymentViewSet.filter_backends
        filterset_fields = IyzicoPaymentViewSet.filterset_fields
        search_fields = IyzicoPaymentViewSet.search_fields
        ordering_fields = IyzicoPaymentViewSet.ordering_fields
        ordering = IyzicoPaymentViewSet.ordering

        def get_queryset(self):
            """Get queryset - must be overridden."""
            if not hasattr(self, "queryset") or self.queryset is None:
                raise NotImplementedError(
                    "You must set 'queryset' attribute or override get_queryset() method"
                )
            return self.queryset

        @action(detail=True, methods=["post"])
        def refund(self, request, pk=None):
            """
            Process refund for a payment.

            POST /api/payments/{id}/refund/
            {
                "amount": "50.00",  # Optional, omit for full refund
                "reason": "Customer request"  # Optional
            }

            Returns:
                {
                    "success": true,
                    "message": "Refund processed successfully",
                    "refund_id": "...",
                    "amount": "50.00"
                }
            """
            payment = self.get_object()

            # Validate request data
            serializer = RefundRequestSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            amount = serializer.validated_data.get("amount")
            reason = serializer.validated_data.get("reason")

            # Check if payment can be refunded
            if not payment.can_be_refunded():
                return Response(
                    {
                        "success": False,
                        "error": "Payment cannot be refunded",
                        "status": payment.status,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get client IP for audit trail (uses centralized function that respects settings)
            ip_address = get_client_ip(request) or '127.0.0.1'

            # Process refund
            try:
                refund_response = payment.process_refund(
                    ip_address=ip_address,
                    amount=amount,
                    reason=reason,
                )

                if refund_response.is_successful():
                    return Response(
                        {
                            "success": True,
                            "message": "Refund processed successfully",
                            "refund_id": refund_response.refund_id,
                            "payment_id": refund_response.payment_id,
                            "amount": str(refund_response.price) if refund_response.price else None,
                            "currency": refund_response.currency,
                        },
                        status=status.HTTP_200_OK,
                    )
                else:
                    return Response(
                        {
                            "success": False,
                            "error": refund_response.error_message,
                            "error_code": refund_response.error_code,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            except (DjangoValidationError, PaymentError) as e:
                return Response(
                    {"success": False, "error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                return Response(
                    {"success": False, "error": f"Refund processing failed: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


else:
    # Provide helpful error messages if DRF is not installed
    def __getattr__(name):
        """Raise helpful error when trying to use DRF viewsets without DRF."""
        raise ImportError(
            f"Cannot use {name} because Django REST Framework is not installed. "
            "Install it with: pip install djangorestframework"
        )
