"""
Installment Payment Examples for django-iyzico.

Demonstrates how to implement installment payments in your Django application.

Table of Contents:
    1. Basic Installment Options Retrieval
    2. Displaying Installment Options in Frontend
    3. Validating Installment Selections
    4. Processing Payments with Installments
    5. Best Installment Recommendations
    6. AJAX Integration Example
    7. Django Form with Installment Selection
    8. React/Vue Integration Example
    9. Admin Customization
    10. Installment Campaign Management
    11. Complete E-commerce Checkout Flow
    12. Testing Installment Functionality
"""

from decimal import Decimal
from typing import List, Dict, Optional

from django.shortcuts import render
from django.http import JsonResponse
from django.views import View
from django.views.generic import FormView
from django import forms

from django_iyzico.installment_client import InstallmentClient
from django_iyzico.installment_utils import (
    format_installment_display,
    get_recommended_installment,
)


# ============================================================================
# Example 1: Basic Installment Options Retrieval
# ============================================================================


def example_1_basic_retrieval():
    """
    Example 1: Retrieve installment options for a card BIN and amount.

    Use this when you need to show available installment options to users
    based on their card number and purchase amount.
    """
    # Initialize the installment client
    client = InstallmentClient()

    # Get the first 6 digits of the card (BIN)
    card_bin = "554960"  # This would come from user's card input

    # Purchase amount
    amount = Decimal("500.00")

    # Retrieve installment options
    bank_options = client.get_installment_info(
        bin_number=card_bin,
        amount=amount,
    )

    # Process results
    for bank in bank_options:
        print(f"\nBank: {bank.bank_name}")
        print(f"Bank Code: {bank.bank_code}")

        for option in bank.installment_options:
            print(f"  {option.installment_number}x: {option.monthly_price} TRY/month")
            print(f"    Total: {option.total_price} TRY")
            print(f"    Rate: {option.installment_rate}%")
            print(f"    Zero Interest: {option.is_zero_interest}")


# ============================================================================
# Example 2: Displaying Installment Options in Frontend
# ============================================================================


class InstallmentOptionsAPIView(View):
    """
    Example 2: API view to provide installment options to frontend.

    GET /api/installments/?bin=554960&amount=500.00

    Returns JSON with all available installment options.
    """

    def get(self, request):
        """Handle GET request for installment options."""
        # Get parameters
        bin_number = request.GET.get("bin")
        amount_str = request.GET.get("amount")

        # Validate
        if not bin_number or not amount_str:
            return JsonResponse(
                {
                    "error": "BIN and amount are required",
                },
                status=400,
            )

        try:
            amount = Decimal(amount_str)
        except (ValueError, TypeError):
            return JsonResponse(
                {
                    "error": "Invalid amount",
                },
                status=400,
            )

        # Get installment options
        client = InstallmentClient()
        bank_options = client.get_installment_info(bin_number, amount)

        # Format for frontend
        response_data = {
            "success": True,
            "banks": [],
        }

        for bank in bank_options:
            bank_data = {
                "bank_name": bank.bank_name,
                "bank_code": bank.bank_code,
                "options": [],
            }

            for option in bank.installment_options:
                bank_data["options"].append(
                    {
                        "installments": option.installment_number,
                        "monthly_payment": str(option.monthly_price),
                        "total": str(option.total_price),
                        "rate": str(option.installment_rate),
                        "zero_interest": option.is_zero_interest,
                        "display_text": format_installment_display(
                            option.installment_number,
                            option.monthly_price,
                            "TRY",
                            show_total=True,
                            total_with_fees=option.total_price,
                            base_amount=option.base_price,
                        ),
                    }
                )

            response_data["banks"].append(bank_data)

        return JsonResponse(response_data)


# ============================================================================
# Example 3: Validating Installment Selections
# ============================================================================


def example_3_validate_selection():
    """
    Example 3: Validate that a selected installment option is available.

    Use this before processing payment to ensure the user's selection is valid.
    """
    client = InstallmentClient()

    # User's selections
    card_bin = "554960"
    amount = Decimal("500.00")
    selected_installment = 3

    # Validate the selection
    is_valid = client.validate_installment_option(
        bin_number=card_bin,
        amount=amount,
        installment_number=selected_installment,
    )

    if is_valid:
        print(f"✓ {selected_installment} installments is available")
        print(f"  Monthly payment: {is_valid.monthly_price} TRY")
        print(f"  Total: {is_valid.total_price} TRY")
        return True
    else:
        print(f"✗ {selected_installment} installments not available")
        return False


