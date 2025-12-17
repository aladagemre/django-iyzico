# PyPI Publication Guide - django-iyzico v0.1.0-beta

**Package:** django-iyzico
**Version:** 0.1.0b1
**Status:** Ready for Beta Release

---

## Prerequisites

### 1. Install Required Tools

```bash
# Install twine for uploading to PyPI
pip install --upgrade twine

# Verify installation
twine --version
```

### 2. PyPI Accounts

You need accounts on both platforms:

- **TestPyPI:** https://test.pypi.org/account/register/
- **PyPI:** https://pypi.org/account/register/

### 3. API Tokens

Create API tokens for secure authentication:

**TestPyPI:**
1. Log in to https://test.pypi.org
2. Go to Account Settings → API Tokens
3. Click "Add API token"
4. Name: `django-iyzico-test`
5. Scope: "Entire account" (or specific to django-iyzico)
6. Copy the token (starts with `pypi-...`)

**PyPI:**
1. Log in to https://pypi.org
2. Go to Account Settings → API Tokens
3. Click "Add API token"
4. Name: `django-iyzico-prod`
5. Scope: "Entire account" (or specific to django-iyzico after first upload)
6. Copy the token (starts with `pypi-...`)

### 4. Configure PyPI Credentials

Create or update `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-PRODUCTION-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TEST-TOKEN-HERE
```

**Security:** Make sure this file has restricted permissions:
```bash
chmod 600 ~/.pypirc
```

---

## Pre-Publication Checklist

Before publishing, verify:

- [x] ✅ Version bumped to 0.1.0b1 in `pyproject.toml`
- [x] ✅ CHANGELOG.md updated with release notes
- [x] ✅ README.md polished for PyPI
- [x] ✅ SECURITY.md created
- [x] ✅ Security audit completed
- [x] ✅ All tests passing (291/291)
- [x] ✅ Test coverage at 95%+
- [x] ✅ Package builds successfully
- [x] ✅ Package installs successfully
- [x] ✅ LICENSE file present
- [x] ✅ MANIFEST.in includes all necessary files
- [x] ✅ pyproject.toml metadata complete
- [ ] ⏳ Git repository clean (no uncommitted changes)
- [ ] ⏳ Git tag created for release
- [ ] ⏳ Tested on TestPyPI

---

## Step-by-Step Publication Process

### Step 1: Clean Previous Builds

```bash
# Remove old build artifacts
rm -rf build/ dist/ *.egg-info

# Verify clean slate
ls dist/  # Should show: No such file or directory
```

### Step 2: Build the Package

```bash
# Activate virtual environment
source venv/bin/activate

# Build both wheel and source distribution
python -m build

# Verify build outputs
ls -lh dist/
```

**Expected output:**
```
django_iyzico-0.1.0b1-py3-none-any.whl  # Wheel package (~44KB)
django_iyzico-0.1.0b1.tar.gz            # Source distribution (~49KB)
```

### Step 3: Verify Package Contents

```bash
# Check wheel contents
unzip -l dist/django_iyzico-0.1.0b1-py3-none-any.whl

# Check source distribution contents
tar -tzf dist/django_iyzico-0.1.0b1.tar.gz

# Verify metadata
twine check dist/*
```

**Expected:** `Checking dist/* ... PASSED`

### Step 4: Upload to TestPyPI (RECOMMENDED FIRST)

```bash
# Upload to TestPyPI for testing
twine upload --repository testpypi dist/*

# You'll see:
# Uploading distributions to https://test.pypi.org/legacy/
# Uploading django_iyzico-0.1.0b1-py3-none-any.whl
# Uploading django_iyzico-0.1.0b1.tar.gz
```

**View on TestPyPI:** https://test.pypi.org/project/django-iyzico/

### Step 5: Test Installation from TestPyPI

```bash
# Create a test virtual environment
python -m venv test_env
source test_env/bin/activate

# Install from TestPyPI (with dependencies from PyPI)
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            django-iyzico==0.1.0b1

# Test import
python -c "import django_iyzico; print(django_iyzico.__version__)"

# Clean up
deactivate
rm -rf test_env
```

### Step 6: Commit and Tag Release (If Not Done)

