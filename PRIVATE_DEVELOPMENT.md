# Private Development Guide - django-iyzico

**Repository:** https://github.com/aladagemre/django-iyzico
**Status:** Private (not published to PyPI yet)
**Version:** 0.1.0b1
**Date:** December 17, 2025

---

## ✅ Current Setup

Your django-iyzico package is now:
- ✅ Committed to git
- ✅ Tagged as v0.1.0-beta
- ✅ Pushed to private GitHub repository
- ✅ Ready for internal development and testing
- ✅ Not published to PyPI (private development)

---

## 🔗 Repository Information

**URL:** https://github.com/aladagemre/django-iyzico
**Visibility:** Private 🔒
**Branch:** main
**Remote:** origin (SSH)

---

## 👥 Sharing with Your Team

### Invite Collaborators

```bash
# Add team member
gh repo add-collaborator username

# Or via web:
open https://github.com/aladagemre/django-iyzico/settings/access
```

### Installation for Team Members

**Option 1: Install from GitHub (SSH)**
```bash
pip install git+ssh://git@github.com/aladagemre/django-iyzico.git@v0.1.0-beta
```

**Option 2: Install from GitHub (HTTPS with token)**
```bash
# Team member needs a GitHub personal access token
pip install git+https://TOKEN@github.com/aladagemre/django-iyzico.git@v0.1.0-beta
```

**Option 3: Clone and develop**
```bash
git clone git@github.com:aladagemre/django-iyzico.git
cd django-iyzico
pip install -e ".[dev]"
```

---

## 🧪 Testing in Your Projects

### In requirements.txt

```txt
# Install specific version from GitHub
git+ssh://git@github.com/aladagemre/django-iyzico.git@v0.1.0-beta
```

### In pyproject.toml

```toml
[project]
dependencies = [
    "django-iyzico @ git+ssh://git@github.com/aladagemre/django-iyzico.git@v0.1.0-beta",
]
```

### Direct Installation

```bash
# Install latest from main branch
pip install git+ssh://git@github.com/aladagemre/django-iyzico.git

# Install specific tag
pip install git+ssh://git@github.com/aladagemre/django-iyzico.git@v0.1.0-beta

# Install specific commit
pip install git+ssh://git@github.com/aladagemre/django-iyzico.git@9d7bc91
```

---

## 🔄 Development Workflow

### Making Changes

```bash
# 1. Create feature branch
git checkout -b feature/new-feature

# 2. Make changes
# Edit files...

# 3. Run tests
pytest

# 4. Commit changes
git add -A
git commit -m "feat: Add new feature"

# 5. Push to GitHub
git push origin feature/new-feature

# 6. Create pull request
gh pr create --title "Add new feature" --body "Description of changes"
```

### Creating New Versions

**For Bug Fixes (0.1.0b2):**
```bash
# 1. Update version in pyproject.toml
version = "0.1.0b2"

# 2. Update CHANGELOG.md
echo "## [0.1.0b2] - $(date +%Y-%m-%d)
### Fixed
- Bug fix description" >> CHANGELOG.md

# 3. Commit and tag
git add -A
git commit -m "fix: Bug fix description"
git tag -a v0.1.0b2 -m "Release v0.1.0b2 - Bug fixes"

# 4. Push
git push origin main --tags

# 5. Build new package (optional, if sharing .whl files)
python -m build
```

**For New Features (0.2.0):**
```bash
# 1. Update version
version = "0.2.0"

# 2. Update CHANGELOG.md with new features

# 3. Commit and tag
git add -A
git commit -m "feat: Add subscription support"
git tag -a v0.2.0 -m "Release v0.2.0 - Subscription support"

# 4. Push
git push origin main --tags
```

---

## 📦 Building and Sharing Packages

### Build Package Locally

```bash
# Clean previous builds
rm -rf build/ dist/ *.egg-info

# Build
python -m build

# Share .whl file with team
# dist/django_iyzico-0.1.0b1-py3-none-any.whl
```

### Installing from Local .whl

```bash
# Team members can install from file
pip install django_iyzico-0.1.0b1-py3-none-any.whl
```

---

## 🧪 Setting Up CI/CD

### Enable GitHub Actions

```bash
# Enable workflow
gh workflow enable tests.yml

# View workflow runs
gh run list

# Watch a specific run
gh run watch
```

### Add Secrets for CI/CD

```bash
# Add PyPI token (for future publication)
gh secret set PYPI_TOKEN --body "your-pypi-token"

# Add test PyPI token
gh secret set TEST_PYPI_TOKEN --body "your-test-pypi-token"
```

---

## 🔒 Security for Private Development

### Protect Main Branch

```bash
# Via web interface:
open https://github.com/aladagemre/django-iyzico/settings/branches

# Enable:
# - Require pull request reviews
# - Require status checks to pass
# - Require branches to be up to date
```

### Code Review Process

```bash
# Team member creates PR
gh pr create

# You review
gh pr view PR_NUMBER
gh pr review PR_NUMBER --approve

# Merge
gh pr merge PR_NUMBER --squash
```

---

## 📊 Monitoring Development

### View Repository Activity

