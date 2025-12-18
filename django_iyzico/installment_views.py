"""
Views for installment payment functionality.

Provides AJAX endpoints for fetching installment options
and processing installment payments.

Security Note:
    All installment views require authentication by default to prevent
    BIN enumeration attacks. Rate limiting is also applied as an
    additional security measure.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any

from django.core.cache import cache
from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required

from .installment_client import InstallmentClient
from .exceptions import IyzicoValidationException, IyzicoAPIException
from .utils import get_client_ip

logger = logging.getLogger(__name__)


def _check_rate_limit(request, cache_key_prefix: str, max_requests: int = 30, window_seconds: int = 60) -> bool:
    """
    Check if request is within rate limits.

    Args:
        request: HTTP request
        cache_key_prefix: Prefix for cache key
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Returns:
        True if within limits, False if exceeded
    """
    client_ip = get_client_ip(request)
    cache_key = f"{cache_key_prefix}_{client_ip}"
    request_count = cache.get(cache_key, 0)

    if request_count >= max_requests:
        return False

    cache.set(cache_key, request_count + 1, window_seconds)
    return True


class InstallmentOptionsView(LoginRequiredMixin, View):
    """
    AJAX view to fetch installment options for a card BIN and amount.

    Requires authentication to prevent BIN enumeration attacks.

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
    # Return JSON response for AJAX requests instead of redirect
    raise_exception = True

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


class BestInstallmentOptionsView(LoginRequiredMixin, View):
    """
    AJAX view to get best/recommended installment options.

    Requires authentication to prevent BIN enumeration attacks.

    Returns top installment options prioritizing 0% interest.

    Example request:
        GET /iyzico/installments/best/?bin=554960&amount=100.00&max=5&currency=TRY

    Query Parameters:
        bin: Card BIN (first 6 digits)
        amount: Payment amount
        max: Maximum number of options (default: 5, max: 20)
        currency: Currency code (TRY, USD, EUR, GBP) - defaults to TRY

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
    # Return JSON response for AJAX requests instead of redirect
    raise_exception = True

    def get(self, request, *args, **kwargs):
        """Handle GET request for best installment options."""
        try:
            # Get parameters
            bin_number = request.GET.get('bin', '').strip()
            amount_str = request.GET.get('amount', '').strip()
            # Currency parameter - defaults to TRY but can be overridden
            currency = request.GET.get('currency', 'TRY').strip().upper()
            # Validate currency (allow common currencies)
            valid_currencies = {'TRY', 'USD', 'EUR', 'GBP'}
            if currency not in valid_currencies:
                currency = 'TRY'

            # Safe int conversion with bounds
            try:
                max_options = int(request.GET.get('max', 5))
                max_options = max(1, min(max_options, 20))  # Bounded between 1 and 20
            except (ValueError, TypeError):
                max_options = 5

            # Validate
            if not bin_number or not amount_str:
                return JsonResponse({
                    'success': False,
                    'error': 'BIN and amount are required',
                }, status=400)

            # Safe Decimal conversion
            try:
                amount = Decimal(amount_str)
            except (InvalidOperation, ValueError):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid amount format',
                }, status=400)

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
                    currency=currency,
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


class ValidateInstallmentView(LoginRequiredMixin, View):
    """
    AJAX view to validate an installment selection.

    Requires authentication to prevent BIN enumeration attacks.

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
    # Return JSON response for AJAX requests instead of redirect
    raise_exception = True

    def post(self, request, *args, **kwargs):
        """Handle POST request to validate installment."""
        import json

        # Rate limiting as additional protection layer
        if not _check_rate_limit(request, 'installment_validate', max_requests=30, window_seconds=60):
            logger.warning(f"Rate limit exceeded for installment validation from IP {get_client_ip(request)}")
            return JsonResponse({
                'success': False,
                'error': 'Rate limit exceeded. Please try again later.',
            }, status=429)

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
            bin_number = data.get('bin', '').strip() if data.get('bin') else ''
            amount_str = data.get('amount', '').strip() if data.get('amount') else ''
            installment_number = data.get('installment')

            # Validate
            if not bin_number or not amount_str or not installment_number:
                return JsonResponse({
                    'success': False,
                    'error': 'BIN, amount, and installment are required',
                }, status=400)

            # Safe Decimal conversion
            try:
                amount = Decimal(amount_str)
            except (InvalidOperation, ValueError):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid amount format',
                }, status=400)

            # Safe int conversion
            try:
                installment_number = int(installment_number)
                if installment_number < 1 or installment_number > 36:
                    raise ValueError("Installment number out of range")
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid installment number',
                }, status=400)

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
@login_required
@require_http_methods(["GET"])
def get_installment_options(request):
    """
    Simple function-based view to get installment options.

    Requires authentication to prevent BIN enumeration attacks.

    Query parameters:
        - bin: Card BIN (first 6 digits)
        - amount: Payment amount

    Returns:
        JSON response with installment options
    """
    view = InstallmentOptionsView()
    view.request = request  # Set request for LoginRequiredMixin to access user
    return view.get(request)


# Optional: Django REST Framework ViewSet
try:
    from rest_framework import viewsets, status
    from rest_framework.decorators import action
    from rest_framework.response import Response
    from rest_framework.permissions import IsAuthenticated
    from rest_framework.throttling import UserRateThrottle

    class InstallmentRateThrottle(UserRateThrottle):
        """Rate throttle for installment endpoints to prevent BIN enumeration."""
        rate = '30/minute'

    class InstallmentViewSet(viewsets.ViewSet):
        """
        ViewSet for installment operations (DRF).

        Requires authentication to prevent BIN enumeration attacks.

        Endpoints:
            GET /installments/options/?bin=554960&amount=100.00
            GET /installments/best/?bin=554960&amount=100.00
            POST /installments/validate/
        """

        permission_classes = [IsAuthenticated]
        throttle_classes = [InstallmentRateThrottle]

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
            except (InvalidOperation, ValueError):
                return Response(
                    {'error': 'Invalid amount format'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
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
            # Currency parameter - defaults to TRY but can be overridden
            currency = (request.query_params.get('currency', 'TRY') or 'TRY').strip().upper()
            valid_currencies = {'TRY', 'USD', 'EUR', 'GBP'}
            if currency not in valid_currencies:
                currency = 'TRY'

            # Safe int conversion with bounds
            try:
                max_options = int(request.query_params.get('max', 5))
                max_options = max(1, min(max_options, 20))  # Bounded between 1 and 20
            except (ValueError, TypeError):
                max_options = 5

            if not bin_number or not amount_str:
                return Response(
                    {'error': 'BIN and amount are required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                amount = Decimal(amount_str)
            except (InvalidOperation, ValueError):
                return Response(
                    {'error': 'Invalid amount format'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
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
                        currency,
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

            # Safe Decimal conversion
            try:
                amount = Decimal(amount_str)
            except (InvalidOperation, ValueError):
                return Response(
                    {'error': 'Invalid amount format'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Safe int conversion with bounds
            try:
                installment_number = int(installment_number)
                if installment_number < 1 or installment_number > 36:
                    raise ValueError("Installment number out of range")
            except (ValueError, TypeError):
                return Response(
                    {'error': 'Invalid installment number'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
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