```bash
# Check status
git status

# Add all changes
git add .

# Commit release preparation
git commit -m "chore: Prepare v0.1.0-beta release

- Updated pyproject.toml with beta version
- Created CHANGELOG.md, SECURITY.md, RELEASE_NOTES.md
- Updated README.md for PyPI
- Completed security audit
- Built and tested package

Ready for PyPI publication."

# Create annotated tag
git tag -a v0.1.0-beta -m "Release v0.1.0-beta

First beta release of django-iyzico.

Features:
- Complete payment processing (direct + 3D Secure)
- PCI DSS compliant security
- Django admin integration
- Webhook handling
- Refund processing
- 291 passing tests, 95% coverage

See CHANGELOG.md and RELEASE_NOTES.md for details."

# Push to GitHub
git push origin main
git push origin v0.1.0-beta
```

### Step 7: Upload to Production PyPI

⚠️ **WARNING:** This step is **irreversible**. Once uploaded, you cannot delete or re-upload the same version.

**Final checks before uploading:**
```bash
# Verify version is correct
grep version pyproject.toml

# Verify tests pass
pytest

# Verify package builds
python -m build

# Verify package contents
twine check dist/*
```

**Upload to PyPI:**
```bash
# Upload to production PyPI
twine upload dist/*

# You'll see:
# Uploading distributions to https://upload.pypi.org/legacy/
# Uploading django_iyzico-0.1.0b1-py3-none-any.whl
# Uploading django_iyzico-0.1.0b1.tar.gz
# View at: https://pypi.org/project/django-iyzico/0.1.0b1/
```

**View on PyPI:** https://pypi.org/project/django-iyzico/

### Step 8: Verify Production Installation

```bash
# Create fresh test environment
python -m venv prod_test_env
source prod_test_env/bin/activate

# Install from production PyPI
pip install django-iyzico==0.1.0b1

# Verify installation
python -c "
import django_iyzico
print(f'Version: {django_iyzico.__version__}')
print(f'Author: {django_iyzico.__author__}')
print('✅ Package installed successfully from PyPI!')
"

# Clean up
deactivate
rm -rf prod_test_env
```

### Step 9: Create GitHub Release

