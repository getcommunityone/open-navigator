---
sidebar_position: 11
---

# Build Protection & CI/CD

Comprehensive guide to the **multi-layered build protection system** that prevents broken deployments.

## 🛡️ Protection Layers

We have **4 layers of protection** to catch build errors before they reach production:

```mermaid
graph LR
    A[Local Pre-Push Hook] --> B[GitHub CI Tests]
    B --> C[Docker Build Test]
    C --> D[HuggingFace Deployment]
    
    style A fill:#52796F
    style B fill:#84A98C
    style C fill:#CAD2C5
    style D fill:#354F52
```

### Layer 1: Pre-Push Hook (Local)

**Runs before every `git push`** on your local machine.

**Checks:**
- ✅ Frontend TypeScript compilation
- ✅ Python syntax validation
- ✅ Frontend build succeeds

**Setup:**
```bash
# One-time setup (run once after cloning)
./setup-git-hooks.sh
```

**Bypass (emergency only):**
```bash
git push --no-verify
```

### Layer 2: GitHub Actions CI (Automatic)

**Runs automatically on every push and pull request** to `main` or `develop`.

**Workflow:** [`.github/workflows/ci-build-test.yml`](.github/workflows/ci-build-test.yml)

**Tests:**
1. **Frontend Build**
   - TypeScript type checking
   - Vite production build
   - Artifact verification

2. **Documentation Build**
   - Docusaurus build
   - Mermaid diagram rendering
   - Static site generation

3. **Backend Tests**
   - Python syntax checking
   - Module import validation
   - API app initialization

4. **Docker Build**
   - Full multi-stage Docker build
   - All three services (Docs + App + API)
   - Uses build cache for speed

