"""
Tests for multi-currency functionality.

Tests currency constants, validation, formatting, conversion, and model methods.
"""

import pytest
from decimal import Decimal

from django_iyzico.currency import (
    Currency,
    CURRENCY_INFO,
    is_valid_currency,
    validate_currency,
    get_currency_info,
    format_amount,
    parse_amount,
    CurrencyConverter,
    get_currency_symbol,
    get_currency_name,
    get_all_currencies,
    compare_amounts,
)


# ============================================================================
# Currency Constants Tests
# ============================================================================


class TestCurrencyEnum:
    """Test Currency enum."""

    def test_currency_values(self):
        """Test currency enum values."""
        assert Currency.TRY == 'TRY'
        assert Currency.USD == 'USD'
        assert Currency.EUR == 'EUR'
        assert Currency.GBP == 'GBP'

    def test_currency_choices(self):
        """Test currency choices for Django field."""
        choices = Currency.choices()

        assert len(choices) == 4
        assert ('TRY', 'Turkish Lira (TRY)') in choices
        assert ('USD', 'US Dollar (USD)') in choices

    def test_currency_values_list(self):
        """Test getting list of currency codes."""
        values = Currency.values()

        assert 'TRY' in values
        assert 'USD' in values
        assert 'EUR' in values
        assert 'GBP' in values
        assert len(values) == 4

    def test_currency_default(self):
        """Test default currency."""
        assert Currency.default() == 'TRY'


class TestCurrencyInfo:
    """Test CURRENCY_INFO dictionary."""

    def test_currency_info_structure(self):
        """Test currency info has required fields."""
        for currency in Currency:
            info = CURRENCY_INFO[currency]

            assert 'code' in info
            assert 'name' in info
            assert 'symbol' in info
            assert 'decimal_places' in info
            assert 'thousands_separator' in info
            assert 'decimal_separator' in info

    def test_try_info(self):
        """Test Turkish Lira info."""
        info = CURRENCY_INFO[Currency.TRY]

        assert info['code'] == 'TRY'
        assert info['name'] == 'Turkish Lira'
        assert info['symbol'] == '₺'
        assert info['decimal_places'] == 2

    def test_usd_info(self):
        """Test US Dollar info."""
        info = CURRENCY_INFO[Currency.USD]

        assert info['code'] == 'USD'
        assert info['name'] == 'US Dollar'
        assert info['symbol'] == '$'
        assert info['decimal_places'] == 2


# ============================================================================
# Validation Tests
# ============================================================================


class TestCurrencyValidation:
    """Test currency validation functions."""

    def test_is_valid_currency_valid(self):
        """Test validating valid currencies."""
        assert is_valid_currency('TRY') is True
        assert is_valid_currency('USD') is True
        assert is_valid_currency('EUR') is True
        assert is_valid_currency('GBP') is True

    def test_is_valid_currency_invalid(self):
        """Test validating invalid currencies."""
        assert is_valid_currency('JPY') is False
        assert is_valid_currency('CNY') is False
        assert is_valid_currency('XXX') is False

    def test_validate_currency_valid(self):
        """Test validate_currency with valid input."""
        assert validate_currency('TRY') == 'TRY'
        assert validate_currency('usd') == 'USD'  # Case normalization
        assert validate_currency('  EUR  ') == 'EUR'  # Whitespace trimming

    def test_validate_currency_invalid(self):
        """Test validate_currency with invalid input."""
        with pytest.raises(ValueError, match='Unsupported currency'):
            validate_currency('JPY')

        with pytest.raises(ValueError, match='Unsupported currency'):
            validate_currency('XXX')

    def test_validate_currency_empty(self):
        """Test validate_currency with empty input."""
        with pytest.raises(ValueError, match='Currency code is required'):
            validate_currency('')

        with pytest.raises(ValueError, match='Currency code is required'):
            validate_currency(None)

    def test_get_currency_info_valid(self):
        """Test getting currency info."""
        info = get_currency_info('USD')

        assert info['code'] == 'USD'
        assert info['symbol'] == '$'
        assert info['name'] == 'US Dollar'

    def test_get_currency_info_invalid(self):
        """Test getting info for invalid currency."""
        with pytest.raises(ValueError):
            get_currency_info('JPY')


# ============================================================================
# Formatting Tests
# ============================================================================