# ============================================================================
# Example 4: Processing Payments with Installments
# ============================================================================


def example_4_process_payment_with_installment():
    """
    Example 4: Process a payment with installment.

    Demonstrates storing installment data with the payment.
    """
    from django_iyzico.client import IyzicoClient

    # Initialize clients
    iyzico_client = IyzicoClient()
    installment_client = InstallmentClient()

    # Payment details
    card_bin = "554960"
    amount = Decimal("500.00")
    selected_installment = 3

    # Step 1: Validate installment option
    installment_option = installment_client.validate_installment_option(
        bin_number=card_bin,
        amount=amount,
        installment_number=selected_installment,
    )

    if not installment_option:
        raise ValueError("Selected installment option not available")

    # Step 2: Prepare payment data
    payment_data = {
        "amount": str(amount),
        "installment": selected_installment,
        # ... other payment fields (card, buyer, basket, etc.)
    }

    # Step 3: Process payment through Iyzico
    # payment_response = iyzico_client.create_payment(payment_data)

    # Step 4: Store installment information with payment
    # After successful payment, store:
    payment_record = {
        "amount": amount,
        "installment": selected_installment,
        "installment_rate": installment_option.installment_rate,
        "monthly_installment_amount": installment_option.monthly_price,
        "total_with_installment": installment_option.total_price,
        "bin_number": card_bin,
    }

    return payment_record


# ============================================================================
# Example 5: Best Installment Recommendations
# ============================================================================


def example_5_get_best_options():
    """
    Example 5: Get recommended installment options.

    Use this to show users the best installment deals.
    """
    client = InstallmentClient()

    card_bin = "554960"
    amount = Decimal("1000.00")

    # Get top 5 best options
    best_options = client.get_best_installment_options(
        bin_number=card_bin,
        amount=amount,
        max_options=5,
    )

    print("Recommended Installment Options:")
    print("=" * 60)

    for i, option in enumerate(best_options, 1):
        print(f"\n{i}. {option.installment_number} Installments")
        print(f"   Monthly: {option.monthly_price} TRY")
        print(f"   Total: {option.total_price} TRY")
        print(f"   Rate: {option.installment_rate}%")

        if option.is_zero_interest:
            print("   ⭐ ZERO INTEREST!")

    return best_options


# ============================================================================
# Example 6: AJAX Integration
# ============================================================================