1. Go to https://github.com/aladagemre/django-iyzico/releases/new
2. Choose tag: `v0.1.0-beta`
3. Release title: `v0.1.0-beta - First Beta Release`
4. Copy content from `RELEASE_NOTES.md` into description
5. Mark as "pre-release" (since it's beta)
6. Attach build artifacts (optional):
   - `dist/django_iyzico-0.1.0b1-py3-none-any.whl`
   - `dist/django_iyzico-0.1.0b1.tar.gz`
7. Click "Publish release"

### Step 10: Announce Release

**Twitter/X:**
```
🚀 django-iyzico v0.1.0-beta is now available on PyPI!

A complete Django integration for Iyzico payment gateway 🇹🇷

✅ PCI DSS compliant
✅ 3D Secure support
✅ Django admin integration
✅ 95% test coverage

pip install django-iyzico

https://github.com/aladagemre/django-iyzico
```

**Reddit (r/django):**
```
Title: [Release] django-iyzico v0.1.0-beta - Django integration for Iyzico payment gateway

Body: (Copy key highlights from RELEASE_NOTES.md)
```

**Django Forum:**
Post in "Show and Tell" category

---

## One-Command Publication (For Future Releases)

After the first release, you can use this streamlined process:

```bash
#!/bin/bash
# publish.sh - Automated publication script

set -e  # Exit on any error

echo "🚀 Django-Iyzico Publication Script"
echo "===================================="

# 1. Clean
echo "🧹 Cleaning old builds..."
rm -rf build/ dist/ *.egg-info

# 2. Build
echo "📦 Building package..."
python -m build

# 3. Verify
echo "✅ Verifying package..."
twine check dist/*

# 4. Test on TestPyPI
echo "🧪 Uploading to TestPyPI..."
twine upload --repository testpypi dist/*

echo ""
echo "✅ Uploaded to TestPyPI: https://test.pypi.org/project/django-iyzico/"
echo ""
echo "Please test the package:"
echo "  pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ django-iyzico"
echo ""
read -p "If tests pass, upload to production PyPI? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    echo "📤 Uploading to production PyPI..."
    twine upload dist/*
    echo ""
    echo "✅ Published to PyPI: https://pypi.org/project/django-iyzico/"
    echo "🎉 Release complete!"
else
    echo "❌ Production upload cancelled"
    exit 1
fi
```

Make it executable:
```bash
chmod +x publish.sh
```

---

## Troubleshooting

### Issue: "File already exists"

**Problem:** Trying to upload a version that already exists on PyPI.

**Solution:**
1. PyPI doesn't allow overwriting versions
2. Bump the version in `pyproject.toml`
3. Use a different pre-release version (e.g., `0.1.0b2`)
4. For fixes, use post-release versions (e.g., `0.1.0b1.post1`)

### Issue: "Invalid package metadata"

**Problem:** `twine check` fails.

**Solution:**
1. Verify `pyproject.toml` syntax
2. Check README.md has no syntax errors
3. Ensure all required fields are present
4. Run `python -m build` again

### Issue: "Authentication failed"

**Problem:** Can't authenticate with PyPI.

**Solution:**
1. Verify API token is correct in `~/.pypirc`
2. Check token hasn't expired
3. Ensure username is `__token__` (not your username)
4. Try recreating the API token

### Issue: "Package verification failed"

**Problem:** Package fails verification checks.

**Solution:**
1. Check all files in MANIFEST.in are present
2. Verify LICENSE file exists
3. Ensure README.md is valid Markdown
4. Run tests before building

---

## Post-Publication Checklist

After successful publication:

- [ ] ✅ Verify package appears on PyPI: https://pypi.org/project/django-iyzico/
- [ ] ✅ Test installation from PyPI works
- [ ] ✅ GitHub release created
- [ ] ✅ Git tag pushed
- [ ] ✅ Release notes published
- [ ] ✅ Announcement tweets posted
- [ ] ✅ Django community notified
- [ ] ✅ Update README badges (if needed)
- [ ] ✅ Monitor PyPI stats: https://pypistats.org/packages/django-iyzico
- [ ] ✅ Monitor GitHub issues for feedback

---

## Version Management

### For Next Beta Release (0.1.0b2)

1. Update version in `pyproject.toml`: `version = "0.1.0b2"`
2. Add changes to CHANGELOG.md under new version header
3. Follow publication process above

### For Release Candidate (0.1.0rc1)

1. Update version in `pyproject.toml`: `version = "0.1.0rc1"`
2. Update CHANGELOG.md
3. More extensive testing
4. Follow publication process above

### For Stable Release (0.1.0)

1. Update version in `pyproject.toml`: `version = "0.1.0"`
2. Update README badges
3. Create comprehensive release notes
4. Major announcement
5. Follow publication process above

---

## Quick Reference Commands

```bash
# Clean build
rm -rf build/ dist/ *.egg-info

# Build package
python -m build

# Verify package
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to production PyPI
twine upload dist/*

# Test install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ django-iyzico==0.1.0b1

# Test install from PyPI
pip install django-iyzico==0.1.0b1

# Create git tag
git tag -a v0.1.0-beta -m "Release v0.1.0-beta"
git push origin v0.1.0-beta
```

---

## Resources

- **PyPI:** https://pypi.org/
- **TestPyPI:** https://test.pypi.org/
- **Packaging Guide:** https://packaging.python.org/
- **Twine Documentation:** https://twine.readthedocs.io/
- **Semantic Versioning:** https://semver.org/
- **PEP 440 (Version Identifiers):** https://peps.python.org/pep-0440/

---

## Notes

### Version Naming Convention

We're using PEP 440 version identifiers:
- **Beta:** `0.1.0b1`, `0.1.0b2`, etc.
- **Release Candidate:** `0.1.0rc1`, `0.1.0rc2`, etc.
- **Stable:** `0.1.0`
- **Post-release:** `0.1.0.post1` (for fixes without code changes)
- **Dev releases:** `0.1.0.dev1` (for development versions)

### Security

- Never commit API tokens to version control
- Keep `~/.pypirc` with restricted permissions (600)
- Use different tokens for TestPyPI and production PyPI
- Consider using project-scoped tokens after first upload

---

**Document Version:** 1.0
**Last Updated:** 2025-12-17
**Package Version:** 0.1.0b1
**Status:** Ready for publication
