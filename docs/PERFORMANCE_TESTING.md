# Performance Testing Plan for django-iyzico

**Version:** 0.1.0-beta
**Author:** Emre Aladag
**Last Updated:** 2025-12-17

## Table of Contents

1. [Overview](#overview)
2. [Performance Goals](#performance-goals)
3. [Test Environment](#test-environment)
4. [Test Scenarios](#test-scenarios)
5. [Running Performance Tests](#running-performance-tests)
6. [Metrics to Monitor](#metrics-to-monitor)
7. [Optimization Strategies](#optimization-strategies)
8. [Continuous Performance Testing](#continuous-performance-testing)

---

## Overview

This document outlines the performance testing strategy for django-iyzico to ensure the package maintains high performance under various load conditions.

### Key Performance Areas

1. **API Response Time** - Time to process payment requests
2. **Database Performance** - Query efficiency and optimization
3. **Memory Usage** - Memory footprint during operations
4. **Concurrent Requests** - Behavior under load
5. **Webhook Processing** - Speed of webhook handling

---

## Performance Goals

### Target Metrics (v0.1.0-beta)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **API Call Response Time** | < 2 seconds | p95 |
| **Database Query Time** | < 50ms | Average per query |
| **Webhook Processing Time** | < 100ms | Average |
| **Memory Usage** | < 100MB | Per payment operation |
| **Concurrent Payments** | 100 requests/second | Without degradation |
| **Database Connections** | < 10 | During normal operation |

### Acceptable Limits

| Metric | Warning Threshold | Critical Threshold |
|--------|------------------|-------------------|
| API Response Time | 3 seconds | 5 seconds |
| Database Query Time | 100ms | 200ms |
| Webhook Processing | 200ms | 500ms |
| Memory Usage | 150MB | 200MB |
| Error Rate | 1% | 5% |

---

## Test Environment

### Hardware Requirements

```yaml
Minimum Testing Environment:
  CPU: 4 cores
  RAM: 8GB
  Storage: 20GB SSD
  Network: 100 Mbps

Recommended Testing Environment:
  CPU: 8 cores
  RAM: 16GB
  Storage: 50GB SSD
  Network: 1 Gbps
```

### Software Stack

```python
# Required Software
Python: 3.11+
Django: 4.2+ (supports 4.2 LTS, 5.2, 6.0)
PostgreSQL: 12+ (recommended for production testing)
Redis: 6+ (for caching tests)

# Testing Tools
locust: 2.0+  # Load testing
django-debug-toolbar: 3.0+  # Query analysis
memory_profiler: 0.60+  # Memory profiling
pytest-benchmark: 4.0+  # Benchmark tests
```

### Database Configuration

```python
# settings.py - Performance testing configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'iyzico_perf_test',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# Caching for performance tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'iyzico_perf',
        'TIMEOUT': 300,
    }
}
```

---

## Test Scenarios

### 1. Single Payment Processing

**Objective:** Measure baseline performance for individual payment processing.

**Test Cases:**
- Direct payment (non-3D Secure)
- 3D Secure payment initialization
- 3D Secure payment completion
- Payment with basket items (1, 5, 10, 20 items)

**Expected Results:**
- Single payment: < 1 second
- 3DS initialization: < 1.5 seconds
- 3DS completion: < 1 second

### 2. Database Query Performance

**Objective:** Ensure database operations are optimized.

**Test Cases:**
- Payment creation and save
- Payment retrieval by payment_id
- Payment retrieval by conversation_id
- Bulk payment queries (100, 1000, 10000 records)
- Admin list view queries
- Filter queries (status, date range, amount)

**Expected Results:**
- Single record retrieval: < 10ms
- Bulk queries (1000 records): < 100ms
- Admin list view: < 200ms (with pagination)

### 3. Concurrent Payment Processing

**Objective:** Test behavior under concurrent load.

**Test Cases:**
- 10 concurrent payments
- 50 concurrent payments
- 100 concurrent payments
- 500 concurrent payments

**Expected Results:**
- No payment failures due to concurrency
- Response time degradation < 50% at 100 concurrent
- Database connection pool remains stable

### 4. Webhook Processing

**Objective:** Measure webhook handling performance.

**Test Cases:**
- Single webhook processing
- Burst of 100 webhooks
- Webhook signature validation overhead
- Webhook IP whitelist checking

**Expected Results:**
- Single webhook: < 50ms
- Webhook burst: < 100ms average
- Signature validation overhead: < 10ms

### 5. Refund Processing

**Objective:** Test refund operation performance.

**Test Cases:**
- Single full refund
- Single partial refund
- Bulk refunds (10, 50, 100 orders)
- Concurrent refund requests

**Expected Results:**
- Single refund: < 2 seconds
- Bulk refunds (100): < 5 minutes
- No database deadlocks

### 6. Admin Interface Performance

**Objective:** Ensure admin remains responsive with large datasets.

**Test Cases:**
- List view with 10k payments
- List view with 100k payments
- Filtering and searching
- Bulk actions (export, refund)
- Detail view with large raw_response JSON

**Expected Results:**
- List view (paginated): < 500ms
- Search queries: < 300ms
- Bulk export (1000 records): < 10 seconds

### 7. Memory Usage

**Objective:** Prevent memory leaks and excessive memory consumption.

**Test Cases:**
- Memory usage during 1000 sequential payments
- Memory usage during 100 concurrent payments
- Memory usage in long-running process
- Memory leak detection

**Expected Results:**
- Memory usage stable over time
- No memory leaks detected
- Max memory per payment: < 5MB

---

## Running Performance Tests

### Setup

```bash
# 1. Install performance testing dependencies
pip install -e ".[dev]"
pip install locust pytest-benchmark memory-profiler django-debug-toolbar

# 2. Set up performance test database
createdb iyzico_perf_test
python manage.py migrate

# 3. Load test data
python manage.py loaddata tests/fixtures/performance_data.json

# Or generate test data:
python manage.py shell
>>> from tests.performance.generate_data import generate_test_payments
>>> generate_test_payments(count=10000)
```

### Running Benchmark Tests

```bash
# Run all benchmark tests
pytest tests/performance/test_benchmarks.py -v

# Run specific benchmark
pytest tests/performance/test_benchmarks.py::test_payment_creation_benchmark -v

# Compare with baseline
pytest tests/performance/test_benchmarks.py --benchmark-compare=baseline

# Save new baseline
pytest tests/performance/test_benchmarks.py --benchmark-save=baseline
```

### Running Load Tests with Locust

```bash
# Start Locust web interface
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Run headless (command-line)
locust -f tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless

# Generate report
locust -f tests/performance/locustfile.py \
    --host=http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 5m \
    --headless \
    --html=performance_report.html
```

### Memory Profiling

```bash
# Profile memory usage
python -m memory_profiler tests/performance/profile_memory.py

# Profile specific function
python tests/performance/profile_payment.py

# Generate memory usage graph
mprof run tests/performance/profile_payment.py
mprof plot
```

### Database Query Analysis

```python
# Using Django Debug Toolbar
# 1. Add to INSTALLED_APPS in test settings
INSTALLED_APPS += ['debug_toolbar']

# 2. Enable SQL logging
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
        }
    }
}

# 3. Use Django shell to analyze queries
python manage.py shell_plus --print-sql

>>> from myapp.models import Order
>>> orders = Order.objects.filter(status='success').select_related('user')
>>> # Examine SQL queries
```

---

## Metrics to Monitor

### Application Metrics

```python
# Key metrics to track

1. Payment Processing Metrics:
   - Average payment creation time
   - Payment success rate
   - Payment failure rate
   - 3DS conversion rate

2. Database Metrics:
   - Query count per request
   - Average query time
   - Slow query count (> 100ms)
   - Connection pool usage
   - Database CPU usage

3. Cache Metrics:
   - Cache hit rate
   - Cache miss rate
   - Average cache response time

4. API Metrics:
   - Iyzico API response time
   - Iyzico API error rate
   - API timeout rate

5. System Metrics:
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network I/O
```

### Monitoring Tools

```yaml
Application Performance Monitoring (APM):
  - New Relic
  - Datadog
  - Sentry (for error tracking)
  - Prometheus + Grafana

Database Monitoring:
  - pgBadger (PostgreSQL)
  - pg_stat_statements
  - Django Debug Toolbar

Custom Metrics:
  - Django middleware for timing
  - Custom logging
  - Statsd for metrics collection
```

---

## Optimization Strategies

### 1. Database Optimization

```python
# Query optimization techniques

# ✅ Good: Use select_related for foreign keys
orders = Order.objects.select_related('user', 'subscription')

# ✅ Good: Use prefetch_related for reverse relations
users = User.objects.prefetch_related('orders')

# ✅ Good: Use only() to fetch specific fields
orders = Order.objects.only('id', 'payment_id', 'amount', 'status')

# ✅ Good: Use defer() to exclude large fields
orders = Order.objects.defer('raw_response')

# ✅ Good: Use bulk operations
Order.objects.bulk_create(order_list)
Order.objects.bulk_update(order_list, ['status'])

# ❌ Bad: N+1 queries
for order in Order.objects.all():
    print(order.user.email)  # Separate query for each order

# ✅ Good: Single query with select_related
for order in Order.objects.select_related('user'):
    print(order.user.email)  # No extra queries
```

### 2. Caching Strategies

```python
# Cache frequently accessed data

from django.core.cache import cache
from django.views.decorators.cache import cache_page

# Cache view results
@cache_page(60 * 15)  # Cache for 15 minutes
def payment_stats(request):
    # ...

# Cache querysets
def get_successful_payments():
    cache_key = 'successful_payments'
    result = cache.get(cache_key)

    if result is None:
        result = list(Order.objects.filter(status='success'))
        cache.set(cache_key, result, 60 * 15)  # 15 minutes

    return result

# Cache expensive computations
def get_monthly_revenue():
    cache_key = 'monthly_revenue'
    result = cache.get(cache_key)

    if result is None:
        result = Order.objects.filter(
            status='success',
            created_at__month=timezone.now().month
        ).aggregate(total=Sum('amount'))['total']

        cache.set(cache_key, result, 60 * 60)  # 1 hour

    return result
```

### 3. API Call Optimization

```python
# Minimize and optimize Iyzico API calls

# ✅ Good: Batch webhook processing
def process_webhooks_batch(webhook_data_list):
    with transaction.atomic():
        for data in webhook_data_list:
            process_webhook(data)

# ✅ Good: Cache Iyzico settings
# (Already implemented in IyzicoClient)

# ✅ Good: Use connection pooling
# Configure in settings.py:
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,
    }
}
```

### 4. Memory Optimization

```python
# Reduce memory usage

# ✅ Good: Use iterators for large querysets
for order in Order.objects.iterator(chunk_size=100):
    process_order(order)

# ✅ Good: Use values() for simple data
order_data = Order.objects.values('id', 'payment_id', 'amount')

# ✅ Good: Clear querysets when done
orders = Order.objects.filter(status='success')
process_orders(orders)
orders = None  # Free memory

# ❌ Bad: Loading all objects into memory
all_orders = list(Order.objects.all())  # Can use GBs of memory
```

### 5. Index Optimization

```python
# Ensure proper database indexes

# Already included in AbstractIyzicoPayment:
class Meta:
    indexes = [
        models.Index(fields=['payment_id']),
        models.Index(fields=['conversation_id']),
        models.Index(fields=['status']),
        models.Index(fields=['created_at']),
        models.Index(fields=['-created_at']),
        models.Index(fields=['buyer_email']),
    ]

# Add custom indexes for your use case:
class Order(AbstractIyzicoPayment):
    class Meta:
        indexes = AbstractIyzicoPayment.Meta.indexes + [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['created_at', 'status']),
        ]
```

---

## Continuous Performance Testing

### CI/CD Integration

```yaml
# .github/workflows/performance.yml
name: Performance Tests

on:
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday

jobs:
  performance:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install pytest-benchmark locust

      - name: Run benchmark tests
        run: |
          pytest tests/performance/test_benchmarks.py \
            --benchmark-only \
            --benchmark-compare=baseline \
            --benchmark-compare-fail=mean:10%

      - name: Run load tests
        run: |
          locust -f tests/performance/locustfile.py \
            --host=http://localhost:8000 \
            --users 50 \
            --spawn-rate 5 \
            --run-time 2m \
            --headless \
            --html=performance_report.html

      - name: Upload performance report
        uses: actions/upload-artifact@v3
        with:
          name: performance-report
          path: performance_report.html
```

### Performance Regression Detection

```python
# tests/performance/test_benchmarks.py
import pytest
from decimal import Decimal
from django_iyzico.client import IyzicoClient
from myapp.models import Order

@pytest.mark.benchmark
def test_payment_creation_benchmark(benchmark):
    """Benchmark payment creation time."""

    def create_payment():
        order = Order.objects.create(
            conversation_id=f"BENCH-{uuid.uuid4()}",
            amount=Decimal("100.00"),
        )
        return order

    result = benchmark(create_payment)
    assert result is not None

@pytest.mark.benchmark
def test_payment_query_benchmark(benchmark):
    """Benchmark payment retrieval time."""

    # Setup: Create test payment
    order = Order.objects.create(
        payment_id="test-payment-123",
        amount=Decimal("100.00"),
    )

    def query_payment():
        return Order.objects.get(payment_id="test-payment-123")

    result = benchmark(query_payment)
    assert result.payment_id == "test-payment-123"
```

### Performance Dashboard

```python
# Create custom management command for performance metrics

# management/commands/performance_report.py
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    help = 'Generate performance metrics report'

    def handle(self, *args, **options):
        now = timezone.now()
        last_hour = now - timedelta(hours=1)

        from myapp.models import Order

        metrics = {
            'total_payments': Order.objects.filter(
                created_at__gte=last_hour
            ).count(),

            'successful_payments': Order.objects.filter(
                created_at__gte=last_hour,
                status='success'
            ).count(),

            'failed_payments': Order.objects.filter(
                created_at__gte=last_hour,
                status='failed'
            ).count(),

            'average_amount': Order.objects.filter(
                created_at__gte=last_hour,
                status='success'
            ).aggregate(avg=Avg('amount'))['avg'],
        }

        self.stdout.write(self.style.SUCCESS('Performance Metrics (Last Hour):'))
        self.stdout.write(f"Total Payments: {metrics['total_payments']}")
        self.stdout.write(f"Successful: {metrics['successful_payments']}")
        self.stdout.write(f"Failed: {metrics['failed_payments']}")
        self.stdout.write(f"Average Amount: {metrics['average_amount']}")

        # Success rate
        if metrics['total_payments'] > 0:
            success_rate = (
                metrics['successful_payments'] / metrics['total_payments'] * 100
            )
            self.stdout.write(f"Success Rate: {success_rate:.2f}%")
```

---

## Conclusion

Regular performance testing ensures django-iyzico maintains high performance as the codebase evolves. Follow this plan to:

1. Establish performance baselines
2. Detect performance regressions early
3. Optimize critical paths
4. Ensure scalability

**Next Steps:**
1. Implement benchmark tests
2. Set up load testing with Locust
3. Configure CI/CD performance tests
4. Monitor production performance metrics

---

**Related Documents:**
- [Development Roadmap](DEVELOPMENT_ROADMAP.md)
- [Security Audit](SECURITY_AUDIT.md)
- [System Design](SYSTEM_DESIGN.md)
