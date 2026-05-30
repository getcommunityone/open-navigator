---
sidebar_position: 8
---

# Build Verification & CI/CD

This guide explains how we prevent failed HuggingFace deployments through automated build verification.

## 🚨 The Problem We Solved

**April 2026:** A duplicate `gtag` configuration caused a HuggingFace deployment to fail after a 15-minute build process. The error only appeared during the Docker build on HuggingFace's servers, making it slow and expensive to discover.

**Root Cause:** Configuration errors in `docusaurus.config.ts` that weren't caught before deployment.

## ✅ The Solution

We implemented **two layers of protection**:

### 1. Pre-Deployment Build Verification

The [deploy-huggingface.sh](/home/developer/projects/open-navigator/deploy-huggingface.sh) script now tests builds BEFORE pushing to HuggingFace:

```bash
./deploy-huggingface.sh
```

**What it does:**
1. ✅ **Docusaurus build test** (fast, ~30 seconds)
   - Catches config errors like duplicate gtag
   - Validates all markdown files and links
   - Tests before the slow Docker build

2. ✅ **Docker build test** (slow, ~5-10 minutes)
   - Full deployment simulation
   - Tests all three apps: docs, frontend, API
   - Validates the complete build process

3. ✅ **Clear error messages**
   - Explains common issues
   - Suggests fixes
   - Prevents deployment if tests fail

### 2. GitHub Actions CI/CD

The [.github/workflows/ci-build-test.yml](/home/developer/projects/open-navigator/.github/workflows/ci-build-test.yml) workflow automatically tests:

- ✅ Frontend TypeScript build
- ✅ **Docusaurus documentation build** ← catches config errors
- ✅ Backend Python tests

**Runs automatically on:**
- Every push to `main`
- Every push to `huggingface-deploy`
- Every pull request to `main`

## 🛡️ What This Prevents

### Before (Manual Deployment)
```bash
git push hf-www huggingface-deploy:main
# Wait 15 minutes...
# ❌ Build fails on HuggingFace
# Must fix, commit, push again
# Wait another 15 minutes...
```

### After (Automated Verification)
```bash
./deploy-huggingface.sh
# Docusaurus build test (30s)
# ❌ FAIL: Duplicate gtag config detected
# Fix locally, test again
# ✅ Docusaurus build succeeds
# ✅ Docker build succeeds
# ✅ Deploy to HuggingFace (confident it will work)
```

## 🔧 Common Build Errors Caught

### Duplicate gtag Configuration
**Error:** `"gtag" field in themeConfig should now be specified as option for plugin-google-gtag`

**Fix:** Remove gtag from `themeConfig`, keep only in preset options:

```typescript
// ✅ CORRECT
presets: [
  ['classic', {
    gtag: {
      trackingID: 'G-5EQV815915',
      anonymizeIP: true,
    }
  }]
],
themeConfig: {
  // ❌ Do NOT put gtag here
}
```

### Missing export statement
**Error:** `ParseError: Unexpected token`

**Fix:** Ensure config file ends properly:

```typescript
export default config;
```

### Broken markdown links
**Warning:** `Markdown link with URL "..." couldn't be resolved`

**Fix:** Use paths relative to docs directory or full URLs

## 📊 Workflow Diagram

```
Developer makes changes
    ↓
git push origin main
    ↓
GitHub Actions runs tests ← Catches errors automatically
    ├─ Frontend build
    ├─ Docs build ← Your gtag error caught here!
    └─ Backend tests
    ↓
If tests pass:
    ↓
./deploy-huggingface.sh
    ├─ Docusaurus test (30s)
    ├─ Docker test (5-10min)
    └─ Push to HuggingFace
    ↓
✅ Deployment succeeds!
```

## 🚀 Usage

### Deploy with all verification (recommended)
```bash
./deploy-huggingface.sh
```

### Skip tests (NOT recommended)
```bash
./deploy-huggingface.sh --skip-test
```

### Test builds locally without deploying
```bash
# Test Docusaurus only
cd website && npm run build

# Test full Docker build
./test-huggingface-build.sh

# Test and keep container running
./test-huggingface-build.sh --keep
```

## 💡 Best Practices

1. **Always test locally** before deploying:
   ```bash
   cd website && npm run build
   ```

2. **Watch CI/CD results** on GitHub:
   - Check Actions tab after pushing
   - Don't deploy if tests fail

3. **Use the deploy script**, don't push manually:
   ```bash
   # ✅ Good
   ./deploy-huggingface.sh
   
   # ❌ Bad (skips verification)
   git push hf-www huggingface-deploy:main
   ```

4. **Review warnings** even if build succeeds:
   - Broken links
   - Missing dependencies
   - Version mismatches

## 🔍 Troubleshooting

### Build fails with "npm WARN EBADENGINE"
**Issue:** HuggingFace uses Node 20, but package wants Node 22

**Fix:** Usually safe to ignore warnings, but check if it causes runtime errors

### Docker build test fails locally
**Issue:** Not enough disk space or memory

**Fix:**
```bash
# Clean up Docker
docker system prune -a -f

# Check disk space
df -h

# Check Docker settings in Docker Desktop (increase resources)
```

### CI tests pass but local build fails
**Issue:** Different Node/npm versions

**Fix:**
```bash
# Check versions match CI
node -v  # Should be 20.x
npm -v   # Should be 10.x

# Use nvm to switch versions
nvm use 20
```

## 📚 Related Documentation

- [HuggingFace Spaces Deployment](huggingface-spaces.md)
- [Docker Troubleshooting](docker-troubleshooting.md)
- [Development Workflow](../development/workflow.md)

## 🎯 Summary

This two-layer verification system prevents expensive deployment failures:

1. **GitHub Actions** - Automatic testing on every push
2. **deploy-huggingface.sh** - Pre-deployment verification

**Result:** Catch errors in 30 seconds locally instead of waiting 15 minutes for HuggingFace build to fail.
