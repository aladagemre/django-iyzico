"""
Views for installment payment functionality.

Provides AJAX endpoints for fetching installment options
and processing installment payments.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any

from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from .installment_client import InstallmentClient
from .exceptions import IyzicoValidationException, IyzicoAPIException

logger = logging.getLogger(__name__)


class InstallmentOptionsView(View):
    """
    AJAX view to fetch installment options for a card BIN and amount.

    Returns JSON with available installment options from all banks.

    Example request:
        GET /iyzico/installments/?bin=554960&amount=100.00

    Example response:
        {
            "success": true,
            "banks": [
                {
                    "bank_name": "Akbank",
                    "bank_code": 62,
                    "installment_options": [
                        {
                            "installment_number": 1,
                            "base_price": "100.00",
                            "total_price": "100.00",
                            "monthly_price": "100.00",
                            "installment_rate": "0.00",
                            "total_fee": "0.00",
                            "is_zero_interest": true
                        },
                        ...
                    ]
                }
            ]
        }
    """

    def get(self, request, *args, **kwargs):
        """Handle GET request for installment options."""
        try:
            # Get parameters
            bin_number = request.GET.get('bin', '').strip()
            amount_str = request.GET.get('amount', '').strip()

            # Validate parameters
            if not bin_number:
                return JsonResponse({
                    'success': False,
                    'error': 'BIN number is required',
                }, status=400)

            if not amount_str:
                return JsonResponse({
                    'success': False,
                    'error': 'Amount is required',
                }, status=400)

            # Parse amount
            try:
                amount = Decimal(amount_str)
            except (InvalidOperation, ValueError):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid amount format',
                }, status=400)

            # Get installment options
            client = InstallmentClient()

            try:
                bank_options = client.get_installment_info(
                    bin_number=bin_number,
                    amount=amount,
                )
            except IyzicoValidationException as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e),
                }, status=400)
            except IyzicoAPIException as e:
                logger.error(f"Iyzico API error: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'Unable to fetch installment options. Please try again.',
                }, status=500)

            # Format response
            response_data = {
                'success': True,
                'banks': [bank.to_dict() for bank in bank_options],
            }

            return JsonResponse(response_data)

        except Exception as e:
            logger.exception(f"Unexpected error in InstallmentOptionsView: {e}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred',
            }, status=500)


class BestInstallmentOptionsView(View):
    """
    AJAX view to get best/recommended installment options.

    Returns top installment options prioritizing 0% interest.

    Example request:
        GET /iyzico/installments/best/?bin=554960&amount=100.00&max=5

    Example response:
        {
            "success": true,
            "options": [
                {
                    "installment_number": 3,
                    "monthly_price": "33.33",
                    "total_price": "100.00",
                    "is_zero_interest": true,
                    "display": "3x 33.33 TRY (0% Interest)"
                },
                ...
            ]
        }
    """

    def get(self, request, *args, **kwargs):
        """Handle GET request for best installment options."""
        try:
            # Get parameters
            bin_number = request.GET.get('bin', '').strip()
            amount_str = request.GET.get('amount', '').strip()
            max_options = int(request.GET.get('max', 5))

            # Validate
            if not bin_number or not amount_str:
                return JsonResponse({
                    'success': False,
                    'error': 'BIN and amount are required',
                }, status=400)

            amount = Decimal(amount_str)

            # Get best options
            client = InstallmentClient()

            try:
                best_options = client.get_best_installment_options(
                    bin_number=bin_number,
                    amount=amount,
                    max_options=max_options,
                )
            except (IyzicoValidationException, IyzicoAPIException) as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e),
                }, status=400)

            # Format response with display strings
            from .installment_utils import format_installment_display

            options_data = []
            for opt in best_options:
                option_dict = opt.to_dict()
                option_dict['display'] = format_installment_display(
                    installment_count=opt.installment_number,
                    monthly_payment=opt.monthly_price,
                    currency='TRY',
                    show_total=True,
                    total_with_fees=opt.total_price,
                    base_amount=opt.base_price,
                )
                options_data.append(option_dict)

            return JsonResponse({
                'success': True,
                'options': options_data,
            })

        except Exception as e:
            logger.exception(f"Error in BestInstallmentOptionsView: {e}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred',
            }, status=500)


class ValidateInstallmentView(View):
    """
    AJAX view to validate an installment selection.

    Verifies that the selected installment option is available
    for the given BIN and amount.

    Example request:
        POST /iyzico/installments/validate/
        {
            "bin": "554960",
            "amount": "100.00",
            "installment": 3
        }

    Example response:
        {
            "success": true,
            "valid": true,
            "option": {
                "installment_number": 3,
                "monthly_price": "34.33",
                "total_price": "103.00",
                "installment_rate": "3.00"
            }
        }
    """

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        """Disable CSRF for API endpoint."""
        return super().dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Handle POST request to validate installment."""
        import json

        try:
            # Parse JSON body
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid JSON',
                }, status=400)

            # Get parameters
            bin_number = data.get('bin', '').strip()
            amount_str = data.get('amount', '').strip()
            installment_number = data.get('installment')

            # Validate
            if not bin_number or not amount_str or not installment_number:
                return JsonResponse({
                    'success': False,
                    'error': 'BIN, amount, and installment are required',
                }, status=400)

            amount = Decimal(amount_str)
            installment_number = int(installment_number)

            # Validate installment option
            client = InstallmentClient()

            option = client.validate_installment_option(
                bin_number=bin_number,
                amount=amount,
                installment_number=installment_number,
            )

            if option:
                return JsonResponse({
                    'success': True,
                    'valid': True,
                    'option': option.to_dict(),
                })
            else:
                return JsonResponse({
                    'success': True,
                    'valid': False,
                    'message': 'Installment option not available for this card',
                })

        except Exception as e:
            logger.exception(f"Error in ValidateInstallmentView: {e}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred',
            }, status=500)


