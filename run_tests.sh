#!/bin/bash
#
# Test runner script for django-iyzico
#
# This script sets up the environment and runs all tests with coverage.
#

set -e

echo "==================================="
echo "django-iyzico Test Runner"
echo "==================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -e ".[dev]"

echo ""
echo "==================================="
echo "Running Tests"
echo "==================================="
echo ""

# Run pytest with coverage
pytest tests/ -v --cov=django_iyzico --cov-report=html --cov-report=term-missing

echo ""
echo "==================================="
echo "Coverage Report Generated"
echo "==================================="
echo "View detailed report: open htmlcov/index.html"
echo ""

# Run specific test categories
echo ""
echo "==================================="
echo "Running Test Categories"
echo "==================================="
echo ""

echo "1. Security-Critical Tests (card masking)..."
pytest tests/test_utils.py::TestMaskCardData -v

echo ""
echo "2. Model Tests..."
pytest tests/test_models.py -v

echo ""
echo "3. Client Tests..."
pytest tests/test_client.py -v

echo ""
echo "4. View Tests..."
pytest tests/test_views.py -v

echo ""
echo "5. Signal Tests..."
pytest tests/test_signals.py -v

echo ""
echo "==================================="
echo "All Tests Complete!"
echo "==================================="
