---
sidebar_position: 5
---

# OAuth Providers Setup

Complete guide to configuring OAuth authentication with Google, Facebook, GitHub, and HuggingFace for Open Navigator.

## Overview

This application supports four OAuth providers for user authentication:
- 🔵 **Google** - Google Account authentication
- 🔵 **Facebook** - Facebook Login
- ⚫ **GitHub** - GitHub OAuth Apps
- 🤗 **HuggingFace** - HuggingFace OAuth

:::info
Each provider requires creating an OAuth application and configuring redirect URIs. **Never commit secrets to git!**
:::

---

## 🌐 Required Redirect URIs

For **all providers**, you need to configure these redirect URIs:

### Local Development
```
http://localhost:8000/auth/callback/{provider}
```

### Production (HTTPS required)
```
https://www.communityone.com/auth/callback/{provider}
https://your-space-name.hf.space/auth/callback/{provider}
```

Replace `{provider}` with: `google`, `facebook`, `github`, or `huggingface`

---

## 🔵 Google OAuth Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "NEW PROJECT"
3. Enter project name: `open-navigator-for-engagement`
4. Click "CREATE"

### Step 2: Enable Google Identity Toolkit API

1. Navigate to **APIs & Services → Library**
2. Search for: `Google Identity Toolkit API`
3. Click "ENABLE"

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Select **"External"** user type → Click "CREATE"
3. Fill in app information:
   - **App name:** `Open Navigator`
   - **User support email:** Your email
   - **App domain:** `www.communityone.com`
   - **Developer contact:** Your email
4. Click "SAVE AND CONTINUE"

5. **Scopes page:**
   - Click "ADD OR REMOVE SCOPES"
   - Select: `userinfo.email`, `userinfo.profile`, `openid`
   - Click "UPDATE" → "SAVE AND CONTINUE"

6. **Test users** (optional for development):
   - Add your Google account email
   - Click "SAVE AND CONTINUE"

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **"+ CREATE CREDENTIALS" → "OAuth client ID"**
3. Configure:
   - **Application type:** Web application
   - **Name:** `Open Navigator Web App`

4. **Authorized JavaScript origins:**
   ```
   http://localhost:5173
   http://localhost:8000
   https://www.communityone.com
   https://your-space.hf.space
   ```

5. **Authorized redirect URIs:**
   ```
   http://localhost:8000/api/auth/callback/google
   https://www.communityone.com/api/auth/callback/google
   https://your-space.hf.space/api/auth/callback/google
   ```

6. Click **"CREATE"**

