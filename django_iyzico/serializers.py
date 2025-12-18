"""
Django REST Framework serializers for django-iyzico.

Optional module - only available if DRF is installed.
Provides serializers for exposing payment data through REST APIs.
"""

try:
    from rest_framework import serializers

    HAS_DRF = True
except ImportError:
    HAS_DRF = False

    # Create dummy base classes for graceful degradation
    class serializers:  # type: ignore
        class Serializer:
            pass

        class ModelSerializer:
            pass


if HAS_DRF:
    from .models import AbstractIyzicoPayment, PaymentStatus

    class IyzicoPaymentSerializer(serializers.ModelSerializer):
        """
        Serializer for Iyzico payment transactions.

        Read-only serializer that excludes sensitive data.
        Designed to be used with models that inherit from AbstractIyzicoPayment.

        Example:
            class Order(AbstractIyzicoPayment):
                # Your model fields
                pass

            class OrderSerializer(IyzicoPaymentSerializer):
                class Meta(IyzicoPaymentSerializer.Meta):
                    model = Order
                    fields = IyzicoPaymentSerializer.Meta.fields + ['your_field']
        """

        status_display = serializers.CharField(
            source="get_status_display",
            read_only=True,
            help_text="Human-readable payment status",
        )

        amount_display = serializers.CharField(
            source="get_amount_display",
            read_only=True,
            help_text="Formatted amount with currency (e.g., '100.00 TRY')",
        )

        paid_amount_display = serializers.CharField(
            source="get_paid_amount_display",
            read_only=True,
            help_text="Formatted paid amount with currency",
        )

        card_display = serializers.CharField(
            source="get_card_display",
            read_only=True,
            help_text="Masked card information (e.g., 'VISA **** 1234')",
        )

        buyer_full_name = serializers.CharField(
            source="get_buyer_full_name",
            read_only=True,
            help_text="Buyer's full name",
        )

        is_successful = serializers.SerializerMethodField(
            help_text="Whether payment was successful",
        )

        is_failed = serializers.SerializerMethodField(
            help_text="Whether payment failed",
        )

        is_pending = serializers.SerializerMethodField(
            help_text="Whether payment is pending",
        )

        can_be_refunded = serializers.SerializerMethodField(
            help_text="Whether payment can be refunded",
        )

        def get_is_successful(self, obj):
            return obj.is_successful()

        def get_is_failed(self, obj):
            return obj.is_failed()

        def get_is_pending(self, obj):
            return obj.is_pending()

        def get_can_be_refunded(self, obj):
            return obj.can_be_refunded()

        class Meta:
            model = AbstractIyzicoPayment
            fields = [
                # IDs
                "id",
                "payment_id",
                "conversation_id",
                # Status
                "status",
                "status_display",
                # Amounts
                "amount",
                "amount_display",
                "paid_amount",
                "paid_amount_display",
                "currency",
                "installment",
                # Card info (safe only)
                "card_display",
                "card_last_four_digits",
                "card_type",
                "card_association",
                "card_family",
                "card_bank_name",
                # Buyer info
                "buyer_email",
                "buyer_name",
                "buyer_surname",
                "buyer_full_name",
                # Error info
                "error_code",
                "error_message",
                # Timestamps
                "created_at",
                "updated_at",
                # Computed fields
                "is_successful",
                "is_failed",
                "is_pending",
                "can_be_refunded",
            ]
            read_only_fields = fields  # All fields are read-only

    class RefundRequestSerializer(serializers.Serializer):
        """
        Serializer for refund requests.

        Use this to validate refund request data before processing.

        Example:
            serializer = RefundRequestSerializer(data=request.data)
            if serializer.is_valid():
                payment.process_refund(
                    amount=serializer.validated_data.get('amount'),
                    reason=serializer.validated_data.get('reason')
                )
        """

        amount = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
            required=False,
            allow_null=True,
            help_text="Refund amount (omit for full refund)",
        )

        reason = serializers.CharField(
            max_length=500,
            required=False,
            allow_blank=True,
            help_text="Refund reason (optional)",
        )

        def validate_amount(self, value):
            """Validate refund amount."""
            if value is not None and value <= 0:
                raise serializers.ValidationError("Refund amount must be greater than zero")
            return value

    class PaymentFilterSerializer(serializers.Serializer):
        """
        Serializer for payment filtering parameters.

        Use this for query parameter validation in list views.

        Example:
            serializer = PaymentFilterSerializer(data=request.query_params)
            if serializer.is_valid():
                filters = serializer.validated_data
                queryset = Payment.objects.filter(**filters)
        """

        status = serializers.ChoiceField(
            choices=PaymentStatus.choices,
            required=False,
            help_text="Filter by payment status",
        )

        currency = serializers.CharField(
            max_length=3,
            required=False,
            help_text="Filter by currency code",
        )

        buyer_email = serializers.EmailField(
            required=False,
            help_text="Filter by buyer email",
        )

        min_amount = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
            required=False,
            help_text="Filter by minimum amount",
        )

        max_amount = serializers.DecimalField(
            max_digits=10,
            decimal_places=2,
            required=False,
            help_text="Filter by maximum amount",
        )

        created_after = serializers.DateTimeField(
            required=False,
            help_text="Filter payments created after this date",
        )

        created_before = serializers.DateTimeField(
            required=False,
            help_text="Filter payments created before this date",
        )

        def validate(self, data):
            """Cross-field validation."""
            # Validate amount range
            min_amount = data.get("min_amount")
            max_amount = data.get("max_amount")

            if min_amount and max_amount and min_amount > max_amount:
                raise serializers.ValidationError("min_amount cannot be greater than max_amount")

            # Validate date range
            created_after = data.get("created_after")
            created_before = data.get("created_before")

            if created_after and created_before and created_after > created_before:
                raise serializers.ValidationError(
                    "created_after cannot be later than created_before"
                )

            return data

else:
    # Provide helpful error messages if DRF is not installed
    def __getattr__(name):
        """Raise helpful error when trying to use DRF serializers without DRF."""
        raise ImportError(
            f"Cannot use {name} because Django REST Framework is not installed. "
            "Install it with: pip install djangorestframework"
        )
