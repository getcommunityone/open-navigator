---
sidebar_position: 4
---

# Hugging Face Spaces Deployment

Complete guide to deploy Open Navigator to Hugging Face Spaces with all three applications running together.

## 📋 What Gets Deployed

This deployment runs **all three apps** in a single Docker Space:

| Component | Access Path | Description |
|-----------|-------------|-------------|
| **Documentation** | `/docs` | Docusaurus documentation site |
| **Main App** | `/` | React frontend application |
| **API** | `/api` | FastAPI backend server |

All served through nginx reverse proxy on port 7860 (Hugging Face Spaces default).

## 🚀 Quick Start for Developers

**TL;DR** - Deploy in 3 commands:

```bash
# 1. Set your Hugging Face username in .env
echo "HF_USERNAME=your_username" >> .env

# 2. Run the deployment script (includes testing)
./deploy-huggingface.sh

# 3. Configure your Space
# - Go to https://huggingface.co/spaces/YOUR_USERNAME/www.communityone.com
# - Settings → Resource configuration → Select "CPU Basic"
# - Settings → Variables and secrets → Add your API keys
```

The script will:
1. ✅ Test Docusaurus build (catches config errors)
2. ✅ Test Docker build locally (validates deployment)
3. ✅ Create the Space on Hugging Face
4. ✅ Push your code
5. ✅ Trigger automatic build (~10-15 minutes)

**Note**: This project uses **Apache 2.0 license** (updated from MIT in April 2026).


## 💰 Cost Breakdown

### Required:
- **CPU Basic Hardware**: ~$0.03/hour = ~$22/month
  - 2 vCPU, 16 GB RAM
  - Required to run Docker Spaces

### Optional:
- **Pro Plan**: $9/month
  - Persistent storage (keeps data between restarts)
  - Better performance
  - Private Spaces option
  - Longer timeout limits

**Total Cost**: $22-31/month depending on plan

## 🛠️ Prerequisites

