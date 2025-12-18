"""
Tests for django-iyzico signals.

Tests signal definitions and triggering.
"""

from django.dispatch import Signal

from django_iyzico.signals import (
    payment_completed,
    payment_failed,
    payment_initiated,
    payment_refunded,
    threeds_completed,
    threeds_failed,
    threeds_initiated,
    webhook_received,
)


class TestSignalDefinitions:
    """Test that all signals are properly defined."""

    def test_payment_initiated_is_signal(self):
        """Test payment_initiated is a Signal instance."""
        assert isinstance(payment_initiated, Signal)

    def test_payment_completed_is_signal(self):
        """Test payment_completed is a Signal instance."""
        assert isinstance(payment_completed, Signal)

    def test_payment_failed_is_signal(self):
        """Test payment_failed is a Signal instance."""
        assert isinstance(payment_failed, Signal)

    def test_payment_refunded_is_signal(self):
        """Test payment_refunded is a Signal instance."""
        assert isinstance(payment_refunded, Signal)

    def test_threeds_initiated_is_signal(self):
        """Test threeds_initiated is a Signal instance."""
        assert isinstance(threeds_initiated, Signal)

    def test_threeds_completed_is_signal(self):
        """Test threeds_completed is a Signal instance."""
        assert isinstance(threeds_completed, Signal)

    def test_threeds_failed_is_signal(self):
        """Test threeds_failed is a Signal instance."""
        assert isinstance(threeds_failed, Signal)

    def test_webhook_received_is_signal(self):
        """Test webhook_received is a Signal instance."""
        assert isinstance(webhook_received, Signal)


class TestSignalConnection:
    """Test signal connection and disconnection."""

    def test_can_connect_to_payment_completed(self):
        """Test that receivers can connect to payment_completed."""
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs)

        payment_completed.connect(receiver)

        try:
            payment_completed.send(sender=None, test_data="test")
            assert len(received) == 1
            assert received[0]["test_data"] == "test"
        finally:
            payment_completed.disconnect(receiver)

    def test_can_connect_to_threeds_completed(self):
        """Test that receivers can connect to threeds_completed."""
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs)

        threeds_completed.connect(receiver)

        try:
            threeds_completed.send(sender=None, payment_id="123")
            assert len(received) == 1
            assert received[0]["payment_id"] == "123"
        finally:
            threeds_completed.disconnect(receiver)

    def test_can_connect_to_webhook_received(self):
        """Test that receivers can connect to webhook_received."""
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs)

        webhook_received.connect(receiver)

        try:
            webhook_received.send(
                sender=None,
                event_type="payment.success",
                payment_id="123",
            )
            assert len(received) == 1
            assert received[0]["event_type"] == "payment.success"
        finally:
            webhook_received.disconnect(receiver)

    def test_disconnect_prevents_signal_reception(self):
        """Test that disconnecting prevents signal reception."""
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs)

        payment_completed.connect(receiver)
        payment_completed.disconnect(receiver)

        payment_completed.send(sender=None, test_data="test")

        # Should not receive signal after disconnect
        assert len(received) == 0


class TestSignalArguments:
    """Test that signals pass correct arguments."""

    def test_payment_completed_arguments(self):
        """Test payment_completed signal arguments."""
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs)

        payment_completed.connect(receiver)

        try:
            payment_completed.send(
                sender=None,
                payment_id="123",
                conversation_id="conv-123",
                response={"status": "success"},
            )

            assert len(received) == 1
            assert "payment_id" in received[0]
            assert "conversation_id" in received[0]
            assert "response" in received[0]
        finally:
            payment_completed.disconnect(receiver)

    def test_payment_failed_arguments(self):
        """Test payment_failed signal arguments."""
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs)

        payment_failed.connect(receiver)

        try:
            payment_failed.send(
                sender=None,
                error_code="5006",
                error_message="Card declined",
            )

            assert len(received) == 1
            assert "error_code" in received[0]
            assert "error_message" in received[0]
        finally:
            payment_failed.disconnect(receiver)

    def test_webhook_received_arguments(self):
        """Test webhook_received signal arguments."""
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs)

        webhook_received.connect(receiver)

        try:
            webhook_received.send(
                sender=None,
                event_type="payment.success",
                payment_id="123",
                conversation_id="conv-123",
                data={"status": "success"},
            )

            assert len(received) == 1
            assert "event_type" in received[0]
            assert "payment_id" in received[0]
            assert "conversation_id" in received[0]
            assert "data" in received[0]
        finally:
            webhook_received.disconnect(receiver)


class TestMultipleReceivers:
    """Test multiple receivers for same signal."""

    def test_multiple_receivers_all_called(self):
        """Test that all receivers are called when signal is sent."""
        received_1 = []
        received_2 = []

        def receiver_1(sender, **kwargs):
            received_1.append(kwargs)

        def receiver_2(sender, **kwargs):
            received_2.append(kwargs)

        payment_completed.connect(receiver_1)
        payment_completed.connect(receiver_2)

        try:
            payment_completed.send(sender=None, test_data="test")

            assert len(received_1) == 1
            assert len(received_2) == 1
        finally:
            payment_completed.disconnect(receiver_1)
            payment_completed.disconnect(receiver_2)

    def test_receiver_exception_does_not_prevent_other_receivers(self):
        """Test that one receiver's exception doesn't prevent others."""
        received_2 = []

        def failing_receiver(sender, **kwargs):
            raise Exception("Test exception")

        def working_receiver(sender, **kwargs):
            received_2.append(kwargs)

        payment_completed.connect(failing_receiver)
        payment_completed.connect(working_receiver)

        try:
            # Use send_robust to ensure all receivers are called even if one raises
            # send_robust returns a list of (receiver, response) tuples
            # where response is either the return value or an exception
            responses = payment_completed.send_robust(sender=None, test_data="test")

            # Should have responses from both receivers
            assert len(responses) == 2

            # Second receiver should have been called despite first receiver's exception
            assert len(received_2) == 1

            # One response should be an exception
            exceptions = [r for r in responses if isinstance(r[1], Exception)]
            assert len(exceptions) == 1
        finally:
            payment_completed.disconnect(failing_receiver)
            payment_completed.disconnect(working_receiver)


class TestSignalSenderFiltering:
    """Test signal filtering by sender."""

    def test_receiver_can_filter_by_sender(self):
        """Test that receivers can filter signals by sender."""
        received = []

        class TestSender:
            pass

        def receiver(sender, **kwargs):
            received.append((sender, kwargs))

        # Connect with specific sender class
        payment_completed.connect(receiver, sender=TestSender)

        try:
            # Send with matching sender class
            payment_completed.send(sender=TestSender, test_data="test")

            # Send with different sender
            payment_completed.send(sender=None, test_data="other")

            # Should only receive signal from matching sender
            assert len(received) == 1
            assert received[0][0] == TestSender
        finally:
            payment_completed.disconnect(receiver, sender=TestSender)


class TestSignalWeakReferences:
    """Test that signal receivers use weak references properly."""

    def test_receiver_is_garbage_collected(self):
        """Test that receiver is garbage collected when deleted."""
        import weakref

        received = []

        class Receiver:
            def __call__(self, sender, **kwargs):
                received.append(kwargs)

        receiver = Receiver()
        weak_ref = weakref.ref(receiver)

        payment_completed.connect(receiver, weak=True)

        # Receiver should exist
        assert weak_ref() is not None

        # Delete receiver
        del receiver

        # Receiver should be garbage collected
        import gc

        gc.collect()
        assert weak_ref() is None

        # Signal should not raise error even though receiver is gone
        payment_completed.send(sender=None, test_data="test")