def example_6_ajax_template():
    """
    Example 6: Template with AJAX integration for dynamic installment display.

    HTML/JavaScript template example.
    """
    html_template = """
    <!-- Installment Options Display -->
    <div id="installment-options">
        <h3>Select Installment Option</h3>

        <div class="form-group">
            <label>Card Number</label>
            <input type="text"
                   id="card-number"
                   class="form-control"
                   placeholder="**** **** **** ****"
                   maxlength="19">
        </div>

        <div class="form-group">
            <label>Amount</label>
            <input type="text"
                   id="amount"
                   class="form-control"
                   value="500.00"
                   readonly>
        </div>

        <div id="installment-list" class="mt-3">
            <!-- Installment options will be loaded here -->
        </div>
    </div>

    <script>
    // Fetch installment options when card BIN is entered
    document.getElementById('card-number').addEventListener('input', function(e) {
        let cardNumber = e.target.value.replace(/\\s/g, '');

        // Wait until we have at least 6 digits (BIN)
        if (cardNumber.length >= 6) {
            let bin = cardNumber.substring(0, 6);
            let amount = document.getElementById('amount').value;

            // Fetch options
            fetch(`/api/installments/?bin=${bin}&amount=${amount}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displayInstallmentOptions(data.banks);
                    }
                })
                .catch(error => {
                    console.error('Error fetching installment options:', error);
                });
        }
    });

    function displayInstallmentOptions(banks) {
        let container = document.getElementById('installment-list');
        container.innerHTML = '';

        banks.forEach(bank => {
            let bankDiv = document.createElement('div');
            bankDiv.className = 'bank-options mb-3';

            let bankTitle = document.createElement('h4');
            bankTitle.textContent = bank.bank_name;
            bankDiv.appendChild(bankTitle);

            let optionsList = document.createElement('div');
            optionsList.className = 'list-group';

            bank.options.forEach(option => {
                let optionItem = document.createElement('button');
                optionItem.type = 'button';
                optionItem.className = 'list-group-item list-group-item-action';
                optionItem.dataset.installment = option.installments;

                let badge = '';
                if (option.zero_interest) {
                    badge = '<span class="badge badge-success">0% Interest</span>';
                }

                optionItem.innerHTML = `
                    <div class="d-flex w-100 justify-content-between">
                        <h5 class="mb-1">${option.installments}x ${option.monthly_payment} TRY</h5>
                        ${badge}
                    </div>
                    <p class="mb-1">Total: ${option.total} TRY (${option.rate}% rate)</p>
                `;

                optionItem.addEventListener('click', function() {
                    selectInstallment(option.installments);
                });

                optionsList.appendChild(optionItem);
            });

            bankDiv.appendChild(optionsList);
            container.appendChild(bankDiv);
        });
    }

    function selectInstallment(installmentCount) {
        // Store selected installment
        document.getElementById('selected-installment').value = installmentCount;

        // Highlight selected option
        document.querySelectorAll('.list-group-item').forEach(item => {
            item.classList.remove('active');
        });
        event.target.closest('.list-group-item').classList.add('active');
    }
    </script>
    """

    return html_template


# ============================================================================
# Example 7: Django Form with Installment Selection
# ============================================================================


class PaymentForm(forms.Form):
    """
    Example 7: Django form with installment field.

    Demonstrates validation and processing of installment payments.
    """

    card_number = forms.CharField(
        max_length=16,
        widget=forms.TextInput(
            attrs={
                "placeholder": "1234567812345678",
                "class": "form-control",
            }
        ),
    )

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
            }
        ),
    )

    installment = forms.IntegerField(
        min_value=1,
        max_value=12,
        initial=1,
        widget=forms.Select(
            attrs={
                "class": "form-control",
            }
        ),
    )

    def clean(self):
        """Validate installment option."""
        cleaned_data = super().clean()

        card_number = cleaned_data.get("card_number")
        amount = cleaned_data.get("amount")
        installment = cleaned_data.get("installment")

        if card_number and amount and installment:
            # Get BIN from card
            card_bin = card_number[:6]

            # Validate installment option
            client = InstallmentClient()
            option = client.validate_installment_option(
                bin_number=card_bin,
                amount=amount,
                installment_number=installment,
            )

            if not option:
                raise forms.ValidationError(
                    f"{installment} installments not available for this card"
                )

            # Store installment details for later use
            self.installment_option = option

        return cleaned_data


class PaymentFormView(FormView):
    """Example view using PaymentForm."""

    template_name = "payment.html"
    form_class = PaymentForm

    def form_valid(self, form):
        """Process valid form."""
        # Get installment option from form
        installment_option = form.installment_option

        # Process payment with installment details
        # ...

        return super().form_valid(form)


# ============================================================================
# Example 8: React/Vue Integration
# ============================================================================


