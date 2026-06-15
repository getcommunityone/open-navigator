---
sidebar_position: 10
---

# 🐛 Docker Build Troubleshooting Guide

## Testing Docker Build Locally

Before deploying to Hugging Face, always test the build locally:

```bash
# Run comprehensive build test
./test-huggingface-build.sh
```

This script will:
1. ✅ Build the Docker image
2. ✅ Check image size (HF has 50GB limit)
3. ✅ Start the container
4. ✅ Wait for services to be ready
5. ✅ Test all endpoints (/, /docs, /api/docs, /api/health)
6. ✅ Show container logs

## Common Build Failures

### 1. **Node.js Build Failures**

**Symptom:** `npm ci` or `npm install` fails during docs build

**Causes:**
- Network timeouts
- Package version conflicts
- Missing dependencies

**Solutions:**

```dockerfile
# Increase timeouts in Dockerfile.huggingface
RUN npm config set fetch-retry-mintimeout 20000 && \
    npm config set fetch-retry-maxtimeout 120000 && \
    npm ci --prefer-offline --no-audit || npm install --prefer-offline --no-audit
```

**Test locally:**
```bash
cd website
npm ci
npm run build
```

### 2. **Frontend Build Failures**

**Symptom:** `npm run build` fails in frontend directory

**Causes:**
- TypeScript errors
- Missing environment variables
- Vite configuration issues

**Solutions:**

Check build locally:
```bash
cd frontend
npm ci
npm run build
```

Fix TypeScript errors:
```bash
npm run typecheck
```

### 3. **Python Dependencies Fail**

**Symptom:** `pip install` fails

**Causes:**
- Missing system dependencies
- Incompatible versions
- Network issues

**Solutions:**

Test locally:
```bash
pip install -r requirements.txt
```

Check system dependencies in Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    # Add missing dependencies here
    && rm -rf /var/lib/apt/lists/*
```

### 4. **Image Size Too Large**

**Symptom:** Image exceeds 50GB limit on Hugging Face

**Solutions:**

Check image size:
```bash
docker images open-navigator-hf-test --format "{{.Size}}"
```

Reduce size:
- Remove unnecessary files in `.dockerignore`
- Use multi-stage builds
- Clean up apt cache: `rm -rf /var/lib/apt/lists/*`
- Remove dev dependencies after build

### 5. **Services Not Starting**

**Symptom:** Container starts but services don't respond

**Check logs:**
```bash
docker logs open-navigator-test-container
```

**Common issues:**
- Nginx configuration errors
- Port conflicts (7860)
- Missing environment variables
- Supervisor not starting services

**Test nginx config:**
```bash
docker exec open-navigator-test-container nginx -t
```

**Check supervisor status:**
```bash
docker exec open-navigator-test-container supervisorctl status
```

### 6. **File Copy Errors**

**Symptom:** `COPY` commands fail in Dockerfile

**Causes:**
- Files not in build context
- Incorrect paths
- .dockerignore excluding needed files

**Solutions:**

Check .dockerignore:
```bash
cat .dockerignore
```

Verify files exist:
```bash
ls -la .huggingface/
ls -la website/build/
```

### 7. **Static Files Not Found**

**Symptom:** Frontend or docs return 404

**Check build output:**
```bash
# Check if docs built
ls -la static/docs/

# Check if frontend built
ls -la api/static/
ls -la static/frontend/
```

**Fix frontend build path:**
```dockerfile
# Ensure vite.config.ts outputs to correct location
RUN cd /app/frontend && npm run build

# Verify output
RUN ls -la /app/api/static/

# Copy to nginx location
RUN cp -r /app/api/static/* /app/static/frontend/
```

## Debugging Steps

### 1. Build Image Locally

```bash
docker build -f Dockerfile.huggingface -t test-build . --progress=plain
```

The `--progress=plain` flag shows detailed output.

### 2. Run Container Interactively

```bash
docker run -it --rm \
  -p 7860:7860 \
  --entrypoint /bin/bash \
  test-build
```

Then manually run commands:
```bash
# Check files
ls -la /app/
ls -la /app/static/

# Test nginx config
nginx -t

# Start services manually
supervisord -c /etc/supervisor/conf.d/supervisord.conf
```

### 3. Test Individual Services

```bash
# Test API directly
python -m uvicorn api.app:app --host 0.0.0.0 --port 8001

# Test nginx config
nginx -t -c /etc/nginx/nginx.conf

# Test supervisor
supervisorctl status
```

### 4. Check Network Connectivity

```bash
# Inside container
curl http://localhost:7860/
curl http://localhost:7860/docs
curl http://localhost:7860/api/docs
curl http://localhost:7860/api/health
```

## Hugging Face Specific Issues

### 1. **Build Timeout**

HF has build time limits. Optimize:
- Use layer caching effectively
- Minimize npm install time with `npm ci --prefer-offline`
- Pre-download large files

### 2. **Environment Variables**

Set in HF Space Settings → Variables and secrets:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
HF_TOKEN=hf_...
LOG_LEVEL=INFO
HF_SPACES=1
```

### 3. **Hardware Requirements**

Docker Spaces require paid hardware:
- Settings → Resource configuration
- Select "CPU Basic" minimum (~$22/month)

### 4. **Port Configuration**

HF Spaces expect port 7860:
```dockerfile
EXPOSE 7860
```

```bash
# In nginx config
listen 7860;
```

## Quick Fixes

### Reset Everything

```bash
# Clean Docker
docker system prune -a
docker volume prune

# Rebuild from scratch
docker build --no-cache -f Dockerfile.huggingface -t test-build .
```

### Check Build Context Size

```bash
# See what's being sent to Docker
docker build -f Dockerfile.huggingface -t test-build . 2>&1 | grep "Sending build context"
```

### Update Dependencies

```bash
# Update npm packages
cd website && npm update && cd ..
cd frontend && npm update && cd ..

# Update Python packages
pip list --outdated
pip install -U package-name
```

## Getting Help

1. **Check HF Build Logs:**
   - Go to your Space
   - Click "Logs" tab
   - Look for error messages

2. **Test Locally First:**
   ```bash
   ./test-huggingface-build.sh
   ```

3. **Compare with Working Build:**
   - Check git history: `git log --oneline`
   - Compare Dockerfiles: `git diff HEAD~1 Dockerfile.huggingface`

4. **Report Issues:**
   - Include build logs
   - Include local test results
   - Include Docker version: `docker --version`

## Deployment Workflow

✅ **Recommended Process:**

```bash
# 1. Make changes
git add -A
git commit -m "Your changes"

# 2. Test build locally (THIS IS CRITICAL)
./test-huggingface-build.sh

# 3. If tests pass, deploy
./deploy-huggingface.sh

# 4. Monitor HF build logs
# Visit: https://huggingface.co/spaces/YOUR_USERNAME/open-navigator-for-engagement
```

⚠️ **Skip tests only if urgent:**

```bash
./deploy-huggingface.sh YOUR_USERNAME --skip-test
```

## Success Checklist

Before deploying to Hugging Face:

- [ ] Local build succeeds: `./test-huggingface-build.sh`
- [ ] All endpoints respond (/, /docs, /api/docs)
- [ ] No errors in container logs
- [ ] Image size < 50GB
- [ ] All environment variables configured
- [ ] HF Space hardware configured (CPU Basic minimum)
- [ ] Git changes committed

## Resources

- [Hugging Face Spaces Docker Guide](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [Supervisor Configuration](http://supervisord.org/configuration.html)

---

**Last Updated:** 2026-04-26