class TestCurrencyFormatting:
    """Test currency formatting functions."""

    def test_format_amount_usd(self):
        """Test formatting USD amount."""
        result = format_amount(Decimal('1234.56'), 'USD')

        assert '$' in result
        assert '1' in result
        assert '234' in result
        assert '56' in result

    def test_format_amount_try(self):
        """Test formatting TRY amount."""
        result = format_amount(Decimal('1234.56'), 'TRY')

        assert '₺' in result
        assert '1' in result
        assert '234' in result
        assert '56' in result

    def test_format_amount_no_symbol(self):
        """Test formatting without symbol."""
        result = format_amount(
            Decimal('1234.56'),
            'USD',
            show_symbol=False
        )

        assert '$' not in result
        assert '1,234.56' in result

    def test_format_amount_with_code(self):
        """Test formatting with currency code."""
        result = format_amount(
            Decimal('1234.56'),
            'EUR',
            show_code=True
        )

        assert 'EUR' in result

    def test_format_amount_negative(self):
        """Test formatting negative amount."""
        result = format_amount(Decimal('-100.00'), 'USD')

        assert '-' in result

    def test_format_amount_zero(self):
        """Test formatting zero amount."""
        result = format_amount(Decimal('0.00'), 'TRY')

        assert '0' in result

    def test_parse_amount_usd(self):
        """Test parsing USD amount."""
        result = parse_amount('$1,234.56', 'USD')

        assert result == Decimal('1234.56')

    def test_parse_amount_try(self):
        """Test parsing TRY amount."""
        result = parse_amount('₺1.234,56', 'TRY')

        assert result == Decimal('1234.56')

    def test_parse_amount_invalid(self):
        """Test parsing invalid amount."""
        with pytest.raises(ValueError):
            parse_amount('invalid', 'USD')


# ============================================================================
# Currency Conversion Tests
# ============================================================================


class TestCurrencyConverter:
    """Test CurrencyConverter class."""

    def test_converter_initialization(self):
        """Test creating currency converter."""
        converter = CurrencyConverter()

        assert converter.rates is not None
        assert Currency.TRY in converter.rates

    def test_converter_custom_rates(self):
        """Test converter with custom rates."""
        custom_rates = {
            Currency.TRY: Decimal('1.00'),
            Currency.USD: Decimal('0.04'),
        }

        converter = CurrencyConverter(rates=custom_rates)

        assert converter.rates[Currency.USD] == Decimal('0.04')

    def test_convert_same_currency(self):
        """Test converting to same currency."""
        converter = CurrencyConverter()
        result = converter.convert(Decimal('100.00'), 'TRY', 'TRY')

        assert result == Decimal('100.00')

    def test_convert_try_to_usd(self):
        """Test converting TRY to USD."""
        converter = CurrencyConverter()
        result = converter.convert(Decimal('100.00'), 'TRY', 'USD')

        assert result > Decimal('0.00')
        assert result < Decimal('100.00')  # USD worth more

    def test_convert_usd_to_try(self):
        """Test converting USD to TRY."""
        converter = CurrencyConverter()
        result = converter.convert(Decimal('100.00'), 'USD', 'TRY')

        assert result > Decimal('100.00')  # TRY worth less

    def test_convert_invalid_currency(self):
        """Test converting with invalid currency."""
        converter = CurrencyConverter()

        with pytest.raises(ValueError):
            converter.convert(Decimal('100.00'), 'JPY', 'USD')

    def test_get_rate(self):
        """Test getting exchange rate."""
        converter = CurrencyConverter()
        rate = converter.get_rate('TRY', 'USD')

        assert rate > Decimal('0.00')

    def test_get_rate_same_currency(self):
        """Test rate for same currency."""
        converter = CurrencyConverter()
        rate = converter.get_rate('USD', 'USD')

        assert rate == Decimal('1.00')

    def test_update_rates(self):
        """Test updating exchange rates."""
        converter = CurrencyConverter()
        new_rate = Decimal('0.035')

        converter.update_rates({
            'USD': new_rate,
        })

        assert converter.rates[Currency.USD] == new_rate


# ============================================================================
# Helper Functions Tests
# ============================================================================


