"""
Locust load testing script for django-iyzico

This script simulates realistic user behavior for payment processing
to test system performance under load.

Usage:
    # Web UI mode:
    locust -f locustfile.py --host=http://localhost:8000

    # Headless mode:
    locust -f locustfile.py --host=http://localhost:8000 \
        --users 100 --spawn-rate 10 --run-time 5m --headless

    # Generate HTML report:
    locust -f locustfile.py --host=http://localhost:8000 \
        --users 100 --spawn-rate 10 --run-time 5m \
        --headless --html=report.html

Author: Emre Aladag
Version: 0.1.0-beta
"""

import random
import uuid
from decimal import Decimal

from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask


class IyzicoPaymentUser(HttpUser):
    """
    Simulates a user making payments through the system.

    This user performs various payment-related operations with
    realistic timing and behavior patterns.
    """

    # Wait 1-5 seconds between tasks (simulates user think time)
    wait_time = between(1, 5)

    def on_start(self):
        """Initialize test data when user starts."""
        self.conversation_id = None
        self.payment_id = None
        self.auth_token = None

        # Login (if authentication is required)
        self.login()

    def login(self):
        """Authenticate user (modify based on your auth system)."""
        # Example login - adjust for your authentication
        response = self.client.post(
            "/api/auth/login/",
            json={
                "username": f"test_user_{uuid.uuid4().hex[:8]}",
                "password": "testpassword123",
            },
        )

        if response.status_code == 200:
            self.auth_token = response.json().get("token")

    @task(10)
    def create_direct_payment(self):
        """
        Task: Create a direct payment (non-3D Secure).

        Weight: 10 (most common operation)
        """
        conversation_id = f"LOAD-{uuid.uuid4()}"
        amount = Decimal(random.choice(["10.00", "50.00", "100.00", "250.00", "500.00"]))

        payment_data = {
            "conversationId": conversation_id,
            "price": str(amount),
            "paidPrice": str(amount),
            "currency": "TRY",
            "basketId": f"BASKET-{uuid.uuid4()}",
            "installment": 1,
            "paymentCard": {
                "cardHolderName": "Test User",
                "cardNumber": "5528790000000008",
                "expireMonth": "12",
                "expireYear": "2030",
                "cvc": "123",
            },
            "buyer": {
                "id": str(uuid.uuid4()),
                "name": "Test",
                "surname": "User",
                "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
                "identityNumber": "11111111111",
                "registrationAddress": "Test Address",
                "city": "Istanbul",
                "country": "Turkey",
                "zipCode": "34000",
            },
            "billingAddress": {
                "address": "Test Address",
                "city": "Istanbul",
                "country": "Turkey",
                "zipCode": "34000",
            },
        }

        with self.client.post(
            "/api/payments/create/",
            json=payment_data,
            catch_response=True,
            name="Create Direct Payment",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.conversation_id = conversation_id
                    self.payment_id = data.get("payment_id")
                    response.success()
                else:
                    response.failure(f"Payment failed: {data.get('error_message')}")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(5)
    def create_3ds_payment(self):
        """
        Task: Initialize 3D Secure payment.

        Weight: 5 (common operation)
        """
        conversation_id = f"3DS-{uuid.uuid4()}"
        amount = Decimal(random.choice(["100.00", "250.00", "500.00"]))

        payment_data = {
            "conversationId": conversation_id,
            "price": str(amount),
            "paidPrice": str(amount),
            "currency": "TRY",
            "basketId": f"BASKET-{uuid.uuid4()}",
            "installment": 1,
            "callbackUrl": "http://localhost:8000/payments/callback/",
            "paymentCard": {
                "cardHolderName": "Test User",
                "cardNumber": "5528790000000008",
                "expireMonth": "12",
                "expireYear": "2030",
                "cvc": "123",
            },
            "buyer": {
                "id": str(uuid.uuid4()),
                "name": "Test",
                "surname": "User",
                "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
                "identityNumber": "11111111111",
                "registrationAddress": "Test Address",
                "city": "Istanbul",
                "country": "Turkey",
                "zipCode": "34000",
            },
            "billingAddress": {
                "address": "Test Address",
                "city": "Istanbul",
                "country": "Turkey",
                "zipCode": "34000",
            },
        }

        with self.client.post(
            "/api/payments/create-3ds/",
            json=payment_data,
            catch_response=True,
            name="Initialize 3DS Payment",
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    response.success()
                else:
                    response.failure(f"3DS initialization failed")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(3)
    def list_payments(self):
        """
        Task: List payments (API endpoint).

        Weight: 3 (frequent read operation)
        """
        params = {
            "page": random.randint(1, 5),
            "page_size": 20,
        }

        with self.client.get(
            "/api/payments/",
            params=params,
            catch_response=True,
            name="List Payments",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def get_payment_detail(self):
        """
        Task: Get payment details.

        Weight: 2 (common read operation)
        """
        if not self.payment_id:
            # Skip if no payment created yet
            raise RescheduleTask()

        with self.client.get(
            f"/api/payments/{self.payment_id}/",
            catch_response=True,
            name="Get Payment Detail",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                # Payment not found - expected if it was from previous run
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def process_refund(self):
        """
        Task: Process refund.

        Weight: 1 (less frequent operation)
        """
        if not self.payment_id:
            raise RescheduleTask()

        refund_data = {
            "payment_id": self.payment_id,
            "reason": "Load test refund",
        }

        with self.client.post(
            "/api/payments/refund/",
            json=refund_data,
            catch_response=True,
            name="Process Refund",
        ) as response:
            if response.status_code in [200, 400]:
                # 200 = success, 400 = already refunded (expected in tests)
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def get_payment_stats(self):
        """
        Task: Get payment statistics.

        Weight: 2 (dashboard/reporting queries)
        """
        params = {
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        }

        with self.client.get(
            "/api/payments/stats/",
            params=params,
            catch_response=True,
            name="Get Payment Stats",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def simulate_webhook(self):
        """
        Task: Simulate webhook callback.

        Weight: 1 (background process)
        """
        webhook_data = {
            "paymentId": f"webhook-{uuid.uuid4()}",
            "conversationId": f"WEBHOOK-{uuid.uuid4()}",
            "status": "success",
            "price": "100.00",
            "paidPrice": "100.00",
            "currency": "TRY",
        }

        with self.client.post(
            "/payments/webhook/",
            json=webhook_data,
            catch_response=True,
            name="Webhook Callback",
        ) as response:
            if response.status_code in [200, 400]:
                # 200 = processed, 400 = validation error (expected)
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class AdminUser(HttpUser):
    """
    Simulates admin user accessing Django admin interface.

    Tests admin panel performance under load.
    """

    wait_time = between(2, 8)

    def on_start(self):
        """Login as admin."""
        self.client.post(
            "/admin/login/",
            {
                "username": "admin",
                "password": "admin",
            },
        )

    @task(5)
    def view_payment_list(self):
        """View payment list in admin."""
        with self.client.get(
            "/admin/myapp/order/",
            catch_response=True,
            name="Admin: Payment List",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def view_payment_detail(self):
        """View payment detail in admin."""
        # Random payment ID (will 404 for non-existent)
        payment_id = random.randint(1, 1000)

        with self.client.get(
            f"/admin/myapp/order/{payment_id}/change/",
            catch_response=True,
            name="Admin: Payment Detail",
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def export_payments_csv(self):
        """Export payments as CSV."""
        with self.client.get(
            "/admin/myapp/order/?action=export_csv",
            catch_response=True,
            name="Admin: Export CSV",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


# Event hooks for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print("🚀 Starting django-iyzico performance test...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops - print summary."""
    print("✅ Performance test completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failed requests: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"Max response time: {environment.stats.total.max_response_time:.2f}ms")

    # Check if performance goals are met
    avg_response = environment.stats.total.avg_response_time
    failure_rate = (
        environment.stats.total.num_failures / environment.stats.total.num_requests * 100
        if environment.stats.total.num_requests > 0
        else 0
    )

    print("\n📊 Performance Goals:")
    print(
        f"Average Response Time: {avg_response:.2f}ms (Goal: < 2000ms) "
        f"{'✅' if avg_response < 2000 else '❌'}"
    )
    print(
        f"Failure Rate: {failure_rate:.2f}% (Goal: < 1%) " f"{'✅' if failure_rate < 1 else '❌'}"
    )


# Custom shape for realistic load pattern
from locust import LoadTestShape


class StepLoadShape(LoadTestShape):
    """
    A step load shape that gradually increases load.

    Simulates realistic traffic patterns:
    - Start with 10 users
    - Increase by 10 every minute
    - Up to 100 users
    - Run for 10 minutes total
    """

    step_time = 60  # 1 minute per step
    step_load = 10  # Add 10 users per step
    spawn_rate = 5
    time_limit = 600  # 10 minutes total

    def tick(self):
        """Return (user_count, spawn_rate) at current time."""
        run_time = self.get_run_time()

        if run_time > self.time_limit:
            return None

        current_step = run_time // self.step_time
        user_count = min(current_step * self.step_load + 10, 100)

        return (user_count, self.spawn_rate)
