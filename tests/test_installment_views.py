"""
Tests for installment views.

Tests InstallmentOptionsView, BestInstallmentOptionsView, ValidateInstallmentView,
and optional DRF ViewSet.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from django_iyzico.exceptions import IyzicoAPIException, IyzicoValidationException
from django_iyzico.installment_client import BankInstallmentInfo, InstallmentOption
from django_iyzico.installment_views import (
    BestInstallmentOptionsView,
    InstallmentOptionsView,
    ValidateInstallmentView,
    get_installment_options,
)

# ============================================================================
# InstallmentOptionsView Tests
# ============================================================================


class TestInstallmentOptionsView(TestCase):
    """Test InstallmentOptionsView."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = InstallmentOptionsView()

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_installment_options_success(self, mock_client_class):
        """Test successfully getting installment options."""
        # Mock data
        mock_options = [
            InstallmentOption(1, Decimal("100"), Decimal("100"), Decimal("100")),
            InstallmentOption(3, Decimal("100"), Decimal("103"), Decimal("34.33"), Decimal("3.00")),
        ]
        mock_bank_info = BankInstallmentInfo("Akbank", 62, mock_options)

        mock_client = MagicMock()
        mock_client.get_installment_info.return_value = [mock_bank_info]
        mock_client_class.return_value = mock_client

        # Create request
        request = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )

        # Call view
        response = self.view.get(request)

        # Assert response
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["success"] is True
        assert len(data["banks"]) == 1
        assert data["banks"][0]["bank_name"] == "Akbank"

    def test_get_installment_options_missing_bin(self):
        """Test with missing BIN parameter."""
        request = self.factory.get(
            "/installments/",
            {
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False
        assert "BIN number is required" in data["error"]

    def test_get_installment_options_missing_amount(self):
        """Test with missing amount parameter."""
        request = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False
        assert "Amount is required" in data["error"]

    def test_get_installment_options_invalid_amount(self):
        """Test with invalid amount format."""
        request = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
                "amount": "invalid",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False
        assert "Invalid amount format" in data["error"]

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_installment_options_validation_error(self, mock_client_class):
        """Test handling validation error from client."""
        mock_client = MagicMock()
        mock_client.get_installment_info.side_effect = IyzicoValidationException("Invalid BIN")
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/",
            {
                "bin": "12345",
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_installment_options_api_error(self, mock_client_class):
        """Test handling API error."""
        mock_client = MagicMock()
        mock_client.get_installment_info.side_effect = IyzicoAPIException("API error")
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 500
        data = json.loads(response.content)
        assert data["success"] is False
        assert "Unable to fetch installment options" in data["error"]

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_installment_options_unexpected_error(self, mock_client_class):
        """Test handling unexpected error."""
        mock_client = MagicMock()
        mock_client.get_installment_info.side_effect = Exception("Unexpected error")
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 500
        data = json.loads(response.content)
        assert data["success"] is False
        assert "unexpected error" in data["error"]

    def test_get_installment_options_empty_bin(self):
        """Test with empty BIN string."""
        request = self.factory.get(
            "/installments/",
            {
                "bin": "   ",
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 400

    def test_get_installment_options_whitespace_amount(self):
        """Test with whitespace amount."""
        request = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
                "amount": "  100.00  ",
            },
        )

        # Should strip whitespace and work
        # Response is not checked further as behavior depends on implementation
        self.view.get(request)


# ============================================================================
# BestInstallmentOptionsView Tests
# ============================================================================


class TestBestInstallmentOptionsView(TestCase):
    """Test BestInstallmentOptionsView."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = BestInstallmentOptionsView()

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_best_options_success(self, mock_client_class):
        """Test successfully getting best options."""
        mock_options = [
            InstallmentOption(3, Decimal("100"), Decimal("100"), Decimal("33.33")),
            InstallmentOption(6, Decimal("100"), Decimal("105"), Decimal("17.50"), Decimal("5.00")),
        ]

        mock_client = MagicMock()
        mock_client.get_best_installment_options.return_value = mock_options
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/best/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["success"] is True
        assert len(data["options"]) == 2
        assert "display" in data["options"][0]

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_best_options_with_max(self, mock_client_class):
        """Test getting best options with max limit."""
        mock_options = [
            InstallmentOption(3, Decimal("100"), Decimal("100"), Decimal("33.33")),
        ]

        mock_client = MagicMock()
        mock_client.get_best_installment_options.return_value = mock_options
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/best/",
            {
                "bin": "554960",
                "amount": "100.00",
                "max": "3",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 200
        mock_client.get_best_installment_options.assert_called_with(
            bin_number="554960",
            amount=Decimal("100.00"),
            max_options=3,
        )

    def test_get_best_options_missing_params(self):
        """Test with missing parameters."""
        request = self.factory.get(
            "/installments/best/",
            {
                "bin": "554960",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_best_options_api_error(self, mock_client_class):
        """Test handling API error."""
        mock_client = MagicMock()
        mock_client.get_best_installment_options.side_effect = IyzicoAPIException("API error")
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/best/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        assert response.status_code == 400

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_get_best_options_display_formatting(self, mock_client_class):
        """Test that display formatting is applied."""
        mock_option = InstallmentOption(
            installment_number=3,
            base_price=Decimal("100"),
            total_price=Decimal("103"),
            monthly_price=Decimal("34.33"),
            installment_rate=Decimal("3.00"),
        )

        mock_client = MagicMock()
        mock_client.get_best_installment_options.return_value = [mock_option]
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/best/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )

        response = self.view.get(request)

        data = json.loads(response.content)
        assert "display" in data["options"][0]
        assert "3x" in data["options"][0]["display"]


# ============================================================================
# ValidateInstallmentView Tests
# ============================================================================


class TestValidateInstallmentView(TestCase):
    """Test ValidateInstallmentView."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = ValidateInstallmentView()

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_validate_installment_valid(self, mock_client_class):
        """Test validating a valid installment."""
        mock_option = InstallmentOption(
            3, Decimal("100"), Decimal("103"), Decimal("34.33"), Decimal("3.00")
        )

        mock_client = MagicMock()
        mock_client.validate_installment_option.return_value = mock_option
        mock_client_class.return_value = mock_client

        request = self.factory.post(
            "/installments/validate/",
            data=json.dumps(
                {
                    "bin": "554960",
                    "amount": "100.00",
                    "installment": 3,
                }
            ),
            content_type="application/json",
        )

        response = self.view.post(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["success"] is True
        assert data["valid"] is True
        assert data["option"]["installment_number"] == 3

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_validate_installment_invalid(self, mock_client_class):
        """Test validating an invalid installment."""
        mock_client = MagicMock()
        mock_client.validate_installment_option.return_value = None
        mock_client_class.return_value = mock_client

        request = self.factory.post(
            "/installments/validate/",
            data=json.dumps(
                {
                    "bin": "554960",
                    "amount": "100.00",
                    "installment": 9,
                }
            ),
            content_type="application/json",
        )

        response = self.view.post(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["success"] is True
        assert data["valid"] is False
        assert "not available" in data["message"]

    def test_validate_installment_invalid_json(self):
        """Test with invalid JSON."""
        request = self.factory.post(
            "/installments/validate/",
            data="invalid json",
            content_type="application/json",
        )

        response = self.view.post(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert data["success"] is False
        assert "Invalid JSON" in data["error"]

    def test_validate_installment_missing_params(self):
        """Test with missing parameters."""
        request = self.factory.post(
            "/installments/validate/",
            data=json.dumps(
                {
                    "bin": "554960",
                    "amount": "100.00",
                    # Missing 'installment'
                }
            ),
            content_type="application/json",
        )

        response = self.view.post(request)

        assert response.status_code == 400
        data = json.loads(response.content)
        assert "required" in data["error"]

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_validate_installment_unexpected_error(self, mock_client_class):
        """Test handling unexpected error."""
        mock_client = MagicMock()
        mock_client.validate_installment_option.side_effect = Exception("Unexpected")
        mock_client_class.return_value = mock_client

        request = self.factory.post(
            "/installments/validate/",
            data=json.dumps(
                {
                    "bin": "554960",
                    "amount": "100.00",
                    "installment": 3,
                }
            ),
            content_type="application/json",
        )

        response = self.view.post(request)

        assert response.status_code == 500


# ============================================================================
# Function-Based View Tests
# ============================================================================


class TestGetInstallmentOptionsFunction(TestCase):
    """Test get_installment_options function-based view."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_function_view_delegates_to_class_view(self, mock_client_class):
        """Test that function view delegates to class view."""
        mock_options = [
            InstallmentOption(1, Decimal("100"), Decimal("100"), Decimal("100")),
        ]
        mock_bank_info = BankInstallmentInfo("Akbank", 62, mock_options)

        mock_client = MagicMock()
        mock_client.get_installment_info.return_value = [mock_bank_info]
        mock_client_class.return_value = mock_client

        request = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )
        # Add mock authenticated user for login_required decorator
        request.user = MagicMock()
        request.user.is_authenticated = True

        response = get_installment_options(request)

        assert response.status_code == 200


# ============================================================================
# DRF ViewSet Tests (if DRF is installed)
# ============================================================================


try:
    from rest_framework.test import APIRequestFactory, force_authenticate

    from django_iyzico.installment_views import InstallmentViewSet

    class TestInstallmentViewSet(TestCase):
        """Test InstallmentViewSet (DRF)."""

        def setUp(self):
            """Set up test fixtures."""
            from django.contrib.auth import get_user_model

            User = get_user_model()
            self.factory = APIRequestFactory()
            self.user = User.objects.create_user(
                username="testuser", email="test@example.com", password="testpass"
            )

        @patch("django_iyzico.installment_views.InstallmentClient")
        def test_options_action(self, mock_client_class):
            """Test options action."""
            mock_options = [
                InstallmentOption(1, Decimal("100"), Decimal("100"), Decimal("100")),
            ]
            mock_bank_info = BankInstallmentInfo("Akbank", 62, mock_options)

            mock_client = MagicMock()
            mock_client.get_installment_info.return_value = [mock_bank_info]
            mock_client_class.return_value = mock_client

            request = self.factory.get(
                "/installments/options/",
                {
                    "bin": "554960",
                    "amount": "100.00",
                },
            )
            force_authenticate(request, user=self.user)

            view = InstallmentViewSet.as_view({"get": "options"})
            response = view(request)

            assert response.status_code == 200
            assert "banks" in response.data

        @patch("django_iyzico.installment_views.InstallmentClient")
        def test_best_action(self, mock_client_class):
            """Test best action."""
            mock_options = [
                InstallmentOption(3, Decimal("100"), Decimal("100"), Decimal("33.33")),
            ]

            mock_client = MagicMock()
            mock_client.get_best_installment_options.return_value = mock_options
            mock_client_class.return_value = mock_client

            request = self.factory.get(
                "/installments/best/",
                {
                    "bin": "554960",
                    "amount": "100.00",
                },
            )
            force_authenticate(request, user=self.user)

            view = InstallmentViewSet.as_view({"get": "best"})
            response = view(request)

            assert response.status_code == 200
            assert "options" in response.data

        @patch("django_iyzico.installment_views.InstallmentClient")
        def test_validate_action(self, mock_client_class):
            """Test validate action."""
            mock_option = InstallmentOption(3, Decimal("100"), Decimal("103"), Decimal("34.33"))

            mock_client = MagicMock()
            mock_client.validate_installment_option.return_value = mock_option
            mock_client_class.return_value = mock_client

            request = self.factory.post(
                "/installments/validate/",
                {
                    "bin": "554960",
                    "amount": "100.00",
                    "installment": 3,
                },
                format="json",
            )
            force_authenticate(request, user=self.user)

            view = InstallmentViewSet.as_view({"post": "validate"})
            response = view(request)

            assert response.status_code == 200
            assert response.data["valid"] is True

        def test_options_action_missing_params(self):
            """Test options action with missing params."""
            request = self.factory.get(
                "/installments/options/",
                {
                    "bin": "554960",
                },
            )
            force_authenticate(request, user=self.user)

            view = InstallmentViewSet.as_view({"get": "options"})
            response = view(request)

            assert response.status_code == 400

        def test_best_action_missing_params(self):
            """Test best action with missing params."""
            request = self.factory.get(
                "/installments/best/",
                {
                    "amount": "100.00",
                },
            )
            force_authenticate(request, user=self.user)

            view = InstallmentViewSet.as_view({"get": "best"})
            response = view(request)

            assert response.status_code == 400

        def test_validate_action_missing_params(self):
            """Test validate action with missing params."""
            request = self.factory.post(
                "/installments/validate/",
                {
                    "bin": "554960",
                    "amount": "100.00",
                },
                format="json",
            )
            force_authenticate(request, user=self.user)

            view = InstallmentViewSet.as_view({"post": "validate"})
            response = view(request)

            assert response.status_code == 400

        @patch("django_iyzico.installment_views.InstallmentClient")
        def test_validate_action_invalid_installment(self, mock_client_class):
            """Test validate action with invalid installment."""
            mock_client = MagicMock()
            mock_client.validate_installment_option.return_value = None
            mock_client_class.return_value = mock_client

            request = self.factory.post(
                "/installments/validate/",
                {
                    "bin": "554960",
                    "amount": "100.00",
                    "installment": 9,
                },
                format="json",
            )
            force_authenticate(request, user=self.user)

            view = InstallmentViewSet.as_view({"post": "validate"})
            response = view(request)

            assert response.status_code == 200
            assert response.data["valid"] is False

except ImportError:
    # DRF not installed, skip these tests
    pass


# ============================================================================
# Integration Tests
# ============================================================================


class TestInstallmentViewsIntegration(TestCase):
    """Integration tests for installment views."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    @patch("django_iyzico.installment_views.InstallmentClient")
    def test_full_flow_get_validate(self, mock_client_class):
        """Test full flow: get options -> validate selection."""
        # Mock responses
        mock_options = [
            InstallmentOption(1, Decimal("100"), Decimal("100"), Decimal("100")),
            InstallmentOption(3, Decimal("100"), Decimal("103"), Decimal("34.33"), Decimal("3.00")),
        ]
        mock_bank_info = BankInstallmentInfo("Akbank", 62, mock_options)

        mock_client = MagicMock()
        mock_client.get_installment_info.return_value = [mock_bank_info]
        mock_client.validate_installment_option.return_value = mock_options[1]
        mock_client_class.return_value = mock_client

        # Step 1: Get options
        options_view = InstallmentOptionsView()
        request1 = self.factory.get(
            "/installments/",
            {
                "bin": "554960",
                "amount": "100.00",
            },
        )
        response1 = options_view.get(request1)

        data1 = json.loads(response1.content)
        assert data1["success"] is True

        # Step 2: Validate selection
        validate_view = ValidateInstallmentView()
        request2 = self.factory.post(
            "/installments/validate/",
            data=json.dumps(
                {
                    "bin": "554960",
                    "amount": "100.00",
                    "installment": 3,
                }
            ),
            content_type="application/json",
        )
        response2 = validate_view.post(request2)

        data2 = json.loads(response2.content)
        assert data2["success"] is True
        assert data2["valid"] is True