class TestCurrencyHelpers:
    """Test currency helper functions."""

    def test_get_currency_symbol(self):
        """Test getting currency symbol."""
        assert get_currency_symbol('USD') == '$'
        assert get_currency_symbol('EUR') == '€'
        assert get_currency_symbol('GBP') == '£'
        assert get_currency_symbol('TRY') == '₺'

    def test_get_currency_name(self):
        """Test getting currency name."""
        assert get_currency_name('USD') == 'US Dollar'
        assert get_currency_name('EUR') == 'Euro'
        assert get_currency_name('GBP') == 'British Pound Sterling'
        assert get_currency_name('TRY') == 'Turkish Lira'

    def test_get_all_currencies(self):
        """Test getting all currencies."""
        currencies = get_all_currencies()

        assert len(currencies) == 4
        assert any(c['code'] == Currency.USD for c in currencies)
        assert all('symbol' in c for c in currencies)

    def test_compare_amounts_greater(self):
        """Test comparing amounts - first greater."""
        result = compare_amounts(
            Decimal('100.00'), 'USD',
            Decimal('100.00'), 'TRY'
        )

        assert result == 1  # USD is worth more

    def test_compare_amounts_less(self):
        """Test comparing amounts - first less."""
        result = compare_amounts(
            Decimal('100.00'), 'TRY',
            Decimal('100.00'), 'USD'
        )

        assert result == -1  # TRY is worth less

    def test_compare_amounts_equal(self):
        """Test comparing equal amounts."""
        result = compare_amounts(
            Decimal('100.00'), 'USD',
            Decimal('100.00'), 'USD'
        )

        assert result == 0


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================


class TestCurrencyEdgeCases:
    """Test edge cases and error handling."""

    def test_format_very_large_amount(self):
        """Test formatting very large amount."""
        result = format_amount(Decimal('1000000.00'), 'USD')

        assert '$' in result
        assert '1,000,000.00' in result

    def test_format_very_small_amount(self):
        """Test formatting very small amount."""
        result = format_amount(Decimal('0.01'), 'EUR')

        assert '0' in result
        assert '01' in result

    def test_convert_zero_amount(self):
        """Test converting zero amount."""
        converter = CurrencyConverter()
        result = converter.convert(Decimal('0.00'), 'USD', 'EUR')

        assert result == Decimal('0.00')

    def test_convert_negative_amount(self):
        """Test converting negative amount."""
        converter = CurrencyConverter()
        result = converter.convert(Decimal('-100.00'), 'USD', 'EUR')

        assert result < Decimal('0.00')

    def test_case_insensitive_validation(self):
        """Test case-insensitive currency validation."""
        assert validate_currency('try') == 'TRY'
        assert validate_currency('Usd') == 'USD'
        assert validate_currency('EuR') == 'EUR'

    def test_whitespace_handling(self):
        """Test whitespace handling in validation."""
        assert validate_currency('  TRY  ') == 'TRY'
        assert validate_currency('\tUSD\n') == 'USD'


# ============================================================================
# Integration Tests
# ============================================================================


class TestCurrencyIntegration:
    """Integration tests for currency functionality."""

    def test_format_and_parse_roundtrip(self):
        """Test formatting and parsing roundtrip."""
        original = Decimal('1234.56')

        # Format
        formatted = format_amount(original, 'USD')

        # Parse back
        parsed = parse_amount(formatted, 'USD')

        assert parsed == original

    def test_conversion_chain(self):
        """Test chain of conversions."""
        converter = CurrencyConverter()

        # Start with TRY
        try_amount = Decimal('100.00')

        # Convert TRY -> USD
        usd_amount = converter.convert(try_amount, 'TRY', 'USD')

        # Convert USD -> EUR
        eur_amount = converter.convert(usd_amount, 'USD', 'EUR')

        # Convert EUR -> back to TRY
        final_try = converter.convert(eur_amount, 'EUR', 'TRY')

        # Should be approximately the same (minor rounding differences)
        difference = abs(final_try - try_amount)
        assert difference < Decimal('0.10')  # Within 10 cents

    def test_all_currency_pairs(self):
        """Test conversion between all currency pairs."""
        converter = CurrencyConverter()
        amount = Decimal('100.00')

        for from_curr in Currency.values():
            for to_curr in Currency.values():
                result = converter.convert(amount, from_curr, to_curr)
                assert result > Decimal('0.00')
                assert isinstance(result, Decimal)