# Function-based view for simple use cases
@require_http_methods(["GET"])
def get_installment_options(request):
    """
    Simple function-based view to get installment options.

    Query parameters:
        - bin: Card BIN (first 6 digits)
        - amount: Payment amount

    Returns:
        JSON response with installment options
    """
    view = InstallmentOptionsView()
    return view.get(request)


# Optional: Django REST Framework ViewSet
try:
    from rest_framework import viewsets, status
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from rest_framework.permissions import AllowAny

    class InstallmentViewSet(viewsets.ViewSet):
        """
        ViewSet for installment operations (DRF).

        Endpoints:
            GET /installments/options/?bin=554960&amount=100.00
            GET /installments/best/?bin=554960&amount=100.00
            POST /installments/validate/
        """

        permission_classes = [AllowAny]

        @action(detail=False, methods=['get'])
        def options(self, request):
            """Get all installment options."""
            bin_number = request.query_params.get('bin')
            amount_str = request.query_params.get('amount')

            if not bin_number or not amount_str:
                return Response(
                    {'error': 'BIN and amount are required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                amount = Decimal(amount_str)
                client = InstallmentClient()
                bank_options = client.get_installment_info(bin_number, amount)

                return Response({
                    'banks': [bank.to_dict() for bank in bank_options],
                })

            except (IyzicoValidationException, IyzicoAPIException) as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except Exception as e:
                logger.exception(f"Error getting installment options: {e}")
                return Response(
                    {'error': 'An unexpected error occurred'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        @action(detail=False, methods=['get'])
        def best(self, request):
            """Get best installment options."""
            bin_number = request.query_params.get('bin')
            amount_str = request.query_params.get('amount')
            max_options = int(request.query_params.get('max', 5))

            if not bin_number or not amount_str:
                return Response(
                    {'error': 'BIN and amount are required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                amount = Decimal(amount_str)
                client = InstallmentClient()
                best_options = client.get_best_installment_options(
                    bin_number, amount, max_options
                )

                from .installment_utils import format_installment_display

                options_data = []
                for opt in best_options:
                    option_dict = opt.to_dict()
                    option_dict['display'] = format_installment_display(
                        opt.installment_number,
                        opt.monthly_price,
                        'TRY',
                        True,
                        opt.total_price,
                        opt.base_price,
                    )
                    options_data.append(option_dict)

                return Response({'options': options_data})

            except Exception as e:
                logger.exception(f"Error getting best options: {e}")
                return Response(
                    {'error': 'An unexpected error occurred'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        @action(detail=False, methods=['post'])
        def validate(self, request):
            """Validate installment selection."""
            bin_number = request.data.get('bin')
            amount_str = request.data.get('amount')
            installment_number = request.data.get('installment')

            if not all([bin_number, amount_str, installment_number]):
                return Response(
                    {'error': 'BIN, amount, and installment are required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                amount = Decimal(amount_str)
                installment_number = int(installment_number)

                client = InstallmentClient()
                option = client.validate_installment_option(
                    bin_number, amount, installment_number
                )

                if option:
                    return Response({
                        'valid': True,
                        'option': option.to_dict(),
                    })
                else:
                    return Response({
                        'valid': False,
                        'message': 'Installment option not available',
                    })

            except Exception as e:
                logger.exception(f"Error validating installment: {e}")
                return Response(
                    {'error': 'An unexpected error occurred'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

except ImportError:
    # DRF not installed, skip viewset
    InstallmentViewSet = None