```bash
# View commits
git log --oneline --graph --all

# View branches
git branch -a

# View tags
git tag -l

# View contributors
gh api repos/aladagemre/django-iyzico/contributors

# View recent activity
gh repo view
```

### Track Issues and Tasks

```bash
# Create issue
gh issue create --title "Bug: Payment processing fails" --body "Description"

# List issues
gh issue list

# View issue
gh issue view ISSUE_NUMBER

# Close issue
gh issue close ISSUE_NUMBER
```

---

## 🚀 Going Public Later

### When Ready to Publish to PyPI

1. **Test Thoroughly**
   ```bash
   pytest
   python -m build
   twine check dist/*
   ```

2. **Update Documentation**
   - Remove "PRIVATE" notices
   - Update README with PyPI badge
   - Finalize CHANGELOG

3. **Make Repository Public**
   ```bash
   gh repo edit aladagemre/django-iyzico --visibility public
   ```

4. **Publish to PyPI**
   ```bash
   # Test on TestPyPI first
   twine upload --repository testpypi dist/*

   # Then production
   twine upload dist/*
   ```

5. **Create GitHub Release**
   ```bash
   gh release create v0.1.0-beta \
     --title "v0.1.0-beta - First Beta Release" \
     --notes-file RELEASE_NOTES.md \
     --prerelease \
     dist/django_iyzico-0.1.0b1-py3-none-any.whl \
     dist/django_iyzico-0.1.0b1.tar.gz
   ```

6. **Announce**
   - Twitter/X
   - Reddit (r/django)
   - Django Forum
   - Django Discord

---

## 💡 Best Practices for Private Development

### Code Quality

1. **Always run tests before committing**
   ```bash
   pytest
   ```

2. **Keep test coverage high**
   ```bash
   pytest --cov=django_iyzico --cov-report=term-missing
   ```

3. **Lint code**
   ```bash
   black django_iyzico tests
   isort django_iyzico tests
   flake8 django_iyzico
   mypy django_iyzico
   ```

### Documentation

1. **Update README for new features**
2. **Document breaking changes in CHANGELOG**
3. **Add docstrings to new functions**
4. **Update type hints**

### Communication

1. **Use clear commit messages**
   - feat: New feature
   - fix: Bug fix
   - docs: Documentation changes
   - refactor: Code refactoring
   - test: Test changes

2. **Use pull requests for review**
3. **Comment on issues and PRs**
4. **Keep team informed of changes**

---

## 🔧 Useful Commands

### Git Operations

```bash
# Check status
git status

# View diff
git diff

# View log
git log --oneline -10

# Create branch
git checkout -b feature/name

# Switch branch
git checkout main

# Pull latest
git pull origin main

# Push changes
git push origin branch-name

# Delete branch
git branch -d feature/name
```

### GitHub CLI

```bash
# View repository
gh repo view -w

# List issues
gh issue list

# List PRs
gh pr list

# View PR
gh pr view PR_NUMBER

# Check workflow status
gh run list

# View secrets (names only)
gh secret list
```

### Package Management

```bash
# Install in development mode
pip install -e ".[dev]"

# Build package
python -m build

# Check package
twine check dist/*

# List installed version
pip show django-iyzico

# Uninstall
pip uninstall django-iyzico
```

---

## 📝 Internal Testing Checklist

Before sharing with team:

- [ ] All tests pass
- [ ] Test coverage > 90%
- [ ] Code is linted
- [ ] Documentation is updated
- [ ] CHANGELOG is updated
- [ ] Commit messages are clear
- [ ] Branch is pushed
- [ ] PR is created (if applicable)

Before making public:

- [ ] All features tested in real projects
- [ ] Security audit completed
- [ ] Documentation reviewed
- [ ] Examples tested
- [ ] Breaking changes documented
- [ ] Migration guide written (if needed)
- [ ] Version number finalized
- [ ] Repository made public
- [ ] PyPI publication complete

---

## 🎯 Next Steps for Your Team

### Week 1-2: Internal Testing

1. Install in test projects
2. Test all major features
3. Report bugs via GitHub issues
4. Fix critical issues

### Week 3-4: Refinement

1. Add requested features
2. Improve documentation
3. Add more examples
4. Polish API

### Month 2: Prepare for Public Release

1. Final testing
2. Security audit
3. Performance optimization
4. Documentation polish

### Month 3: Go Public

1. Make repository public
2. Publish to PyPI
3. Announce to community
4. Support early adopters

---

## 📞 Internal Support

**Repository:** https://github.com/aladagemre/django-iyzico
**Issues:** https://github.com/aladagemre/django-iyzico/issues (private)
**Discussions:** Use GitHub Discussions for questions
**Email:** aladagemre@gmail.com

---

## 🎉 Current Status Summary

**✅ What's Done:**
- Complete payment integration
- 95% test coverage
- PCI DSS compliant
- Professional documentation
- Private GitHub repository
- Ready for internal testing

**🔄 What's Next:**
- Internal team testing
- Bug fixes and refinements
- Additional features (subscription, installments)
- Public release when ready

---

**Happy developing! 🚀**

*Private development started: December 17, 2025*
*Repository: https://github.com/aladagemre/django-iyzico*
