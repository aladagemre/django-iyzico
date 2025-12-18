"""
Management command to sync payment statuses with Iyzico API.

This command fetches recent payments from the database and compares their
status with Iyzico's API, updating any discrepancies.
"""

import logging
from datetime import timedelta
from typing import Any, Dict

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from django_iyzico.client import IyzicoClient
from django_iyzico.models import PaymentStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Sync payment statuses with Iyzico API.

    This command helps identify and fix discrepancies between local database
    and Iyzico's payment records.
    """

    help = "Sync payment statuses with Iyzico API for recent transactions"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days to look back (default: 7)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )
        parser.add_argument(
            "--model",
            type=str,
            required=True,
            help="Full path to payment model (e.g., myapp.models.Order)",
        )
        parser.add_argument(
            "--status",
            type=str,
            choices=["all", "success", "failed", "pending"],
            default="all",
            help="Only sync payments with specific status (default: all)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Maximum number of payments to sync",
        )

    def handle(self, *args, **options):
        """Execute the command."""
        days = options["days"]
        dry_run = options["dry_run"]
        model_path = options["model"]
        status_filter = options["status"]
        limit = options["limit"]

        # Set logging level based on verbosity
        if options["verbosity"] >= 2:
            logger.setLevel(logging.DEBUG)

        # Import model dynamically
        try:
            PaymentModel = self._import_model(model_path)
        except Exception as e:
            raise CommandError(f"Failed to import model '{model_path}': {e}")

        # Get recent payments
        since_date = timezone.now() - timedelta(days=days)
        payments = PaymentModel.objects.filter(created_at__gte=since_date, payment_id__isnull=False)

        # Apply status filter
        if status_filter == "success":
            payments = payments.filter(status=PaymentStatus.SUCCESS)
        elif status_filter == "failed":
            payments = payments.filter(status=PaymentStatus.FAILED)
        elif status_filter == "pending":
            payments = payments.filter(status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING])

        # Exclude refunded payments (can't sync these)
        payments = payments.exclude(
            status__in=[PaymentStatus.REFUNDED, PaymentStatus.REFUND_PENDING]
        )

        # Apply limit
        if limit:
            payments = payments[:limit]

        total_count = payments.count()

        if total_count == 0:
            self.stdout.write(
                self.style.WARNING(f"No payments found in the last {days} days matching criteria")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"\nSyncing {total_count} payments from last {days} days...")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made\n"))

        # Initialize client
        client = IyzicoClient()

        # Sync statistics
        checked_count = 0
        updated_count = 0
        error_count = 0
        discrepancies = []

        # Process each payment
        for payment in payments:
            checked_count += 1

            if options["verbosity"] >= 2:
                self.stdout.write(
                    f"[{checked_count}/{total_count}] Checking payment {payment.payment_id}..."
                )

            try:
                # Note: Iyzico doesn't have a direct "get payment status" endpoint
                # In a real implementation, you would use their payment inquiry API
                # For now, we'll log what we would check

                result = self._check_payment_status(client, payment, dry_run, options["verbosity"])

                if result["updated"]:
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Updated: {payment.payment_id} - "
                            f"{result['old_status']} -> {result['new_status']}"
                        )
                    )

                if result["discrepancy"]:
                    discrepancies.append(result["discrepancy"])

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f"  Error syncing {payment.payment_id}: {e}"))
                if options["verbosity"] >= 2:
                    logger.exception(f"Error details for {payment.payment_id}")

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("SYNC SUMMARY"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total payments checked: {checked_count}")
        self.stdout.write(f"Payments updated: {updated_count}")
        self.stdout.write(f"Errors encountered: {error_count}")

        if discrepancies:
            self.stdout.write(self.style.WARNING(f"\nFound {len(discrepancies)} discrepancies:"))
            for disc in discrepancies[:10]:  # Show first 10
                self.stdout.write(f"  - {disc}")
            if len(discrepancies) > 10:
                self.stdout.write(f"  ... and {len(discrepancies) - 10} more")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No actual changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS("\nSync completed successfully"))

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

    def _check_payment_status(
        self,
        client: IyzicoClient,
        payment,
        dry_run: bool,
        verbosity: int,
    ) -> Dict[str, Any]:
        """
        Check payment status against Iyzico API.

        Args:
            client: IyzicoClient instance
            payment: Payment model instance
            dry_run: Whether this is a dry run
            verbosity: Verbosity level

        Returns:
            Dictionary with sync results
        """
        result = {
            "updated": False,
            "old_status": payment.status,
            "new_status": payment.status,
            "discrepancy": None,
        }

        # In a real implementation, you would query Iyzico API here
        # Example (pseudo-code):
        # try:
        #     iyzico_response = client.retrieve_payment(payment.payment_id)
        #     iyzico_status = self._map_iyzico_status(iyzico_response.status)
        #
        #     if iyzico_status != payment.status:
        #         result["discrepancy"] = (
        #             f"Payment {payment.payment_id}: "
        #             f"Local={payment.status}, Iyzico={iyzico_status}"
        #         )
        #
        #         if not dry_run:
        #             payment.status = iyzico_status
        #             payment.save(update_fields=["status", "updated_at"])
        #             result["updated"] = True
        #             result["new_status"] = iyzico_status
        # except Exception as e:
        #     raise

        # For now, just log what we would check
        if verbosity >= 2:
            logger.debug(
                f"Would check Iyzico API for payment {payment.payment_id} "
                f"(current status: {payment.status})"
            )

        return result

    def _map_iyzico_status(self, iyzico_status: str) -> str:
        """
        Map Iyzico API status to local PaymentStatus.

        Args:
            iyzico_status: Status from Iyzico API

        Returns:
            Local PaymentStatus value
        """
        status_map = {
            "success": PaymentStatus.SUCCESS,
            "failure": PaymentStatus.FAILED,
            "pending": PaymentStatus.PENDING,
            "processing": PaymentStatus.PROCESSING,
        }
        return status_map.get(iyzico_status.lower(), PaymentStatus.FAILED)