def example_8_frontend_integration():
    """
    Example 8: Modern frontend framework integration.

    React/Vue component example for installment selection.
    """
    react_component = """
    // React Component for Installment Selection
    import React, { useState, useEffect } from 'react';

    function InstallmentSelector({ amount, onSelect }) {
        const [cardBin, setCardBin] = useState('');
        const [options, setOptions] = useState([]);
        const [loading, setLoading] = useState(false);
        const [selectedInstallment, setSelectedInstallment] = useState(1);

        // Fetch options when BIN changes
        useEffect(() => {
            if (cardBin.length >= 6) {
                fetchInstallmentOptions();
            }
        }, [cardBin]);

        const fetchInstallmentOptions = async () => {
            setLoading(true);

            try {
                const response = await fetch(
                    `/api/installments/best/?bin=${cardBin}&amount=${amount}&max=5`
                );
                const data = await response.json();

                if (data.success) {
                    setOptions(data.options);
                }
            } catch (error) {
                console.error('Error fetching options:', error);
            } finally {
                setLoading(false);
            }
        };

        const handleCardInput = (e) => {
            const value = e.target.value.replace(/\\s/g, '');
            setCardBin(value.substring(0, 6));
        };

        const handleSelect = (installment) => {
            setSelectedInstallment(installment);
            onSelect(installment);
        };

        return (
            <div className="installment-selector">
                <div className="form-group">
                    <label>Card Number</label>
                    <input
                        type="text"
                        className="form-control"
                        onChange={handleCardInput}
                        placeholder="Enter card number"
                    />
                </div>

                {loading && <div className="spinner">Loading options...</div>}

                {options.length > 0 && (
                    <div className="installment-options">
                        <h4>Select Installment Plan</h4>

                        {options.map(option => (
                            <div
                                key={option.installment_number}
                                className={`option-card ${
                                    selectedInstallment === option.installment_number
                                        ? 'selected'
                                        : ''
                                }`}
                                onClick={() => handleSelect(option.installment_number)}
                            >
                                <div className="option-header">
                                    <span className="installment-count">
                                        {option.installment_number}x
                                    </span>
                                    <span className="monthly-payment">
                                        {option.monthly_price} TRY/month
                                    </span>
                                </div>

                                <div className="option-details">
                                    <span>Total: {option.total_price} TRY</span>
                                    {option.is_zero_interest && (
                                        <span className="badge-zero-interest">
                                            0% Interest
                                        </span>
                                    )}
                                </div>

                                <div className="option-display">
                                    {option.display}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    export default InstallmentSelector;
    """

    return react_component


# ============================================================================
# Example 9: Admin Customization
# ============================================================================


def example_9_admin_customization():
    """
    Example 9: Customize Django admin for installment display.

    Shows how to extend the admin interface.
    """
    from django.contrib import admin
    from django_iyzico.admin import IyzicoPaymentAdminMixin

    class CustomPaymentAdmin(IyzicoPaymentAdminMixin, admin.ModelAdmin):
        """
        Custom admin with installment filtering and display.
        """

        # Add installment-specific filters
        list_filter = IyzicoPaymentAdminMixin.list_filter + [
            ("installment", admin.ChoicesFieldListFilter),
        ]

        # Custom list display
        list_display = IyzicoPaymentAdminMixin.list_display + [
            "get_installment_savings",
        ]

        def get_installment_savings(self, obj):
            """Calculate savings for zero-interest installments."""
            if obj.has_installment() and obj.is_zero_interest_installment():
                # Calculate expected fee if it wasn't zero interest
                expected_fee = obj.amount * Decimal("0.03")  # Assume 3% average
                return f"Saved ~{expected_fee} {obj.currency}"
            return "-"

        get_installment_savings.short_description = "Savings"

    # admin.site.register(YourPaymentModel, CustomPaymentAdmin)


# ============================================================================
# Example 10: Installment Campaign Management
# ============================================================================


class InstallmentCampaign:
    """
    Example 10: Manage installment campaigns and promotions.

    Demonstrates how to track and promote special installment offers.
    """

    def __init__(self, name: str, min_amount: Decimal, max_installment: int):
        """Initialize campaign."""
        self.name = name
        self.min_amount = min_amount
        self.max_installment = max_installment

    def is_eligible(self, amount: Decimal, installment: int) -> bool:
        """Check if order is eligible for campaign."""
        return amount >= self.min_amount and installment <= self.max_installment

    @classmethod
    def get_active_campaigns(cls) -> List["InstallmentCampaign"]:
        """Get currently active campaigns."""
        return [
            cls(
                name="Spring Sale - 6 Installments 0%",
                min_amount=Decimal("500.00"),
                max_installment=6,
            ),
            cls(
                name="Premium 12 Month 0%",
                min_amount=Decimal("2000.00"),
                max_installment=12,
            ),
        ]

    def apply_to_options(self, options: List) -> List:
        """Mark eligible options with campaign badge."""
        for option in options:
            if self.is_eligible(option.base_price, option.installment_number):
                option.campaign = self.name

        return options


