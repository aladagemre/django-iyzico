"""
Tests for installment utility functions.

Tests all utility functions in installment_utils.py.
"""

import pytest
from decimal import Decimal

from django_iyzico.installment_utils import (
    calculate_installment_payment,
    format_installment_display,
    validate_installment_count,
    get_common_installment_options,
    calculate_zero_interest_threshold,
    is_zero_interest,
    compare_installment_options,
    group_installments_by_rate,
    calculate_savings_vs_single_payment,
    get_recommended_installment,
    format_installment_table,
)


# ============================================================================
# Calculate Installment Payment Tests
# ============================================================================


class TestCalculateInstallmentPayment:
    """Test calculate_installment_payment function."""

    def test_calculate_single_payment(self):
        """Test calculating single payment (no installment)."""
        result = calculate_installment_payment(
            base_amount=Decimal('100.00'),
            installment_count=1,
            installment_rate=Decimal('0.00'),
        )

        assert result['base_amount'] == Decimal('100.00')
        assert result['installment_count'] == 1
        assert result['installment_rate'] == Decimal('0.00')
        assert result['total_fee'] == Decimal('0.00')
        assert result['total_with_fees'] == Decimal('100.00')
        assert result['monthly_payment'] == Decimal('100.00')

    def test_calculate_installment_with_zero_interest(self):
        """Test calculating installment with 0% interest."""
        result = calculate_installment_payment(
            base_amount=Decimal('100.00'),
            installment_count=3,
            installment_rate=Decimal('0.00'),
        )

        assert result['base_amount'] == Decimal('100.00')
        assert result['installment_count'] == 3
        assert result['total_fee'] == Decimal('0.00')
        assert result['total_with_fees'] == Decimal('100.00')
        assert result['monthly_payment'] == Decimal('33.33')

    def test_calculate_installment_with_interest(self):
        """Test calculating installment with interest."""
        result = calculate_installment_payment(
            base_amount=Decimal('100.00'),
            installment_count=3,
            installment_rate=Decimal('3.00'),
        )

        assert result['base_amount'] == Decimal('100.00')
        assert result['installment_count'] == 3
        assert result['installment_rate'] == Decimal('3.00')
        assert result['total_fee'] == Decimal('3.00')
        assert result['total_with_fees'] == Decimal('103.00')
        assert result['monthly_payment'] == Decimal('34.33')

    def test_calculate_installment_rounding(self):
        """Test installment calculation with rounding."""
        result = calculate_installment_payment(
            base_amount=Decimal('100.00'),
            installment_count=7,
            installment_rate=Decimal('0.00'),
        )

        # 100 / 7 = 14.285714... should round to 14.29
        assert result['monthly_payment'] == Decimal('14.29')

    def test_calculate_installment_large_amount(self):
        """Test calculating installment with large amount."""
        result = calculate_installment_payment(
            base_amount=Decimal('10000.00'),
            installment_count=12,
            installment_rate=Decimal('5.00'),
        )

        assert result['total_fee'] == Decimal('500.00')
        assert result['total_with_fees'] == Decimal('10500.00')
        assert result['monthly_payment'] == Decimal('875.00')

    def test_calculate_installment_invalid_count(self):
        """Test with invalid installment count."""
        with pytest.raises(ValueError, match='Installment count must be at least 1'):
            calculate_installment_payment(
                base_amount=Decimal('100.00'),
                installment_count=0,
            )

    def test_calculate_installment_negative_count(self):
        """Test with negative installment count."""
        with pytest.raises(ValueError, match='Installment count must be at least 1'):
            calculate_installment_payment(
                base_amount=Decimal('100.00'),
                installment_count=-1,
            )

    def test_calculate_installment_zero_amount(self):
        """Test with zero amount."""
        with pytest.raises(ValueError, match='Base amount must be greater than zero'):
            calculate_installment_payment(
                base_amount=Decimal('0.00'),
                installment_count=3,
            )

    def test_calculate_installment_negative_amount(self):
        """Test with negative amount."""
        with pytest.raises(ValueError, match='Base amount must be greater than zero'):
            calculate_installment_payment(
                base_amount=Decimal('-100.00'),
                installment_count=3,
            )

    def test_calculate_installment_negative_rate(self):
        """Test with negative rate."""
        with pytest.raises(ValueError, match='Installment rate cannot be negative'):
            calculate_installment_payment(
                base_amount=Decimal('100.00'),
                installment_count=3,
                installment_rate=Decimal('-3.00'),
            )


# ============================================================================
# Format Installment Display Tests
# ============================================================================