7. **Copy your credentials** (you'll need these for environment variables):
   - Client ID: `[long string].apps.googleusercontent.com`
   - Client Secret: `GOCSPX-[random string]`

### Step 5: Add to Environment Variables

**Local (`.env`):**
```bash
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-secret-here
```

**HuggingFace Spaces:**
- Go to Space Settings → Variables and secrets
- Add as Repository secrets (not variables)

---

## 🔵 Facebook OAuth Setup

### Step 1: Create Facebook App

1. Go to [Facebook Developers](https://developers.facebook.com/apps/)
2. Click **"Create App"**
3. Choose **"Other"** → **"Next"** → **"Consumer"** → **"Next"**
4. Enter details:
   - **App name:** `Open Navigator`
   - **Contact email:** Your email
5. Click **"Create App"**

### Step 2: Add Facebook Login Product

1. In app dashboard, find **"Add Products"**
2. Find **"Facebook Login"** → Click **"Set Up"**
3. Choose **"Web"** platform
4. Enter site URL: `http://localhost:5173`
5. Click "Save" → "Continue"

### Step 3: Configure OAuth Settings

1. **Left sidebar:** Click **"Use cases → Authentication and account creation → Customize"**

   OR: **"Facebook Login → Settings"**

2. **Valid OAuth Redirect URIs** (one per line):
   ```
   http://localhost:8000/api/auth/callback/facebook
   https://www.communityone.com/api/auth/callback/facebook
   https://your-space.hf.space/api/auth/callback/facebook
   ```

3. **Enable these settings:**
   - ✅ Client OAuth Login: ON
   - ✅ Web OAuth Login: ON
   - ❌ Native or desktop app: OFF

4. Click **"Save Changes"**

### Step 4: Configure App Settings

1. **Left sidebar:** Click **"App settings → Basic"**

2. **App Domains:**
   ```
   localhost
   www.communityone.com
   your-space.hf.space
   ```

3. **Privacy Policy URL:**
   ```
   https://www.communityone.com/privacyfacebook.html
   ```

4. Click **"Save Changes"**

### Step 5: Get App Credentials

1. Still in **"App settings → Basic"**
2. Copy your credentials:
   - **App ID:** 15-digit number
   - **App Secret:** Click "Show" → 32-character string

### Step 6: Add to Environment Variables

**Local (`.env`):**
```bash
FACEBOOK_APP_ID=your-app-id-here
FACEBOOK_APP_SECRET=your-app-secret-here
```

**HuggingFace Spaces:**
- Add as Repository secrets

### Step 7: App Mode

**Development Mode** (default):
- Only you can log in
- Good for testing

**Live Mode** (for production):
- Requires App Review
- Toggle in "App settings → Basic"

---

## ⚫ GitHub OAuth Setup

### Step 1: Create OAuth App

1. Go to [GitHub Settings → Developer settings](https://github.com/settings/developers)
2. Click **"OAuth Apps"** → **"New OAuth App"**

### Step 2: Configure Application

1. Fill in details:
   - **Application name:** `Open Navigator`
   - **Homepage URL:** `https://www.communityone.com`
   - **Authorization callback URL:** `http://localhost:8000/api/auth/callback/github`

2. Click **"Register application"**

### Step 3: Add Additional Callback URLs

GitHub only allows ONE callback URL per OAuth app. For multiple environments:

**Option 1:** Create separate apps for each environment
- Local Dev app → `http://localhost:8000/api/auth/callback/github`
- Production app → `https://www.communityone.com/api/auth/callback/github`

**Option 2:** Use production URL only
- Set: `https://www.communityone.com/api/auth/callback/github`
- For local dev, temporarily change to localhost during testing

### Step 4: Get Credentials

1. On the OAuth app page:
   - **Client ID:** 20-character string
   - **Client secrets:** Click "Generate a new client secret"

2. Copy both values immediately (secret won't be shown again)

### Step 5: Add to Environment Variables

**Local (`.env`):**
```bash
GITHUB_CLIENT_ID=your-client-id-here
GITHUB_CLIENT_SECRET=your-client-secret-here
```

**HuggingFace Spaces:**
- Add as Repository secrets

---

## 🤗 HuggingFace OAuth Setup

### Step 1: Create OAuth Application

1. Go to [HuggingFace Settings → Applications](https://huggingface.co/settings/applications)
2. Click **"Create a new application"**

### Step 2: Configure Application

1. Fill in details:
   - **Application name:** `Open Navigator`
   - **Homepage URL:** `https://www.communityone.com`
   - **Scopes:** `openid profile email`

2. **Redirect URIs** (add all):
   ```
   http://localhost:8000/api/auth/callback/huggingface
   https://www.communityone.com/api/auth/callback/huggingface
   https://your-space.hf.space/api/auth/callback/huggingface
   ```

3. Click **"Create application"**

### Step 3: Get Credentials

1. On the application page:
   - **Client ID:** UUID format (8-4-4-4-12 characters)
   - **Client Secret:** Long random string starting with `oauth_app_secret_`

2. Copy both values

### Step 4: Add to Environment Variables

**Local (`.env`):**
```bash
HUGGINGFACE_CLIENT_ID=your-client-id-here
HUGGINGFACE_CLIENT_SECRET=oauth_app_secret_your-secret-here
```

**HuggingFace Spaces:**
- Add as Repository secrets

---

## 🔒 Environment Variables Reference

### Local Development (`.env`)

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=sqlite:///./data/users.db

# JWT Secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-random-32-byte-hex-string

# Application URLs
FRONTEND_URL=http://localhost:5173
API_BASE_URL=http://localhost:8000

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Facebook OAuth
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=

# GitHub OAuth
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# HuggingFace OAuth
HUGGINGFACE_CLIENT_ID=
HUGGINGFACE_CLIENT_SECRET=
```

:::warning
Never commit `.env` to git! It's already in `.gitignore`.
:::

### Production (HuggingFace Spaces)

Add these as **Repository secrets** in Space Settings → Variables and secrets:

```bash
# CRITICAL: Use HTTPS for production URLs
API_BASE_URL=https://www.communityone.com
FRONTEND_URL=https://www.communityone.com

# Database
DATABASE_URL=sqlite:///./data/users.db

# JWT Secret (same as local for consistency, or generate new)
JWT_SECRET_KEY=your-random-32-byte-hex-string

# OAuth Credentials (same as local)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
HUGGINGFACE_CLIENT_ID=...
HUGGINGFACE_CLIENT_SECRET=...
```

:::danger
Production URLs **MUST** use `https://` - OAuth providers reject `http://` for security.
:::

---

## 🧪 Testing OAuth Configuration

### Local Testing

1. **Start all services:**
   ```bash
   ./start-all.sh
   ```

2. **Open application:** http://localhost:5173

3. **Test each provider:**
   - Click "Login" → Select provider
   - Authorize the app
   - Should redirect back with your profile

4. **Check for errors in:**
   - Browser console (F12)
   - API server logs
   - Network tab (watch redirect flow)

### Production Testing

1. **Deploy to HuggingFace Spaces** (see [HuggingFace Deployment Guide](./huggingface-spaces.md))

2. **Add all environment secrets** in Space settings

3. **Test each provider** at https://www.communityone.com

4. **Common issues:**
   - ❌ 400 Bad Request → Redirect URI not registered
   - ❌ redirect_uri_mismatch → Using `http://` instead of `https://`
   - ❌ 401 Unauthorized → Wrong client secret or missing env vars

---

## 🔧 Troubleshooting

### "Redirect URI Mismatch"

**Cause:** OAuth provider doesn't recognize the callback URL

**Fix:**
1. Check exact URL in error message
2. Add that exact URL to provider settings
3. Ensure `http://` vs `https://` matches
4. No trailing slashes

### "Invalid Client"

**Cause:** Wrong client ID or secret

**Fix:**
1. Verify credentials copied correctly
2. Check for extra spaces
3. Ensure environment variables are loaded
4. Restart server after changing `.env`

### "Access Blocked"

**Cause:** App not verified or in development mode

**Fix:**
- **Google:** Add yourself as test user in OAuth consent screen
- **Facebook:** Use Development Mode for testing
- **GitHub:** No verification needed
- **HuggingFace:** No verification needed

### Production HTTPS Issues

**Cause:** Using `http://` URLs in production

**Fix:**
```bash
# In HuggingFace Spaces secrets, use HTTPS:
API_BASE_URL=https://www.communityone.com  # ✅ Correct
API_BASE_URL=http://www.communityone.com   # ❌ Wrong
```

---

## 📚 Related Documentation

- [Authentication Setup](./authentication-setup.md) - Database and JWT configuration
- [HuggingFace Deployment](./huggingface-spaces.md) - Deploy to production
- [Environment Configuration](../guides/environment-setup.md) - Full environment setup

---

## 🔐 Security Best Practices

1. **Never commit secrets** - Use `.env` files (gitignored)
2. **Use HTTPS in production** - Required by OAuth providers
3. **Rotate secrets regularly** - Generate new secrets periodically
4. **Limit OAuth scopes** - Only request necessary permissions
5. **Use separate apps** - Different OAuth apps for dev/staging/prod
6. **Monitor usage** - Check OAuth app dashboards for suspicious activity

---

## 📝 Quick Reference

| Provider | Setup URL | Redirect URI Format |
|----------|-----------|---------------------|
| Google | [console.cloud.google.com](https://console.cloud.google.com/apis/credentials) | `/api/auth/callback/google` |
| Facebook | [developers.facebook.com](https://developers.facebook.com/apps/) | `/api/auth/callback/facebook` |
| GitHub | [github.com/settings/developers](https://github.com/settings/developers) | `/api/auth/callback/github` |
| HuggingFace | [huggingface.co/settings/applications](https://huggingface.co/settings/applications) | `/api/auth/callback/huggingface` |

---

:::tip
Start with one provider (e.g., Google) to verify the flow works, then add others incrementally.
:::
