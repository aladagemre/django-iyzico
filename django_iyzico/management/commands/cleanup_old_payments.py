"""
Management command to clean up old payment records.

This command helps maintain database hygiene by archiving or deleting
old payment records based on configurable retention policies.
"""

import csv
import logging
from datetime import timedelta
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from django_iyzico.models import PaymentStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Clean up old payment records.

    This command helps maintain database size and performance by removing
    old payment records while respecting different retention periods for
    successful vs. failed payments.
    """

    help = "Archive or delete old payment records based on retention policy"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Delete failed/cancelled payments older than this many days (default: 365)",
        )
        parser.add_argument(
            "--keep-successful",
            type=int,
            default=730,
            help="Keep successful payments for this many days (default: 730 = 2 years)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Do not prompt for confirmation (use with caution!)",
        )
        parser.add_argument(
            "--model",
            type=str,
            required=True,
            help="Full path to payment model (e.g., myapp.models.Order)",
        )
        parser.add_argument(
            "--export",
            type=str,
            help="Export payments to CSV file before deletion (path to file)",
        )
        parser.add_argument(
            "--keep-refunded",
            action="store_true",
            help="Do not delete refunded payments (for audit purposes)",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        days = options["days"]
        keep_successful = options["keep_successful"]
        dry_run = options["dry_run"]
        no_input = options["no_input"]
        model_path = options["model"]
        export_path = options["export"]
        keep_refunded = options["keep_refunded"]

        # Set logging level based on verbosity
        if options["verbosity"] >= 2:
            logger.setLevel(logging.DEBUG)

        # Import model dynamically
        try:
            PaymentModel = self._import_model(model_path)
        except Exception as e:
            raise CommandError(f"Failed to import model '{model_path}': {e}")

        # Calculate cutoff dates
        cutoff_date = timezone.now() - timedelta(days=days)
        success_cutoff = timezone.now() - timedelta(days=keep_successful)

        # Build query for old failed/cancelled/pending payments
        failed_statuses = [
            PaymentStatus.FAILED,
            PaymentStatus.PENDING,
            PaymentStatus.CANCELLED,
        ]

        # Add refunded status if not keeping them
        if not keep_refunded:
            failed_statuses.extend(
                [
                    PaymentStatus.REFUNDED,
                    PaymentStatus.REFUND_PENDING,
                ]
            )

        old_failed = PaymentModel.objects.filter(
            created_at__lt=cutoff_date,
            status__in=failed_statuses,
        )

        # Find old successful payments
        old_successful = PaymentModel.objects.filter(
            created_at__lt=success_cutoff,
            status=PaymentStatus.SUCCESS,
        )

        # Calculate counts
        failed_count = old_failed.count()
        successful_count = old_successful.count()
        total_count = failed_count + successful_count

        # Display summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.WARNING("PAYMENT CLEANUP SUMMARY"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Failed/Cancelled (older than {days} days): {failed_count}")
        self.stdout.write(f"Successful (older than {keep_successful} days): {successful_count}")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.WARNING(f"TOTAL TO DELETE: {total_count} payments"))
        self.stdout.write("=" * 60 + "\n")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No old payments to clean up"))
            return

        # Show sample of payments to be deleted
        if options["verbosity"] >= 1:
            self._show_sample_payments(old_failed, old_successful)

        # Export if requested
        if export_path and not dry_run:
            self._export_payments(old_failed, old_successful, export_path, options["verbosity"])

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nDRY RUN MODE - No deletions will be performed\n")
            )
            return

        # Confirm deletion
        if not no_input:
            self.stdout.write(
                self.style.WARNING(
                    f"\nYou are about to permanently delete {total_count} payment records!"
                )
            )
            self.stdout.write(self.style.WARNING("This action cannot be undone.\n"))

            confirm = input("Type 'yes' to confirm deletion: ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.SUCCESS("Deletion cancelled"))
                return

        # Perform deletion
        self.stdout.write("\nDeleting payments...")

        try:
            deleted_failed, failed_details = old_failed.delete()
            deleted_successful, success_details = old_successful.delete()

            total_deleted = deleted_failed + deleted_successful

            # Display results
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("CLEANUP COMPLETED"))
            self.stdout.write("=" * 60)
            self.stdout.write(f"Failed/Cancelled payments deleted: {deleted_failed}")
            self.stdout.write(f"Successful payments deleted: {deleted_successful}")
            self.stdout.write("=" * 60)
            self.stdout.write(self.style.SUCCESS(f"Total records deleted: {total_deleted}"))
            self.stdout.write("=" * 60 + "\n")

            # Show detailed breakdown if verbose
            if options["verbosity"] >= 2:
                self.stdout.write("\nDetailed breakdown:")
                for model, count in {**failed_details, **success_details}.items():
                    if count > 0:
                        self.stdout.write(f"  {model}: {count}")

        except Exception as e:
            raise CommandError(f"Deletion failed: {e}")

    def _import_model(self, model_path: str):
        """
        Import model from string path.

        Args:
            model_path: Full path like 'myapp.models.Order' or 'myapp.Order'

        Returns:
            Model class
        """
        from importlib import import_module

        try:
            # First try direct import (e.g., tests.models.TestPayment)
            if "." in model_path:
                parts = model_path.rsplit(".", 1)
                module_path, model_name = parts

                try:
                    module = import_module(module_path)
                    return getattr(module, model_name)
                except (ImportError, AttributeError):
                    pass

            # Try Django app registry
            parts = model_path.rsplit(".", 1)
            if len(parts) == 2:
                app_label = parts[0].split(".")[-1]
                model_name = parts[1]

                try:
                    return apps.get_model(app_label, model_name)
                except LookupError:
                    pass

            raise ValueError(f"Could not import model '{model_path}'")
        except Exception as e:
            raise ValueError(f"Failed to import model: {e}")

    def _show_sample_payments(self, old_failed, old_successful):
        """Show sample of payments that will be deleted."""
        self.stdout.write("Sample of payments to be deleted:\n")

        # Show failed payments sample
        if old_failed.exists():
            self.stdout.write(self.style.WARNING("Failed/Cancelled:"))
            for payment in old_failed[:5]:
                self.stdout.write(
                    f"  - {payment.payment_id or 'No ID'} | "
                    f"{payment.status} | "
                    f"{payment.amount} {payment.currency} | "
                    f"{payment.created_at.strftime('%Y-%m-%d')}"
                )
            if old_failed.count() > 5:
                self.stdout.write(f"  ... and {old_failed.count() - 5} more\n")

        # Show successful payments sample
        if old_successful.exists():
            self.stdout.write(self.style.WARNING("\nSuccessful:"))
            for payment in old_successful[:5]:
                self.stdout.write(
                    f"  - {payment.payment_id or 'No ID'} | "
                    f"{payment.status} | "
                    f"{payment.amount} {payment.currency} | "
                    f"{payment.created_at.strftime('%Y-%m-%d')}"
                )
            if old_successful.count() > 5:
                self.stdout.write(f"  ... and {old_successful.count() - 5} more\n")

        self.stdout.write("")

    def _export_payments(self, old_failed, old_successful, export_path: str, verbosity: int):
        """
        Export payments to CSV before deletion.

        Args:
            old_failed: QuerySet of failed payments
            old_successful: QuerySet of successful payments
            export_path: Path to CSV file
            verbosity: Verbosity level
        """
        try:
            export_file = Path(export_path)
            export_file.parent.mkdir(parents=True, exist_ok=True)

            self.stdout.write(f"\nExporting payments to {export_path}...")

            with open(export_file, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "payment_id",
                    "conversation_id",
                    "status",
                    "amount",
                    "currency",
                    "buyer_email",
                    "buyer_name",
                    "created_at",
                    "updated_at",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Export failed payments
                for payment in old_failed:
                    writer.writerow(
                        {
                            "payment_id": payment.payment_id or "",
                            "conversation_id": payment.conversation_id or "",
                            "status": payment.status,
                            "amount": str(payment.amount),
                            "currency": payment.currency,
                            "buyer_email": payment.buyer_email or "",
                            "buyer_name": payment.get_buyer_full_name(),
                            "created_at": payment.created_at.isoformat(),
                            "updated_at": payment.updated_at.isoformat(),
                        }
                    )

                # Export successful payments
                for payment in old_successful:
                    writer.writerow(
                        {
                            "payment_id": payment.payment_id or "",
                            "conversation_id": payment.conversation_id or "",
                            "status": payment.status,
                            "amount": str(payment.amount),
                            "currency": payment.currency,
                            "buyer_email": payment.buyer_email or "",
                            "buyer_name": payment.get_buyer_full_name(),
                            "created_at": payment.created_at.isoformat(),
                            "updated_at": payment.updated_at.isoformat(),
                        }
                    )

            total_count = old_failed.count() + old_successful.count()
            self.stdout.write(
                self.style.SUCCESS(f"Exported {total_count} payments to {export_path}\n")
            )

        except Exception as e:
            raise CommandError(f"Export failed: {e}")
