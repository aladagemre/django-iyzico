"""
Migration to add installment payment fields.

Adds fields for tracking installment payment details to AbstractIyzicoPayment model.

Fields added:
    - installment_rate: Fee rate percentage
    - monthly_installment_amount: Monthly payment amount
    - total_with_installment: Total amount including fees
    - bin_number: Card BIN (first 6 digits)
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add installment payment fields to payment models."""

    dependencies = [
        ('django_iyzico', '0001_add_subscription_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='abstractiyziicopayment',
            name='installment_rate',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Installment fee rate as percentage (e.g., 3.00 for 3%)',
                max_digits=5,
                null=True,
                verbose_name='Installment Rate',
            ),
        ),
        migrations.AddField(
            model_name='abstractiyziicopayment',
            name='monthly_installment_amount',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Monthly installment payment amount',
                max_digits=10,
                null=True,
                verbose_name='Monthly Installment Amount',
            ),
        ),
        migrations.AddField(
            model_name='abstractiyziicopayment',
            name='total_with_installment',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Total amount including installment fees',
                max_digits=10,
                null=True,
                verbose_name='Total with Installment',
            ),
        ),
        migrations.AddField(
            model_name='abstractiyziicopayment',
            name='bin_number',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='First 6 digits of card number (Bank Identification Number)',
                max_length=6,
                null=True,
                verbose_name='Card BIN',
            ),
        ),
        # Add index for common queries
        migrations.AddIndex(
            model_name='abstractiyziicopayment',
            index=models.Index(
                fields=['installment', 'installment_rate'],
                name='iyzico_inst_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='abstractiyziicopayment',
            index=models.Index(
                fields=['bin_number', 'created_at'],
                name='iyzico_bin_idx',
            ),
        ),
    ]