# ============================================================================
# Example 11: Complete E-commerce Checkout Flow
# ============================================================================


class CheckoutView(View):
    """
    Example 11: Complete checkout flow with installments.

    Full implementation of checkout with installment support.
    """

    def get(self, request):
        """Display checkout page."""
        # Get cart total
        cart_total = self.get_cart_total(request)

        context = {
            "cart_total": cart_total,
        }

        return render(request, "checkout.html", context)

    def post(self, request):
        """Process checkout."""
        # Get form data
        card_number = request.POST.get("card_number")
        amount = Decimal(request.POST.get("amount"))
        selected_installment = int(request.POST.get("installment", 1))

        # Get BIN
        card_bin = card_number[:6]

        # Step 1: Validate installment
        client = InstallmentClient()
        installment_option = client.validate_installment_option(
            bin_number=card_bin,
            amount=amount,
            installment_number=selected_installment,
        )

        if not installment_option:
            return JsonResponse(
                {
                    "error": "Selected installment not available",
                },
                status=400,
            )

        # Step 2: Calculate final total
        final_total = installment_option.total_price

        # Step 3: Process payment
        payment_result = self.process_payment(
            card_number=card_number,
            amount=amount,
            installment=selected_installment,
            installment_data=installment_option,
        )

        # Step 4: Create order
        if payment_result["success"]:
            order = self.create_order(
                payment_result=payment_result,
                installment_option=installment_option,
            )

            return JsonResponse(
                {
                    "success": True,
                    "order_id": order.id,
                    "installment_info": {
                        "count": selected_installment,
                        "monthly_payment": str(installment_option.monthly_price),
                        "total": str(final_total),
                    },
                }
            )

        return JsonResponse(
            {
                "success": False,
                "error": payment_result.get("error"),
            },
            status=400,
        )

    def get_cart_total(self, request):
        """Get cart total from session."""
        # Implementation depends on your cart system
        return Decimal("500.00")

    def process_payment(self, **kwargs):
        """Process payment through Iyzico."""
        # Implementation using IyzicoClient
        return {"success": True}

    def create_order(self, payment_result, installment_option):
        """Create order record."""
        # Create order with installment details
        pass


# ============================================================================
# Example 12: Testing Installment Functionality
# ============================================================================


def example_12_testing():
    """
    Example 12: Test cases for installment functionality.

    Unit tests and integration tests.
    """
    test_code = '''
    import pytest
    from decimal import Decimal
    from django_iyzico.installment_client import InstallmentClient

    class TestInstallmentIntegration:
        """Integration tests for installments."""

        @pytest.fixture
        def client(self):
            """Create installment client."""
            return InstallmentClient()

        def test_get_and_validate_flow(self, client):
            """Test complete get and validate flow."""
            bin_number = '554960'
            amount = Decimal('500.00')

            # Get options
            options = client.get_installment_info(bin_number, amount)

            assert len(options) > 0

            # Get first bank's first option
            first_option = options[0].installment_options[0]

            # Validate that option
            validated = client.validate_installment_option(
                bin_number,
                amount,
                first_option.installment_number,
            )

            assert validated is not None
            assert validated.installment_number == first_option.installment_number

        def test_zero_interest_identification(self, client):
            """Test identifying zero-interest options."""
            options = client.get_best_installment_options(
                '554960',
                Decimal('1000.00'),
                max_options=10,
            )

            zero_interest = [opt for opt in options if opt.is_zero_interest]

            # Should prioritize zero interest
            if zero_interest:
                assert options[0].is_zero_interest
    '''

    return test_code


# ============================================================================
# Running Examples
# ============================================================================


if __name__ == "__main__":
    """Run examples."""
    print("django-iyzico Installment Payment Examples")
    print("=" * 60)

    print("\n\nExample 1: Basic Retrieval")
    print("-" * 60)
    # example_1_basic_retrieval()

    print("\n\nExample 3: Validation")
    print("-" * 60)
    # example_3_validate_selection()

    print("\n\nExample 5: Best Options")
    print("-" * 60)
    # example_5_get_best_options()

    print("\n\nExamples completed!")
    print("\nRefer to individual example functions for implementation details.")
