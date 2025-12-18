"""
Tests for management commands.
"""

import io
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from django_iyzico.models import PaymentStatus


@pytest.mark.django_db
class TestSyncIyzicoPaymentsCommand:
    """Test sync_iyzico_payments management command."""

    def test_sync_command_no_payments(self, payment_model):
        """Test sync command with no payments in database."""
        out = io.StringIO()
        call_command(
            "sync_iyzico_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=7,
            stdout=out,
        )

        output = out.getvalue()
        assert "No payments found" in output

    def test_sync_command_with_payments(self, payment_model):
        """Test sync command with payments."""
        # Create test payments
        payment1 = payment_model.objects.create(
            payment_id="test-payment-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        payment2 = payment_model.objects.create(
            payment_id="test-payment-2",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.PENDING,
        )

        out = io.StringIO()
        call_command(
            "sync_iyzico_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=7,
            stdout=out,
        )

        output = out.getvalue()
        assert "Syncing 2 payments" in output
        assert "SYNC SUMMARY" in output

    def test_sync_command_dry_run(self, payment_model):
        """Test sync command in dry-run mode."""
        payment = payment_model.objects.create(
            payment_id="test-payment",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        out = io.StringIO()
        call_command(
            "sync_iyzico_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=7,
            dry_run=True,
            stdout=out,
        )

        output = out.getvalue()
        assert "DRY RUN MODE" in output
        assert "No actual changes were made" in output

    def test_sync_command_status_filter_success(self, payment_model):
        """Test sync command with status filter."""
        # Create payments with different statuses
        payment_model.objects.create(
            payment_id="success-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        payment_model.objects.create(
            payment_id="failed-1",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.FAILED,
        )

        out = io.StringIO()
        call_command(
            "sync_iyzico_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=7,
            status="success",
            stdout=out,
        )

        output = out.getvalue()
        assert "Syncing 1 payments" in output

    def test_sync_command_with_limit(self, payment_model):
        """Test sync command with limit."""
        # Create multiple payments
        for i in range(5):
            payment_model.objects.create(
                payment_id=f"payment-{i}",
                conversation_id=f"conv-{i}",
                amount=Decimal("100.00"),
                status=PaymentStatus.SUCCESS,
            )

        out = io.StringIO()
        call_command(
            "sync_iyzico_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=7,
            limit=3,
            stdout=out,
        )

        output = out.getvalue()
        assert "Syncing 3 payments" in output

    def test_sync_command_excludes_refunded(self, payment_model):
        """Test that sync command excludes refunded payments."""
        payment_model.objects.create(
            payment_id="refunded-1",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.REFUNDED,
        )

        payment_model.objects.create(
            payment_id="success-1",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.SUCCESS,
        )

        out = io.StringIO()
        call_command(
            "sync_iyzico_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=7,
            stdout=out,
        )

        output = out.getvalue()
        assert "Syncing 1 payments" in output

    def test_sync_command_old_payments_excluded(self, payment_model):
        """Test that old payments are excluded."""
        # Create old payment
        old_payment = payment_model.objects.create(
            payment_id="old-payment",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )
        # Manually set old date
        old_date = timezone.now() - timedelta(days=10)
        payment_model.objects.filter(pk=old_payment.pk).update(created_at=old_date)

        # Create recent payment
        payment_model.objects.create(
            payment_id="recent-payment",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.SUCCESS,
        )

        out = io.StringIO()
        call_command(
            "sync_iyzico_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=7,
            stdout=out,
        )

        output = out.getvalue()
        assert "Syncing 1 payments" in output

    def test_sync_command_invalid_model(self):
        """Test sync command with invalid model path."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command(
                "sync_iyzico_payments",
                model="invalid.Model",
                days=7,
            )


@pytest.mark.django_db
class TestCleanupOldPaymentsCommand:
    """Test cleanup_old_payments management command."""

    def test_cleanup_command_no_payments(self, payment_model):
        """Test cleanup with no old payments."""
        out = io.StringIO()
        call_command(
            "cleanup_old_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=365,
            no_input=True,
            stdout=out,
        )

        output = out.getvalue()
        assert "No old payments to clean up" in output

    def test_cleanup_command_dry_run(self, payment_model):
        """Test cleanup in dry-run mode."""
        # Create old failed payment
        old_payment = payment_model.objects.create(
            payment_id="old-failed",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
        )

        # Set old date
        old_date = timezone.now() - timedelta(days=400)
        payment_model.objects.filter(pk=old_payment.pk).update(created_at=old_date)

        out = io.StringIO()
        call_command(
            "cleanup_old_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=365,
            dry_run=True,
            stdout=out,
        )

        output = out.getvalue()
        assert "DRY RUN MODE" in output
        assert "No deletions will be performed" in output

        # Verify payment still exists
        assert payment_model.objects.filter(pk=old_payment.pk).exists()

    def test_cleanup_deletes_old_failed_payments(self, payment_model):
        """Test cleanup deletes old failed payments."""
        # Create old failed payment
        old_failed = payment_model.objects.create(
            payment_id="old-failed",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
        )

        old_date = timezone.now() - timedelta(days=400)
        payment_model.objects.filter(pk=old_failed.pk).update(created_at=old_date)

        # Create recent failed payment (should not be deleted)
        recent_failed = payment_model.objects.create(
            payment_id="recent-failed",
            conversation_id="conv-2",
            amount=Decimal("200.00"),
            status=PaymentStatus.FAILED,
        )

        out = io.StringIO()
        call_command(
            "cleanup_old_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=365,
            no_input=True,
            stdout=out,
        )

        output = out.getvalue()
        assert "CLEANUP COMPLETED" in output

        # Verify old payment deleted, recent kept
        assert not payment_model.objects.filter(pk=old_failed.pk).exists()
        assert payment_model.objects.filter(pk=recent_failed.pk).exists()

    def test_cleanup_keeps_successful_longer(self, payment_model):
        """Test cleanup keeps successful payments longer."""
        # Create old successful payment (400 days old)
        old_success = payment_model.objects.create(
            payment_id="old-success",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        date_400_days = timezone.now() - timedelta(days=400)
        payment_model.objects.filter(pk=old_success.pk).update(created_at=date_400_days)

        out = io.StringIO()
        call_command(
            "cleanup_old_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=365,
            keep_successful=730,  # Keep successful for 2 years
            no_input=True,
            stdout=out,
        )

        # Successful payment should still exist (400 < 730)
        assert payment_model.objects.filter(pk=old_success.pk).exists()

    def test_cleanup_deletes_very_old_successful(self, payment_model):
        """Test cleanup deletes very old successful payments."""
        # Create very old successful payment (800 days old)
        very_old_success = payment_model.objects.create(
            payment_id="very-old-success",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.SUCCESS,
        )

        date_800_days = timezone.now() - timedelta(days=800)
        payment_model.objects.filter(pk=very_old_success.pk).update(created_at=date_800_days)

        out = io.StringIO()
        call_command(
            "cleanup_old_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=365,
            keep_successful=730,
            no_input=True,
            stdout=out,
        )

        # Very old successful payment should be deleted (800 > 730)
        assert not payment_model.objects.filter(pk=very_old_success.pk).exists()

    def test_cleanup_keep_refunded_flag(self, payment_model):
        """Test cleanup with keep-refunded flag."""
        # Create old refunded payment
        old_refunded = payment_model.objects.create(
            payment_id="old-refunded",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.REFUNDED,
        )

        old_date = timezone.now() - timedelta(days=400)
        payment_model.objects.filter(pk=old_refunded.pk).update(created_at=old_date)

        out = io.StringIO()
        call_command(
            "cleanup_old_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=365,
            keep_refunded=True,
            no_input=True,
            stdout=out,
        )

        # Refunded payment should still exist
        assert payment_model.objects.filter(pk=old_refunded.pk).exists()

    def test_cleanup_export_to_csv(self, payment_model, sample_payment_data, tmp_path):
        """Test cleanup with CSV export."""
        # Create old payment
        old_payment = payment_model.objects.create(
            payment_id="old-payment",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
            buyer_email="test@example.com",
            buyer_name="John",
            buyer_surname="Doe",
        )

        old_date = timezone.now() - timedelta(days=400)
        payment_model.objects.filter(pk=old_payment.pk).update(created_at=old_date)

        export_file = tmp_path / "exported_payments.csv"

        out = io.StringIO()
        call_command(
            "cleanup_old_payments",
            model=f"tests.models.{payment_model.__name__}",
            days=365,
            export=str(export_file),
            no_input=True,
            stdout=out,
        )

        # Verify export file was created
        assert export_file.exists()

        # Verify content
        content = export_file.read_text()
        assert "payment_id" in content
        assert "old-payment" in content
        assert "test@example.com" in content

    def test_cleanup_confirmation_prompt(self, payment_model):
        """Test cleanup prompts for confirmation."""
        # Create old payment
        old_payment = payment_model.objects.create(
            payment_id="old-payment",
            conversation_id="conv-1",
            amount=Decimal("100.00"),
            status=PaymentStatus.FAILED,
        )

        old_date = timezone.now() - timedelta(days=400)
        payment_model.objects.filter(pk=old_payment.pk).update(created_at=old_date)

        # Test with mock input (user says 'no')
        with patch("builtins.input", return_value="no"):
            out = io.StringIO()
            call_command(
                "cleanup_old_payments",
                model=f"tests.models.{payment_model.__name__}",
                days=365,
                stdout=out,
            )

            output = out.getvalue()
            assert "Deletion cancelled" in output

            # Payment should still exist
            assert payment_model.objects.filter(pk=old_payment.pk).exists()

    def test_cleanup_invalid_model(self):
        """Test cleanup with invalid model path."""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command(
                "cleanup_old_payments",
                model="invalid.Model",
                days=365,
                no_input=True,
            )