class TestFormatInstallmentDisplay:
    """Test format_installment_display function."""

    def test_format_single_payment(self):
        """Test formatting single payment."""
        result = format_installment_display(
            installment_count=1,
            monthly_payment=Decimal('100.00'),
        )

        assert result == '1x 100.00 TRY'

    def test_format_installment_basic(self):
        """Test formatting basic installment."""
        result = format_installment_display(
            installment_count=3,
            monthly_payment=Decimal('34.33'),
        )

        assert result == '3x 34.33 TRY'

    def test_format_installment_with_currency(self):
        """Test formatting with different currency."""
        result = format_installment_display(
            installment_count=3,
            monthly_payment=Decimal('34.33'),
            currency='USD',
        )

        assert result == '3x 34.33 USD'

    def test_format_installment_zero_interest(self):
        """Test formatting zero-interest installment with total."""
        result = format_installment_display(
            installment_count=3,
            monthly_payment=Decimal('33.33'),
            show_total=True,
            total_with_fees=Decimal('100.00'),
            base_amount=Decimal('100.00'),
        )

        assert '0% Interest' in result
        assert '3x 33.33 TRY' in result

    def test_format_installment_with_fee(self):
        """Test formatting installment with fee."""
        result = format_installment_display(
            installment_count=3,
            monthly_payment=Decimal('34.33'),
            show_total=True,
            total_with_fees=Decimal('103.00'),
            base_amount=Decimal('100.00'),
        )

        assert '3x 34.33 TRY' in result
        assert 'Total: 103.00 TRY' in result
        assert '+3.00 TRY fee' in result

    def test_format_installment_without_total(self):
        """Test formatting without showing total."""
        result = format_installment_display(
            installment_count=6,
            monthly_payment=Decimal('17.50'),
            show_total=False,
        )

        assert result == '6x 17.50 TRY'
        assert 'Total' not in result


# ============================================================================
# Validate Installment Count Tests
# ============================================================================


class TestValidateInstallmentCount:
    """Test validate_installment_count function."""

    def test_validate_count_valid(self):
        """Test validating valid counts."""
        assert validate_installment_count(1) is True
        assert validate_installment_count(3) is True
        assert validate_installment_count(6) is True
        assert validate_installment_count(12) is True

    def test_validate_count_custom_range(self):
        """Test validating with custom range."""
        assert validate_installment_count(5, min_count=3, max_count=9) is True

    def test_validate_count_too_low(self):
        """Test count below minimum."""
        with pytest.raises(ValueError, match='Installment count must be between'):
            validate_installment_count(0)

    def test_validate_count_too_high(self):
        """Test count above maximum."""
        with pytest.raises(ValueError, match='Installment count must be between'):
            validate_installment_count(15)

    def test_validate_count_not_integer(self):
        """Test non-integer count."""
        with pytest.raises(ValueError, match='Installment count must be an integer'):
            validate_installment_count(3.5)

    def test_validate_count_string(self):
        """Test string count."""
        with pytest.raises(ValueError, match='Installment count must be an integer'):
            validate_installment_count('3')


# ============================================================================
# Common Installment Options Tests
# ============================================================================


class TestGetCommonInstallmentOptions:
    """Test get_common_installment_options function."""

    def test_get_common_options(self):
        """Test getting common installment options."""
        result = get_common_installment_options()

        assert result == [1, 2, 3, 6, 9, 12]
        assert len(result) == 6
        assert all(isinstance(x, int) for x in result)


# ============================================================================
# Zero Interest Threshold Tests
# ============================================================================


class TestCalculateZeroInterestThreshold:
    """Test calculate_zero_interest_threshold function."""

    def test_calculate_threshold(self):
        """Test calculating threshold from campaign rules."""
        rules = {
            'min_amount': Decimal('500.00'),
            'max_installment': 6,
        }

        result = calculate_zero_interest_threshold(rules)

        assert result == Decimal('500.00')

    def test_calculate_threshold_missing_min_amount(self):
        """Test with missing min_amount."""
        rules = {
            'max_installment': 6,
        }

        result = calculate_zero_interest_threshold(rules)

        assert result == Decimal('0.00')

    def test_calculate_threshold_empty_rules(self):
        """Test with empty rules."""
        result = calculate_zero_interest_threshold({})

        assert result == Decimal('0.00')


# ============================================================================
# Is Zero Interest Tests
# ============================================================================


class TestIsZeroInterest:
    """Test is_zero_interest function."""

    def test_is_zero_interest_true(self):
        """Test identifying zero interest."""
        assert is_zero_interest(Decimal('0.00')) is True
        assert is_zero_interest(Decimal('0')) is True

    def test_is_zero_interest_false(self):
        """Test identifying non-zero interest."""
        assert is_zero_interest(Decimal('3.00')) is False
        assert is_zero_interest(Decimal('0.01')) is False
        assert is_zero_interest(Decimal('10.00')) is False


