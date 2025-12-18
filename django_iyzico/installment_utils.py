"""
Installment payment utilities for django-iyzico.

Provides helper functions for installment calculations,
formatting, and validation.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional


def calculate_installment_payment(
    base_amount: Decimal,
    installment_count: int,
    installment_rate: Decimal = Decimal("0.00"),
) -> Dict[str, Decimal]:
    """
    Calculate installment payment breakdown.

    Args:
        base_amount: Base payment amount
        installment_count: Number of installments
        installment_rate: Fee rate as percentage (e.g., 3.00 for 3%)

    Returns:
        Dictionary with payment breakdown:
        - base_amount: Original amount
        - installment_count: Number of installments
        - installment_rate: Fee rate percentage
        - total_fee: Total installment fee
        - total_with_fees: Total amount with fees
        - monthly_payment: Amount per month

    Example:
        >>> breakdown = calculate_installment_payment(
        ...     Decimal('100.00'),
        ...     3,
        ...     Decimal('3.00'),
        ... )
        >>> print(breakdown['monthly_payment'])
        Decimal('34.33')
    """
    if installment_count < 1:
        raise ValueError("Installment count must be at least 1")

    if base_amount <= 0:
        raise ValueError("Base amount must be greater than zero")

    if installment_rate < 0:
        raise ValueError("Installment rate cannot be negative")

    # Calculate total fee
    total_fee = base_amount * (installment_rate / 100)
    total_with_fees = base_amount + total_fee

    # Calculate monthly payment (round to 2 decimal places)
    monthly_payment = (total_with_fees / installment_count).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    return {
        "base_amount": base_amount,
        "installment_count": installment_count,
        "installment_rate": installment_rate,
        "total_fee": total_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "total_with_fees": total_with_fees.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "monthly_payment": monthly_payment,
    }


def format_installment_display(
    installment_count: int,
    monthly_payment: Decimal,
    currency: str = "TRY",
    show_total: bool = False,
    total_with_fees: Optional[Decimal] = None,
    base_amount: Optional[Decimal] = None,
) -> str:
    """
    Format installment option for display.

    Args:
        installment_count: Number of installments
        monthly_payment: Monthly payment amount
        currency: Currency code
        show_total: Whether to show total amount
        total_with_fees: Total amount with fees
        base_amount: Original amount (for fee calculation)

    Returns:
        Formatted display string

    Example:
        >>> display = format_installment_display(
        ...     3,
        ...     Decimal('34.33'),
        ...     'TRY',
        ...     show_total=True,
        ...     total_with_fees=Decimal('103.00'),
        ...     base_amount=Decimal('100.00'),
        ... )
        >>> print(display)
        '3x 34.33 TRY (Total: 103.00 TRY +3.00 TRY fee)'
    """
    basic_display = f"{installment_count}x {monthly_payment} {currency}"

    if not show_total or total_with_fees is None:
        return basic_display

    # Add total and fee information
    fee = (total_with_fees - base_amount) if base_amount else Decimal("0.00")

    if fee == 0:
        return f"{basic_display} (0% Interest)"
    else:
        return f"{basic_display} (Total: {total_with_fees} {currency} +{fee} {currency} fee)"


def validate_installment_count(
    installment_count: int,
    min_count: int = 1,
    max_count: int = 12,
) -> bool:
    """
    Validate installment count.

    Args:
        installment_count: Number of installments
        min_count: Minimum allowed (default: 1)
        max_count: Maximum allowed (default: 12)

    Returns:
        True if valid

    Raises:
        ValueError: If count is invalid

    Example:
        >>> validate_installment_count(3)
        True
        >>> validate_installment_count(15)
        ValueError: Installment count must be between 1 and 12
    """
    if not isinstance(installment_count, int):
        raise ValueError("Installment count must be an integer")

    if installment_count < min_count or installment_count > max_count:
        raise ValueError(f"Installment count must be between {min_count} and {max_count}")

    return True


def get_common_installment_options() -> List[int]:
    """
    Get list of common installment options.

    Returns:
        List of common installment counts [1, 2, 3, 6, 9, 12]

    Example:
        >>> options = get_common_installment_options()
        >>> print(options)
        [1, 2, 3, 6, 9, 12]
    """
    return [1, 2, 3, 6, 9, 12]


def calculate_zero_interest_threshold(
    campaign_rules: Dict[str, Decimal],
) -> Decimal:
    """
    Calculate minimum amount for 0% interest campaigns.

    Args:
        campaign_rules: Dictionary with campaign rules
            Example: {'min_amount': Decimal('500.00'), 'max_installment': 6}

    Returns:
        Minimum amount for 0% interest

    Example:
        >>> threshold = calculate_zero_interest_threshold({
        ...     'min_amount': Decimal('500.00'),
        ...     'max_installment': 6,
        ... })
        >>> print(threshold)
        Decimal('500.00')
    """
    return campaign_rules.get("min_amount", Decimal("0.00"))


def is_zero_interest(installment_rate: Decimal) -> bool:
    """
    Check if installment is 0% interest.

    Args:
        installment_rate: Installment rate percentage

    Returns:
        True if 0% interest

    Example:
        >>> is_zero_interest(Decimal('0.00'))
        True
        >>> is_zero_interest(Decimal('3.50'))
        False
    """
    return installment_rate == Decimal("0.00")


def compare_installment_options(
    option1: Dict[str, Decimal],
    option2: Dict[str, Decimal],
) -> int:
    """
    Compare two installment options.

    Returns -1 if option1 is better, 1 if option2 is better, 0 if equal.
    Priority: 0% interest > lower total > fewer installments

    Args:
        option1: First installment option
        option2: Second installment option

    Returns:
        -1, 0, or 1

    Example:
        >>> opt1 = {'installment_rate': Decimal('0.00'), 'installment_count': 3}
        >>> opt2 = {'installment_rate': Decimal('3.00'), 'installment_count': 3}
        >>> compare_installment_options(opt1, opt2)
        -1  # opt1 is better (0% interest)
    """
    rate1 = option1.get("installment_rate", Decimal("999.99"))
    rate2 = option2.get("installment_rate", Decimal("999.99"))

    # Prefer 0% interest
    if is_zero_interest(rate1) and not is_zero_interest(rate2):
        return -1
    elif not is_zero_interest(rate1) and is_zero_interest(rate2):
        return 1

    # Compare total amounts
    total1 = option1.get("total_with_fees", Decimal("0.00"))
    total2 = option2.get("total_with_fees", Decimal("0.00"))

    if total1 < total2:
        return -1
    elif total1 > total2:
        return 1

    # Compare installment counts (fewer is better)
    count1 = option1.get("installment_count", 999)
    count2 = option2.get("installment_count", 999)

    if count1 < count2:
        return -1
    elif count1 > count2:
        return 1

    return 0


def group_installments_by_rate(
    installment_options: List[Dict[str, Decimal]],
) -> Dict[str, List[Dict[str, Decimal]]]:
    """
    Group installment options by rate (0% vs. with fees).

    Args:
        installment_options: List of installment option dictionaries

    Returns:
        Dictionary with 'zero_interest' and 'with_fees' lists

    Example:
        >>> options = [
        ...     {'installment_rate': Decimal('0.00'), 'installment_count': 3},
        ...     {'installment_rate': Decimal('3.00'), 'installment_count': 6},
        ... ]
        >>> grouped = group_installments_by_rate(options)
        >>> len(grouped['zero_interest'])
        1
    """
    zero_interest = []
    with_fees = []

    for option in installment_options:
        rate = option.get("installment_rate", Decimal("0.00"))

        if is_zero_interest(rate):
            zero_interest.append(option)
        else:
            with_fees.append(option)

    return {
        "zero_interest": zero_interest,
        "with_fees": with_fees,
    }


def calculate_savings_vs_single_payment(
    installment_option: Dict[str, Decimal],
) -> Decimal:
    """
    Calculate cost of installments vs. single payment.

    Args:
        installment_option: Installment option dictionary

    Returns:
        Cost difference (positive = more expensive, negative = savings)

    Example:
        >>> option = {
        ...     'base_amount': Decimal('100.00'),
        ...     'total_with_fees': Decimal('103.00'),
        ... }
        >>> cost = calculate_savings_vs_single_payment(option)
        >>> print(cost)
        Decimal('3.00')  # 3 TRY more expensive
    """
    base = installment_option.get("base_amount", Decimal("0.00"))
    total = installment_option.get("total_with_fees", Decimal("0.00"))

    return total - base


def get_recommended_installment(
    amount: Decimal,
    available_options: List[Dict[str, Decimal]],
) -> Optional[Dict[str, Decimal]]:
    """
    Get recommended installment option based on amount and preferences.

    Recommends:
    - 0% interest if available
    - Otherwise, 3-6 installments with lowest fees

    Args:
        amount: Payment amount
        available_options: List of available installment options

    Returns:
        Recommended option or None

    Example:
        >>> options = [
        ...     {'installment_count': 1, 'installment_rate': Decimal('0.00')},
        ...     {'installment_count': 3, 'installment_rate': Decimal('0.00')},
        ...     {'installment_count': 6, 'installment_rate': Decimal('3.00')},
        ... ]
        >>> recommended = get_recommended_installment(Decimal('100.00'), options)
        >>> print(recommended['installment_count'])
        3  # Prefer 0% with installments over single payment
    """
    if not available_options:
        return None

    # Group by rate
    grouped = group_installments_by_rate(available_options)

    # Prefer 0% interest options
    zero_interest = grouped["zero_interest"]

    if zero_interest:
        # Find option with 3-6 installments if available
        for opt in zero_interest:
            count = opt.get("installment_count", 1)
            if 3 <= count <= 6:
                return opt

        # Otherwise return first 0% option
        return zero_interest[0]

    # No 0% options, find lowest fee with 3-6 installments
    with_fees = grouped["with_fees"]

    if not with_fees:
        return None

    # Sort by total amount
    sorted_options = sorted(with_fees, key=lambda x: x.get("total_with_fees", Decimal("999999.99")))

    # Prefer 3-6 installments
    for opt in sorted_options:
        count = opt.get("installment_count", 1)
        if 3 <= count <= 6:
            return opt

    # Otherwise return cheapest
    return sorted_options[0] if sorted_options else None


def format_installment_table(
    installment_options: List[Dict[str, Decimal]],
    currency: str = "TRY",
) -> str:
    """
    Format installment options as a text table.

    Args:
        installment_options: List of installment options
        currency: Currency code

    Returns:
        Formatted table string

    Example:
        >>> options = [
        ...     {
        ...         'installment_count': 1,
        ...         'monthly_payment': Decimal('100.00'),
        ...         'total_with_fees': Decimal('100.00'),
        ...         'installment_rate': Decimal('0.00'),
        ...     },
        ...     {
        ...         'installment_count': 3,
        ...         'monthly_payment': Decimal('34.33'),
        ...         'total_with_fees': Decimal('103.00'),
        ...         'installment_rate': Decimal('3.00'),
        ...     },
        ... ]
        >>> print(format_installment_table(options))
        Installments | Monthly     | Total       | Rate
        ------------------------------------------------
        1x           | 100.00 TRY  | 100.00 TRY  | 0.00%
        3x           | 34.33 TRY   | 103.00 TRY  | 3.00%
    """
    if not installment_options:
        return "No installment options available"

    lines = []
    lines.append(f"{'Installments':<12} | {'Monthly':<11} | {'Total':<11} | Rate")
    lines.append("-" * 55)

    for opt in installment_options:
        count = opt.get("installment_count", 1)
        monthly = opt.get("monthly_payment", Decimal("0.00"))
        total = opt.get("total_with_fees", Decimal("0.00"))
        rate = opt.get("installment_rate", Decimal("0.00"))

        lines.append(
            f"{count}x{'':<10} | "
            f"{monthly} {currency:<4} | "
            f"{total} {currency:<4} | "
            f"{rate}%"
        )

    return "\n".join(lines)