1. **Hugging Face Account**: Sign up at [huggingface.co](https://huggingface.co)
2. **Hugging Face Token**: Create at [Settings → Access Tokens](https://huggingface.co/settings/tokens)
   - Needs `write` permission
3. **API Keys**: Your OpenAI/Anthropic keys for LLM features
4. **Git**: Installed locally

## 📦 Step 1: Prepare Your Repository

The deployment files are already created:
```
.huggingface/
  ├── README.md              # Space description (shown on HF)
  ├── nginx.conf             # Reverse proxy config
  ├── supervisord.conf       # Process manager config
  └── start.sh               # Startup script
Dockerfile.huggingface       # Multi-stage Docker build
```

## 🚀 Step 2: Create the Hugging Face Space

### Option A: Using the Web UI

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Configure:
   - **Space name**: `open-navigator-for-engagement`
   - **License**: `Apache 2.0`
   - **Space SDK**: Select `Docker`
   - **Visibility**: Public or Private
3. Click **Create Space**

### Option B: Using the CLI

```bash
# Install huggingface-hub
pip install huggingface-hub

# Login with your token
huggingface-cli login

# Create the Space
huggingface-cli repo create open-navigator-for-engagement --type space --space-sdk docker
```

## 📤 Step 3: Deploy Your Code

### Option A: Automated Deployment (Recommended)

Use the deployment script for easy one-command deployment:

**Step 1: Set your username**

Add to your `.env` file:
```bash
echo "HF_USERNAME=your_hf_username" >> .env
```

Or export for current session:
```bash
export HF_USERNAME=getcommunityone  # Replace with your username
```

**Step 2: Run deployment script**
```bash
./deploy-huggingface.sh
```

The script automatically:
- Creates the Space on Hugging Face
- Sets up deployment branch
- Configures Dockerfile and README
- Pushes to Hugging Face

You can also pass username as argument: `./deploy-huggingface.sh YOUR_USERNAME`

### Option B: Manual Deployment

If you prefer manual control:

```bash
# Add Hugging Face as a remote
git remote add hf https://huggingface.co/spaces/YOUR_USERNAME/open-navigator-for-engagement

# Create a deployment branch with the right Dockerfile
git checkout -b huggingface-deploy

# Rename Dockerfile.huggingface to Dockerfile (HF looks for this)
cp Dockerfile.huggingface Dockerfile

# Copy the HF README to root (HF displays this)
cp .huggingface/README.md README_HF.md

# Commit changes
git add Dockerfile README_HF.md .huggingface/
git commit -m "Configure Hugging Face Space deployment"

# Push to Hugging Face
git push hf huggingface-deploy:main
```

## 🔧 Step 4: Configure Space Settings

1. Go to your Space: `https://huggingface.co/spaces/YOUR_USERNAME/open-navigator-for-engagement`
2. Click **Settings**
3. Under **Resource configuration**:
   - Select **CPU Basic** (minimum required)
   - Or **CPU Upgrade** for better performance
4. Under **Variables and secrets** (⚠️ IMPORTANT):
   - Add your API keys as secrets:
     ```
     OPENAI_API_KEY = sk-your-key-here
     ANTHROPIC_API_KEY = sk-ant-your-key-here
     HF_TOKEN = hf_your-token-here
     ```
   - Set environment variables:
     ```
     LOG_LEVEL = INFO
     PYTHONUNBUFFERED = 1
     ```
5. Click **Save**

## 🔄 Step 5: Wait for Build

The Space will automatically build when you push. This takes **10-15 minutes**:

1. Building documentation (Docusaurus)
2. Building frontend (React + Vite)
3. Installing Python dependencies
4. Configuring nginx reverse proxy
5. Starting services

Watch build progress in the **Logs** tab.

## ✅ Step 6: Verify Deployment

Once built, test each component:

### 1. Check Main App
```
https://YOUR_USERNAME-open-navigator-for-engagement.hf.space/
```
Should show the React dashboard.

### 2. Check Documentation
```
https://YOUR_USERNAME-open-navigator-for-engagement.hf.space/docs
```
Should show Docusaurus docs.

### 3. Check API
```
https://YOUR_USERNAME-open-navigator-for-engagement.hf.space/api/docs
```
Should show FastAPI Swagger docs.

### 4. Test API Endpoint
```bash
curl https://YOUR_USERNAME-open-navigator-for-engagement.hf.space/api/health
```
Should return: `{"status": "healthy"}`

## 🔄 Updating Your Space

When you make changes to your code:

```bash
# Make your changes in your main branch
git checkout main
# ... make edits ...
git commit -am "Update feature X"

# Merge to deployment branch
git checkout huggingface-deploy
git merge main

# Update Dockerfile if needed
cp Dockerfile.huggingface Dockerfile
git add Dockerfile
git commit -m "Update deployment"

# Push to Hugging Face
git push hf huggingface-deploy:main
```

The Space will automatically rebuild.

## 🐛 Troubleshooting

### Build Fails

**Check logs**: Click **Logs** tab in your Space

**Common issues**:
- Missing dependencies → Check `requirements.txt`
- Node.js build errors → Check `package.json` versions
- Out of memory → Upgrade to larger hardware

### App Doesn't Start

1. Check environment variables are set
2. Verify API keys are correct
3. Check logs for Python errors
4. Ensure port 7860 is exposed

### 404 Errors

- `/` works but `/docs` doesn't → Check nginx.conf routing
- `/api` returns 404 → Check FastAPI is running on port 8000
- Static files not loading → Check build output directories

### Performance Issues

- **Slow response**: Upgrade to CPU Upgrade or GPU
- **Timeouts**: Enable Pro plan for longer limits
- **Out of memory**: Reduce concurrent workers or upgrade hardware

## 📊 Monitoring

### View Logs
```
Settings → Logs → Container logs
```

### Check Resource Usage
```
Settings → Resource configuration → Usage metrics
```

### Monitor API Calls
FastAPI automatically logs requests to `/var/log/supervisor/api.log`

## 🔒 Security Best Practices

### Secrets Management
✅ DO:
- Add API keys in Space Settings → Variables and secrets
- Use `Secrets` (encrypted), not `Variables` for sensitive data
- Set secrets as "Private" in settings

❌ DON'T:
- Commit `.env` files with real keys
- Hardcode secrets in code
- Share your Space's API keys

### Access Control
- Set Space to **Private** if using sensitive data
- Use Hugging Face OAuth for user authentication
- Enable rate limiting in FastAPI

## 💡 Optimization Tips

### Reduce Build Time
1. Use smaller Docker base images
2. Cache npm dependencies
3. Use multi-stage builds (already configured)

### Improve Performance
1. Enable gzip compression (already configured in nginx)
2. Set cache headers for static assets (already configured)
3. Use CDN for large static files

### Save Costs
1. Use **CPU Basic** instead of GPU (unless you need it)
2. Set **Sleep timeout** for inactive Spaces
3. Use **Persistent storage** only if needed (requires Pro)

## 🎯 Advanced: Custom Domain

Hugging Face Spaces supports custom domains:

1. Go to Space Settings
2. Under **Custom domain**
3. Add your domain (e.g., `opennavigator.org`)
4. Configure DNS:
   ```
   CNAME record: opennavigator.org → YOUR_USERNAME-open-navigator-for-engagement.hf.space
   ```

## 📚 Additional Resources

- [Hugging Face Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [Docker Spaces Guide](https://huggingface.co/docs/hub/spaces-sdks-docker)
- [Space Configuration](https://huggingface.co/docs/hub/spaces-config-reference)

## 🆘 Getting Help

- **Hugging Face Discord**: [hf.co/join/discord](https://hf.co/join/discord)
- **GitHub Issues**: [Your repo issues](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
- **Space Discussions**: Comment on your Space page

---

## 🎉 Next Steps

After deployment:
1. ✅ Test all three apps thoroughly
2. ✅ Share your Space URL with users
3. ✅ Monitor usage and costs
4. ✅ Set up persistent storage if needed (Pro plan)
5. ✅ Configure custom domain (optional)

**Your Space URL**:
```
https://huggingface.co/spaces/YOUR_USERNAME/open-navigator-for-engagement
```

Enjoy your fully deployed civic engagement platform! 🚀