# ============================================================================
# Compare Installment Options Tests
# ============================================================================


class TestCompareInstallmentOptions:
    """Test compare_installment_options function."""

    def test_compare_zero_interest_vs_with_interest(self):
        """Test comparing zero interest vs with interest."""
        opt1 = {
            'installment_rate': Decimal('0.00'),
            'total_with_fees': Decimal('100.00'),
            'installment_count': 3,
        }
        opt2 = {
            'installment_rate': Decimal('3.00'),
            'total_with_fees': Decimal('103.00'),
            'installment_count': 3,
        }

        # opt1 is better (zero interest)
        assert compare_installment_options(opt1, opt2) == -1
        assert compare_installment_options(opt2, opt1) == 1

    def test_compare_same_rate_different_total(self):
        """Test comparing same rate, different totals."""
        opt1 = {
            'installment_rate': Decimal('3.00'),
            'total_with_fees': Decimal('103.00'),
            'installment_count': 3,
        }
        opt2 = {
            'installment_rate': Decimal('3.00'),
            'total_with_fees': Decimal('105.00'),
            'installment_count': 3,
        }

        # opt1 is better (lower total)
        assert compare_installment_options(opt1, opt2) == -1

    def test_compare_same_rate_same_total_different_count(self):
        """Test comparing same rate and total, different counts."""
        opt1 = {
            'installment_rate': Decimal('0.00'),
            'total_with_fees': Decimal('100.00'),
            'installment_count': 3,
        }
        opt2 = {
            'installment_rate': Decimal('0.00'),
            'total_with_fees': Decimal('100.00'),
            'installment_count': 6,
        }

        # opt1 is better (fewer installments)
        assert compare_installment_options(opt1, opt2) == -1

    def test_compare_equal_options(self):
        """Test comparing equal options."""
        opt1 = {
            'installment_rate': Decimal('3.00'),
            'total_with_fees': Decimal('103.00'),
            'installment_count': 3,
        }
        opt2 = {
            'installment_rate': Decimal('3.00'),
            'total_with_fees': Decimal('103.00'),
            'installment_count': 3,
        }

        assert compare_installment_options(opt1, opt2) == 0


# ============================================================================
# Group Installments By Rate Tests
# ============================================================================


class TestGroupInstallmentsByRate:
    """Test group_installments_by_rate function."""

    def test_group_mixed_options(self):
        """Test grouping mixed zero and fee options."""
        options = [
            {'installment_rate': Decimal('0.00'), 'installment_count': 1},
            {'installment_rate': Decimal('3.00'), 'installment_count': 3},
            {'installment_rate': Decimal('0.00'), 'installment_count': 6},
            {'installment_rate': Decimal('5.00'), 'installment_count': 9},
        ]

        result = group_installments_by_rate(options)

        assert len(result['zero_interest']) == 2
        assert len(result['with_fees']) == 2

    def test_group_all_zero_interest(self):
        """Test grouping all zero interest options."""
        options = [
            {'installment_rate': Decimal('0.00'), 'installment_count': 1},
            {'installment_rate': Decimal('0.00'), 'installment_count': 3},
        ]

        result = group_installments_by_rate(options)

        assert len(result['zero_interest']) == 2
        assert len(result['with_fees']) == 0

    def test_group_all_with_fees(self):
        """Test grouping all fee options."""
        options = [
            {'installment_rate': Decimal('3.00'), 'installment_count': 3},
            {'installment_rate': Decimal('5.00'), 'installment_count': 6},
        ]

        result = group_installments_by_rate(options)

        assert len(result['zero_interest']) == 0
        assert len(result['with_fees']) == 2

    def test_group_empty_list(self):
        """Test grouping empty list."""
        result = group_installments_by_rate([])

        assert len(result['zero_interest']) == 0
        assert len(result['with_fees']) == 0


# ============================================================================
# Calculate Savings Tests
# ============================================================================


class TestCalculateSavingsVsSinglePayment:
    """Test calculate_savings_vs_single_payment function."""

    def test_calculate_cost_with_fees(self):
        """Test calculating cost with fees."""
        option = {
            'base_amount': Decimal('100.00'),
            'total_with_fees': Decimal('103.00'),
        }

        result = calculate_savings_vs_single_payment(option)

        assert result == Decimal('3.00')

    def test_calculate_cost_zero_interest(self):
        """Test calculating cost with zero interest."""
        option = {
            'base_amount': Decimal('100.00'),
            'total_with_fees': Decimal('100.00'),
        }

        result = calculate_savings_vs_single_payment(option)

        assert result == Decimal('0.00')

    def test_calculate_cost_missing_values(self):
        """Test with missing values."""
        option = {}

        result = calculate_savings_vs_single_payment(option)

        assert result == Decimal('0.00')