**View Results:**
- Go to the [Actions tab](https://github.com/getcommunityone/open-navigator-for-engagement/actions)
- Each push shows ✅ or ❌ for all tests

### Layer 3: Local Docker Test (Manual)

**Run before deploying** to test the exact Docker build that will run on HuggingFace.

```bash
# Test Docker build locally
./test-huggingface-build.sh

# Keep container running for debugging
./test-huggingface-build.sh --keep
```

**What it tests:**
- 📦 Full Docker image build (8GB+)
- 🌐 All three services start correctly
- 🔗 HTTP endpoints return 200 OK
- ⏱️ Services respond within timeout

**Automatic in deployment:**
The `deploy-huggingface.sh` script **automatically runs this test** before deploying (unless you use `--skip-test`).

### Layer 4: HuggingFace Deployment

**Only runs if all other layers pass.**

**Deployment methods:**
1. **Manual (local):**
   ```bash
   export HF_USERNAME=CommunityOne
   ./deploy-huggingface.sh
   ```

2. **GitHub Actions (automatic):**
   - Push to `deploy` branch, or
   - Manually trigger via [Actions tab](https://github.com/getcommunityone/open-navigator-for-engagement/actions/workflows/deploy-huggingface.yml)

## 🚨 Common Build Errors

### TypeScript Error

**Error:**
```
error TS2322: Type 'X' is not assignable to type 'Y'
```

**Fix:**
1. Check the file mentioned in error
2. Run `cd frontend && npx tsc --noEmit` to see full errors
3. Fix type mismatches
4. Test with `npm run build`

**Prevention:**
- Pre-push hook catches these locally
- GitHub CI catches them before merge

### Docker Build Failure

**Error:**
```
ERROR: process "/bin/sh -c ..." did not complete successfully
```

**Fix:**
1. Run `./test-huggingface-build.sh --keep` locally
2. Inspect container: `docker logs hf-test-open-navigator`
3. Fix the failing build step
4. Clean rebuild: `docker system prune -a` then retry

**Common causes:**
- Missing dependencies in `requirements.txt` or `package.json`
- Build-time environment variable issues
- File path errors

### Stale Deployment Branch

**Error:**
```
Deployment uses old code even though main branch is updated
```

**Fix:**
The deploy script now **automatically syncs** with main:
```bash
git checkout main
git branch -D huggingface-deploy  # Delete old
git checkout -b huggingface-deploy  # Fresh from main
```

No manual intervention needed!

## 📊 Monitoring Deployments

### GitHub Actions Dashboard

1. Go to [Actions tab](https://github.com/getcommunityone/open-navigator-for-engagement/actions)
2. View all CI/CD runs
3. Click any run to see detailed logs
4. Red ❌ = failed, Green ✅ = passed

### HuggingFace Space Logs

1. Visit your Space: https://huggingface.co/spaces/CommunityOne/open-navigator-for-engagement
2. Click **"Logs"** tab
3. Watch build progress in real-time (~10-15 minutes)
4. Green "Running" = successful deployment

### Local Test Logs

```bash
# Run test and save output
./test-huggingface-build.sh 2>&1 | tee build-test.log

# Check specific errors
grep -i error build-test.log
```

## 🔄 CI/CD Workflow Example

**Typical development flow with protection:**

```bash
# 1. Make changes
vim frontend/src/pages/Explore.tsx

# 2. Test locally
cd frontend && npm run build

# 3. Commit changes
git add .
git commit -m "feat: Add new explore feature"

# 4. Push to GitHub
git push origin main
# → Pre-push hook runs TypeScript check ✅
# → GitHub Actions CI runs full test suite ✅

# 5. Deploy to HuggingFace
export HF_USERNAME=CommunityOne
./deploy-huggingface.sh
# → Docker build test runs automatically ✅
# → Deployment proceeds only if test passes ✅
```

## ⚙️ Configuration Files

| File | Purpose |
|------|---------|
| [`.github/workflows/ci-build-test.yml`](.github/workflows/ci-build-test.yml) | Main CI test suite |
| [`.github/workflows/deploy-huggingface.yml`](.github/workflows/deploy-huggingface.yml) | Deployment workflow |
| [`.githooks/pre-push`](.githooks/pre-push) | Local pre-push validation |
| [`test-huggingface-build.sh`](test-huggingface-build.sh) | Docker build test script |
| [`deploy-huggingface.sh`](deploy-huggingface.sh) | Deployment script with tests |

## 🆘 Troubleshooting

### "Pre-push hook failed"

**Solution:**
```bash
# See what failed
git push

# Fix the errors shown
cd frontend && npx tsc --noEmit

# Try again
git push

# Emergency bypass (fix later!)
git push --no-verify
```

### "GitHub Actions failing but local works"

**Causes:**
- Missing files in git (not committed)
- Environment differences
- Cache issues

**Solution:**
```bash
# Ensure all files committed
git status

# Clear GitHub Actions cache
# Go to Actions tab → Caches → Delete old caches
```

### "Docker test passes but HuggingFace fails"

**Causes:**
- HuggingFace-specific environment differences
- Secrets/tokens not configured
- Space hardware limits

**Solution:**
1. Check HuggingFace Space logs
2. Verify secrets in HuggingFace Space settings
3. Check Space hardware configuration (CPU vs GPU)

## 📚 Best Practices

### ✅ DO

- ✅ Run `./setup-git-hooks.sh` once after cloning
- ✅ Let CI tests complete before merging PRs
- ✅ Test deployments with `./test-huggingface-build.sh` first
- ✅ Check GitHub Actions status before deploying
- ✅ Monitor HuggingFace logs during deployment

### ❌ DON'T

- ❌ Use `git push --no-verify` habitually
- ❌ Use `--skip-test` flag on deployments
- ❌ Ignore GitHub Actions failures
- ❌ Deploy without testing locally first
- ❌ Push to `deploy` branch directly (use main → deploy workflow)

## 🎯 Quick Reference

**Test build locally:**
```bash
./test-huggingface-build.sh
```

**Deploy with full protection:**
```bash
export HF_USERNAME=CommunityOne
./deploy-huggingface.sh
# Automatically runs tests before deploying
```

**Emergency deploy (skip tests):**
```bash
./deploy-huggingface.sh --skip-test
# ⚠️ NOT RECOMMENDED - can break production
```

**View CI status:**
```bash
# Web: https://github.com/getcommunityone/open-navigator-for-engagement/actions

# CLI (with GitHub CLI):
gh run list --workflow=ci-build-test.yml
```

**Install pre-push hook:**
```bash
./setup-git-hooks.sh
```

---

## 🚀 Next Steps

- Read the [Docker Build Troubleshooting Guide](docker-troubleshooting.md)
- Learn about [HuggingFace Deployment](huggingface-spaces.md)
- Understand [Variable Migration](variable-migration.md)
