# Contributing to django-iyzico

Thank you for your interest in contributing to django-iyzico!

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/aladagemre/django-iyzico.git
cd django-iyzico
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
make install
# or
pip install -e ".[dev]"
```

### 3. Run Tests

```bash
make test
# or
pytest
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Write code
- Add tests
- Update documentation

### 3. Format Code

```bash
make format
# Runs black and isort
```

### 4. Run Linters

```bash
make lint
# Runs flake8 and mypy
```

### 5. Run Tests

```bash
make test-cov
# Runs tests with coverage report
```

### 6. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

**Commit Message Format:**
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test changes
- `refactor:` Code refactoring
- `chore:` Maintenance tasks

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Standards

### Python Style

- Follow PEP 8
- Use Black for formatting (line length: 100)
- Use isort for import sorting
- Use type hints

### Testing

- Write tests for all new features
- Maintain >90% code coverage
- Use pytest fixtures
- Mock external APIs (Iyzico)

### Documentation

- Add docstrings to all public functions/classes
- Update README.md if needed
- Add examples for new features
- Keep docs in sync with code

## Project Structure

```
django-iyzico/
├── django_iyzico/       # Main package
│   ├── __init__.py
│   ├── client.py        # Iyzico client wrapper
│   ├── models.py        # Django models
│   ├── views.py         # Django views
│   ├── admin.py         # Admin interface
│   ├── signals.py       # Django signals
│   └── utils.py         # Utilities
├── tests/               # Test suite
├── docs/                # Documentation
└── examples/            # Usage examples
```

## Questions?

- Open an issue on GitHub
- Email: your-email@example.com

Thank you for contributing!