# ============================================================================
# Get Recommended Installment Tests
# ============================================================================


class TestGetRecommendedInstallment:
    """Test get_recommended_installment function."""

    def test_recommend_zero_interest_preferred_count(self):
        """Test recommending zero interest with preferred count."""
        options = [
            {'installment_count': 1, 'installment_rate': Decimal('0.00'), 'total_with_fees': Decimal('100.00')},
            {'installment_count': 3, 'installment_rate': Decimal('0.00'), 'total_with_fees': Decimal('100.00')},
            {'installment_count': 6, 'installment_rate': Decimal('3.00'), 'total_with_fees': Decimal('103.00')},
        ]

        result = get_recommended_installment(Decimal('100.00'), options)

        # Should prefer 3-installment zero interest
        assert result['installment_count'] == 3
        assert result['installment_rate'] == Decimal('0.00')

    def test_recommend_zero_interest_fallback(self):
        """Test recommending zero interest without preferred count."""
        options = [
            {'installment_count': 1, 'installment_rate': Decimal('0.00'), 'total_with_fees': Decimal('100.00')},
            {'installment_count': 9, 'installment_rate': Decimal('0.00'), 'total_with_fees': Decimal('100.00')},
        ]

        result = get_recommended_installment(Decimal('100.00'), options)

        # Should return first zero interest option
        assert result['installment_count'] == 1
        assert result['installment_rate'] == Decimal('0.00')

    def test_recommend_with_fees_preferred_count(self):
        """Test recommending with fees in preferred count range."""
        options = [
            {'installment_count': 1, 'installment_rate': Decimal('3.00'), 'total_with_fees': Decimal('103.00')},
            {'installment_count': 3, 'installment_rate': Decimal('3.00'), 'total_with_fees': Decimal('103.00')},
            {'installment_count': 9, 'installment_rate': Decimal('5.00'), 'total_with_fees': Decimal('105.00')},
        ]

        result = get_recommended_installment(Decimal('100.00'), options)

        # Should prefer 3-installment option
        assert result['installment_count'] == 3

    def test_recommend_cheapest_when_no_preferred(self):
        """Test recommending cheapest when no preferred count."""
        options = [
            {'installment_count': 1, 'installment_rate': Decimal('5.00'), 'total_with_fees': Decimal('105.00')},
            {'installment_count': 9, 'installment_rate': Decimal('3.00'), 'total_with_fees': Decimal('103.00')},
        ]

        result = get_recommended_installment(Decimal('100.00'), options)

        # Should return cheapest
        assert result['total_with_fees'] == Decimal('103.00')

    def test_recommend_empty_options(self):
        """Test with empty options."""
        result = get_recommended_installment(Decimal('100.00'), [])

        assert result is None


# ============================================================================
# Format Installment Table Tests
# ============================================================================


class TestFormatInstallmentTable:
    """Test format_installment_table function."""

    def test_format_table_basic(self):
        """Test formatting basic table."""
        options = [
            {
                'installment_count': 1,
                'monthly_payment': Decimal('100.00'),
                'total_with_fees': Decimal('100.00'),
                'installment_rate': Decimal('0.00'),
            },
            {
                'installment_count': 3,
                'monthly_payment': Decimal('34.33'),
                'total_with_fees': Decimal('103.00'),
                'installment_rate': Decimal('3.00'),
            },
        ]

        result = format_installment_table(options)

        assert 'Installments' in result
        assert 'Monthly' in result
        assert 'Total' in result
        assert 'Rate' in result
        assert '1x' in result
        assert '3x' in result
        assert '100.00 TRY' in result
        assert '34.33 TRY' in result
        assert '0.00%' in result
        assert '3.00%' in result

    def test_format_table_custom_currency(self):
        """Test formatting table with custom currency."""
        options = [
            {
                'installment_count': 1,
                'monthly_payment': Decimal('100.00'),
                'total_with_fees': Decimal('100.00'),
                'installment_rate': Decimal('0.00'),
            },
        ]

        result = format_installment_table(options, currency='USD')

        assert 'USD' in result

    def test_format_table_empty_options(self):
        """Test formatting empty table."""
        result = format_installment_table([])

        assert 'No installment options available' in result

    def test_format_table_multiple_options(self):
        """Test formatting table with multiple options."""
        options = [
            {
                'installment_count': i,
                'monthly_payment': Decimal(f'{100/i:.2f}'),
                'total_with_fees': Decimal('100.00'),
                'installment_rate': Decimal('0.00'),
            }
            for i in [1, 2, 3, 6, 9, 12]
        ]

        result = format_installment_table(options)

        # Check all counts are present
        for i in [1, 2, 3, 6, 9, 12]:
            assert f'{i}x' in result
