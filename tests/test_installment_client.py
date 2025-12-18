"""
Tests for installment client functionality.

Tests InstallmentClient, InstallmentOption, and BankInstallmentInfo classes.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from django_iyzico.exceptions import IyzicoAPIException, IyzicoValidationException
from django_iyzico.installment_client import (
    BankInstallmentInfo,
    InstallmentClient,
    InstallmentOption,
)

# ============================================================================
# Dataclass Tests
# ============================================================================


class TestInstallmentOption:
    """Test InstallmentOption dataclass."""

    def test_create_installment_option(self):
        """Test creating installment option."""
        option = InstallmentOption(
            installment_number=3,
            base_price=Decimal("100.00"),
            total_price=Decimal("103.00"),
            monthly_price=Decimal("34.33"),
            installment_rate=Decimal("3.00"),
        )

        assert option.installment_number == 3
        assert option.base_price == Decimal("100.00")
        assert option.total_price == Decimal("103.00")
        assert option.monthly_price == Decimal("34.33")
        assert option.installment_rate == Decimal("3.00")

    def test_installment_option_defaults(self):
        """Test installment option default values."""
        option = InstallmentOption(
            installment_number=1,
            base_price=Decimal("100.00"),
            total_price=Decimal("100.00"),
            monthly_price=Decimal("100.00"),
        )

        assert option.installment_rate == Decimal("0.00")
        assert option.total_fee == Decimal("0.00")

    def test_installment_option_zero_interest(self):
        """Test zero interest installment option."""
        option = InstallmentOption(
            installment_number=3,
            base_price=Decimal("100.00"),
            total_price=Decimal("100.00"),
            monthly_price=Decimal("33.33"),
            installment_rate=Decimal("0.00"),
        )

        assert option.is_zero_interest is True

    def test_installment_option_with_interest(self):
        """Test installment option with interest."""
        option = InstallmentOption(
            installment_number=6,
            base_price=Decimal("100.00"),
            total_price=Decimal("105.00"),
            monthly_price=Decimal("17.50"),
            installment_rate=Decimal("5.00"),
        )

        assert option.is_zero_interest is False

    def test_installment_option_to_dict(self):
        """Test converting installment option to dictionary."""
        option = InstallmentOption(
            installment_number=3,
            base_price=Decimal("100.00"),
            total_price=Decimal("103.00"),
            monthly_price=Decimal("34.33"),
            installment_rate=Decimal("3.00"),
            total_fee=Decimal("3.00"),
        )

        result = option.to_dict()

        assert result["installment_number"] == 3
        assert result["base_price"] == "100.00"
        assert result["total_price"] == "103.00"
        assert result["monthly_price"] == "34.33"
        assert result["installment_rate"] == "3.00"
        assert result["total_fee"] == "3.00"
        assert result["is_zero_interest"] is False


class TestBankInstallmentInfo:
    """Test BankInstallmentInfo dataclass."""

    def test_create_bank_installment_info(self):
        """Test creating bank installment info."""
        options = [
            InstallmentOption(1, Decimal("100"), Decimal("100"), Decimal("100")),
            InstallmentOption(3, Decimal("100"), Decimal("103"), Decimal("34.33"), Decimal("3.00")),
        ]

        bank_info = BankInstallmentInfo(
            bank_name="Akbank",
            bank_code=62,
            installment_options=options,
        )

        assert bank_info.bank_name == "Akbank"
        assert bank_info.bank_code == 62
        assert len(bank_info.installment_options) == 2

    def test_bank_installment_info_to_dict(self):
        """Test converting bank info to dictionary."""
        options = [
            InstallmentOption(1, Decimal("100"), Decimal("100"), Decimal("100")),
        ]

        bank_info = BankInstallmentInfo(
            bank_name="Garanti BBVA",
            bank_code=62,
            installment_options=options,
        )

        result = bank_info.to_dict()

        assert result["bank_name"] == "Garanti BBVA"
        assert result["bank_code"] == 62
        assert len(result["installment_options"]) == 1
        assert isinstance(result["installment_options"][0], dict)


# ============================================================================
# InstallmentClient Tests
# ============================================================================


class TestInstallmentClientValidation:
    """Test InstallmentClient validation."""

    def test_validate_bin_number_valid(self):
        """Test validating valid BIN number."""
        client = InstallmentClient()

        # Should not raise
        client._validate_bin_number("554960")
        client._validate_bin_number("123456")

    def test_validate_bin_number_invalid_length(self):
        """Test validating BIN with invalid length."""
        client = InstallmentClient()

        with pytest.raises(IyzicoValidationException, match="BIN number must be 6 digits"):
            client._validate_bin_number("12345")

        with pytest.raises(IyzicoValidationException, match="BIN number must be 6 digits"):
            client._validate_bin_number("1234567")

    def test_validate_bin_number_invalid_characters(self):
        """Test validating BIN with invalid characters."""
        client = InstallmentClient()

        with pytest.raises(IyzicoValidationException, match="BIN number must contain only digits"):
            client._validate_bin_number("12345a")

        with pytest.raises(IyzicoValidationException, match="BIN number must contain only digits"):
            client._validate_bin_number("12-456")

    def test_validate_amount_valid(self):
        """Test validating valid amount."""
        client = InstallmentClient()

        # Should not raise
        client._validate_amount(Decimal("100.00"))
        client._validate_amount(Decimal("0.01"))

    def test_validate_amount_zero(self):
        """Test validating zero amount."""
        client = InstallmentClient()

        with pytest.raises(IyzicoValidationException, match="Amount must be greater than zero"):
            client._validate_amount(Decimal("0.00"))

    def test_validate_amount_negative(self):
        """Test validating negative amount."""
        client = InstallmentClient()

        with pytest.raises(IyzicoValidationException, match="Amount must be greater than zero"):
            client._validate_amount(Decimal("-10.00"))


class TestInstallmentClientAPI:
    """Test InstallmentClient API interactions."""

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_get_installment_info_success(self, mock_client_class):
        """Test getting installment info successfully."""
        # Mock response
        mock_response = {
            "status": "success",
            "installmentDetails": [
                {
                    "bankName": "Akbank",
                    "bankCode": 62,
                    "installmentPrices": [
                        {
                            "installmentNumber": 1,
                            "price": "100.00",
                            "totalPrice": "100.00",
                            "installmentPrice": "100.00",
                        },
                        {
                            "installmentNumber": 3,
                            "price": "100.00",
                            "totalPrice": "103.00",
                            "installmentPrice": "34.33",
                        },
                    ],
                },
            ],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()
        result = client.get_installment_info("554960", Decimal("100.00"))

        assert len(result) == 1
        assert result[0].bank_name == "Akbank"
        assert result[0].bank_code == 62
        assert len(result[0].installment_options) == 2

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_get_installment_info_api_error(self, mock_client_class):
        """Test handling API error."""
        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.side_effect = Exception("API error")
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()

        with pytest.raises(IyzicoAPIException):
            client.get_installment_info("554960", Decimal("100.00"))

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_get_installment_info_invalid_response(self, mock_client_class):
        """Test handling invalid API response."""
        mock_response = {
            "status": "failure",
            "errorMessage": "Invalid BIN",
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()

        with pytest.raises(IyzicoAPIException):
            client.get_installment_info("554960", Decimal("100.00"))

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_get_installment_info_with_caching(self, mock_client_class):
        """Test that installment info is cached."""
        mock_response = {
            "status": "success",
            "installmentDetails": [
                {
                    "bankName": "Akbank",
                    "bankCode": 62,
                    "installmentPrices": [
                        {
                            "installmentNumber": 1,
                            "price": "100.00",
                            "totalPrice": "100.00",
                            "installmentPrice": "100.00",
                        },
                    ],
                },
            ],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()

        # First call
        result1 = client.get_installment_info("554960", Decimal("100.00"))

        # Second call with same params
        result2 = client.get_installment_info("554960", Decimal("100.00"))

        # Should only call API once
        assert mock_client_instance.retrieve_installment_info.call_count == 1

        # Results should be the same
        assert result1[0].bank_name == result2[0].bank_name


class TestInstallmentClientBestOptions:
    """Test getting best installment options."""

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_get_best_installment_options(self, mock_client_class):
        """Test getting best installment options."""
        mock_response = {
            "status": "success",
            "installmentDetails": [
                {
                    "bankName": "Akbank",
                    "bankCode": 62,
                    "installmentPrices": [
                        {
                            "installmentNumber": 1,
                            "price": "100.00",
                            "totalPrice": "100.00",
                            "installmentPrice": "100.00",
                        },
                        {
                            "installmentNumber": 3,
                            "price": "100.00",
                            "totalPrice": "100.00",
                            "installmentPrice": "33.33",
                        },
                        {
                            "installmentNumber": 6,
                            "price": "100.00",
                            "totalPrice": "105.00",
                            "installmentPrice": "17.50",
                        },
                    ],
                },
            ],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()
        result = client.get_best_installment_options("554960", Decimal("100.00"), max_options=2)

        # Should prioritize zero-interest options
        assert len(result) == 2
        assert result[0].installment_number == 3  # Zero interest
        assert result[0].installment_rate == Decimal("0.00")

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_get_best_installment_options_limit(self, mock_client_class):
        """Test max_options limit."""
        mock_response = {
            "status": "success",
            "installmentDetails": [
                {
                    "bankName": "Akbank",
                    "bankCode": 62,
                    "installmentPrices": [
                        {
                            "installmentNumber": i,
                            "price": "100.00",
                            "totalPrice": "100.00",
                            "installmentPrice": str(100 / i),
                        }
                        for i in range(1, 13)
                    ],
                },
            ],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()
        result = client.get_best_installment_options("554960", Decimal("100.00"), max_options=5)

        assert len(result) == 5


class TestInstallmentClientValidation2:
    """Test validating installment options."""

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_validate_installment_option_valid(self, mock_client_class):
        """Test validating a valid installment option."""
        mock_response = {
            "status": "success",
            "installmentDetails": [
                {
                    "bankName": "Akbank",
                    "bankCode": 62,
                    "installmentPrices": [
                        {
                            "installmentNumber": 3,
                            "price": "100.00",
                            "totalPrice": "103.00",
                            "installmentPrice": "34.33",
                        },
                    ],
                },
            ],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()
        result = client.validate_installment_option("554960", Decimal("100.00"), 3)

        assert result is not None
        assert result.installment_number == 3

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_validate_installment_option_invalid(self, mock_client_class):
        """Test validating an invalid installment option."""
        mock_response = {
            "status": "success",
            "installmentDetails": [
                {
                    "bankName": "Akbank",
                    "bankCode": 62,
                    "installmentPrices": [
                        {
                            "installmentNumber": 3,
                            "price": "100.00",
                            "totalPrice": "103.00",
                            "installmentPrice": "34.33",
                        },
                    ],
                },
            ],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()
        result = client.validate_installment_option("554960", Decimal("100.00"), 6)

        assert result is None


class TestInstallmentClientParsing:
    """Test parsing API responses."""

    def test_parse_installment_response(self):
        """Test parsing installment response."""
        client = InstallmentClient()

        response = {
            "installmentDetails": [
                {
                    "bankName": "Garanti BBVA",
                    "bankCode": 62,
                    "installmentPrices": [
                        {
                            "installmentNumber": 1,
                            "price": "100.00",
                            "totalPrice": "100.00",
                            "installmentPrice": "100.00",
                        },
                        {
                            "installmentNumber": 3,
                            "price": "100.00",
                            "totalPrice": "103.00",
                            "installmentPrice": "34.33",
                        },
                    ],
                },
                {
                    "bankName": "Akbank",
                    "bankCode": 46,
                    "installmentPrices": [
                        {
                            "installmentNumber": 1,
                            "price": "100.00",
                            "totalPrice": "100.00",
                            "installmentPrice": "100.00",
                        },
                    ],
                },
            ],
        }

        result = client._parse_installment_response(response)

        assert len(result) == 2
        assert result[0].bank_name == "Garanti BBVA"
        assert len(result[0].installment_options) == 2
        assert result[1].bank_name == "Akbank"
        assert len(result[1].installment_options) == 1

    def test_parse_installment_option(self):
        """Test parsing single installment option."""
        client = InstallmentClient()

        option_data = {
            "installmentNumber": 3,
            "price": "100.00",
            "totalPrice": "103.00",
            "installmentPrice": "34.33",
        }

        result = client._parse_installment_option(option_data, Decimal("100.00"))

        assert result.installment_number == 3
        assert result.base_price == Decimal("100.00")
        assert result.total_price == Decimal("103.00")
        assert result.monthly_price == Decimal("34.33")
        assert result.installment_rate == Decimal("3.00")
        assert result.total_fee == Decimal("3.00")

    def test_parse_installment_option_zero_interest(self):
        """Test parsing zero-interest installment option."""
        client = InstallmentClient()

        option_data = {
            "installmentNumber": 3,
            "price": "100.00",
            "totalPrice": "100.00",
            "installmentPrice": "33.33",
        }

        result = client._parse_installment_option(option_data, Decimal("100.00"))

        assert result.installment_number == 3
        assert result.installment_rate == Decimal("0.00")
        assert result.total_fee == Decimal("0.00")
        assert result.is_zero_interest is True


class TestInstallmentClientEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_bin_number(self):
        """Test with empty BIN number."""
        client = InstallmentClient()

        with pytest.raises(IyzicoValidationException):
            client.get_installment_info("", Decimal("100.00"))

    def test_whitespace_bin_number(self):
        """Test with whitespace BIN number."""
        client = InstallmentClient()

        with pytest.raises(IyzicoValidationException):
            client._validate_bin_number("   ")

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_no_installment_details_in_response(self, mock_client_class):
        """Test response without installment details."""
        mock_response = {
            "status": "success",
            # Missing installmentDetails
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()

        with pytest.raises(IyzicoAPIException):
            client.get_installment_info("554960", Decimal("100.00"))

    @patch("django_iyzico.installment_client.IyzicoClient")
    def test_malformed_installment_data(self, mock_client_class):
        """Test with malformed installment data."""
        mock_response = {
            "status": "success",
            "installmentDetails": [
                {
                    # Missing required fields
                    "bankName": "Akbank",
                },
            ],
        }

        mock_client_instance = MagicMock()
        mock_client_instance.retrieve_installment_info.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        client = InstallmentClient()

        # Should handle gracefully
        result = client.get_installment_info("554960", Decimal("100.00"))
        assert isinstance(result, list)
