---
sidebar_position: 6
---

# Authentication Setup Guide

Complete guide for setting up OAuth authentication with HuggingFace, Google, Facebook, and GitHub, plus Neon serverless PostgreSQL.

## 🥇 Database Setup: Neon (Serverless PostgreSQL)

**Recommended Choice** - Free tier, zero-config, perfect for production.

### Why Neon?

✅ **Free tier**: 0.5 GB storage with scale-to-zero  
✅ **Managed backups**: Point-in-time recovery included  
✅ **Encrypted**: At rest + in transit  
✅ **Public internet**: Perfect for HuggingFace Spaces  
✅ **Standard PostgreSQL**: No vendor lock-in  
✅ **Enterprise backing**: Acquired by Databricks (2025)

### Setup Steps

1. **Sign up at [neon.tech](https://neon.tech)**
   - Click "Sign up" (free, no credit card required)
   - Sign in with GitHub or email

2. **Create a new project**
   - Click "New Project"
   - Name: `open-navigator-engagement`
   - Region: Choose closest to your users (e.g., `US East`)
   - PostgreSQL version: 16 (latest)

3. **Copy connection string**
   - Go to Dashboard → Connection Details
   - Copy the **"Connection string"** 
   - Format: `postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require`

4. **Add to `.env` file**
   ```bash
   DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

5. **Database auto-initialization**
   - Tables are created automatically on first API startup
   - No migration scripts needed!

### Verify Connection

```bash
# Start the API server
source .venv/bin/activate
python main.py serve

# You should see:
# ✅ Database initialized at: postgresql://...
```

---

## 🔐 OAuth Provider Setup

### 1. HuggingFace OAuth

**Get credentials:** [huggingface.co/settings/applications](https://huggingface.co/settings/applications)

#### Steps:

1. Go to HuggingFace Settings → Applications
2. Click **"Create an OAuth app"**
3. Fill in:
   - **Application name**: `Open Navigator`
   - **Homepage URL**: `https://www.communityone.com`
   - **Redirect URI**: 
     - Development: `http://localhost:8000/auth/callback/huggingface`
     - Production: `https://www.communityone.com/api/auth/callback/huggingface`
   - **Scopes**: `openid profile email`
4. Click **"Create"**
5. Copy **Client ID** and **Client Secret**

#### Add to `.env`:

```bash
HUGGINGFACE_CLIENT_ID=hf_oauth_xxx
HUGGINGFACE_CLIENT_SECRET=hf_oauth_secret_xxx
```

---

### 2. Google OAuth

**Get credentials:** [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)

#### Steps:

1. **Create a project** (or select existing)
   - Go to Google Cloud Console
   - Select project or click "New Project"
   - Name: `Open Navigator`

2. **Enable Google+ API**
   - Go to APIs & Services → Library
   - Search "Google+ API"
   - Click Enable

3. **Configure OAuth consent screen**
   - Go to APIs & Services → OAuth consent screen
   - User Type: **External**
   - App name: `Open Navigator`
   - User support email: Your email
   - Developer contact: Your email
   - Scopes: `email`, `profile`, `openid`

4. **Create OAuth 2.0 Client ID**
   - Go to APIs & Services → Credentials
   - Click **"Create Credentials"** → OAuth client ID
   - Application type: **Web application**
   - Name: `Open Navigator Web Client`
   - Authorized redirect URIs:
     - `http://localhost:8000/api/auth/callback/google` (development)
     - `https://www.communityone.com/api/auth/callback/google` (production)
   - Click **"Create"**

5. Copy **Client ID** and **Client Secret**

#### Add to `.env`:

```bash
GOOGLE_CLIENT_ID=123456789-xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
```

---

### 3. Facebook OAuth

**Get credentials:** [developers.facebook.com/apps](https://developers.facebook.com/apps)

#### Steps:

1. **Create a new app**
   - Click **"Create App"**
   - Type: **Consumer**
   - App Name: `Open Navigator`

2. **Add Facebook Login**
   - Dashboard → Add Product
   - Select **"Facebook Login"** → Set up

3. **Configure OAuth settings**
   - Go to Facebook Login → Settings
   - Valid OAuth Redirect URIs:
     - `http://localhost:8000/api/auth/callback/facebook`
     - `https://www.communityone.com/api/auth/callback/facebook`
   - Client OAuth Login: **Yes**
   - Web OAuth Login: **Yes**

4. **Get App ID and Secret**
   - Go to Settings → Basic
   - Copy **App ID** and **App Secret**

#### Add to `.env`:

```bash
FACEBOOK_APP_ID=1234567890123456
FACEBOOK_APP_SECRET=xxxxxxxxxxxxx
```

---

### 4. GitHub OAuth

**Get credentials:** [github.com/settings/developers](https://github.com/settings/developers)

#### Steps:

1. **Register new OAuth application**
   - Go to Settings → Developer settings → OAuth Apps
   - Click **"New OAuth App"**

2. **Fill in details**
   - **Application name**: `Open Navigator`
   - **Homepage URL**: `https://www.communityone.com`
   - **Authorization callback URL**:
     - Development: `http://localhost:8000/api/auth/callback/github`
     - Production: `https://www.communityone.com/api/auth/callback/github`

3. **Create application**
   - Click **"Register application"**
   - Copy **Client ID**
   - Generate **Client Secret** and copy it

#### Add to `.env`:

```bash
GITHUB_CLIENT_ID=Iv1.xxxxxxxxxxxxx
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxx
```

---

## 🔑 Generate JWT Secret

Create a secure random secret for JWT tokens:

```bash
# Generate 32-byte random secret
openssl rand -hex 32

# Or use Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to `.env`:

```bash
JWT_SECRET_KEY=your_random_32_char_secret_here
```

---

## 🌐 Environment Configuration

### Development `.env`:

```bash
# Database
DATABASE_URL=postgresql://user:password@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require

# JWT
JWT_SECRET_KEY=your_random_secret_key

# Frontend URL
FRONTEND_URL=http://localhost:5173

# OAuth (all providers)
HUGGINGFACE_CLIENT_ID=hf_oauth_xxx
HUGGINGFACE_CLIENT_SECRET=hf_oauth_secret_xxx
GOOGLE_CLIENT_ID=123456789-xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx
FACEBOOK_APP_ID=123456789
FACEBOOK_APP_SECRET=xxx
GITHUB_CLIENT_ID=Iv1.xxx
GITHUB_CLIENT_SECRET=xxx
```

### Production (HuggingFace Spaces)

Add secrets in **Space Settings → Repository secrets**:

| Secret Name | Value |
|-------------|-------|
| `DATABASE_URL` | `postgresql://...neon.tech/...` |
| `JWT_SECRET_KEY` | Your random secret |
| `FRONTEND_URL` | `https://www.communityone.com` |
| `HUGGINGFACE_CLIENT_ID` | From HF OAuth app |
| `HUGGINGFACE_CLIENT_SECRET` | From HF OAuth app |
| `GOOGLE_CLIENT_ID` | From Google Cloud |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud |
| `FACEBOOK_APP_ID` | From Facebook app |
| `FACEBOOK_APP_SECRET` | From Facebook app |
| `GITHUB_CLIENT_ID` | From GitHub OAuth app |
| `GITHUB_CLIENT_SECRET` | From GitHub OAuth app |

---

## 🧪 Testing Authentication

### 1. Start the API server

```bash
source .venv/bin/activate
python main.py serve
```

### 2. Start the frontend

```bash
cd frontend
npm run dev
```

### 3. Test OAuth flows

1. Visit `http://localhost:5173`
2. Click **"Login"** in top-right
3. Select a provider (HuggingFace, Google, Facebook, or GitHub)
4. Complete OAuth flow
5. You should be redirected back with your profile visible

### 4. Verify database

Check that user was created in Neon:

```bash
# Option 1: Neon SQL Editor (in dashboard)
SELECT * FROM "user";

# Option 2: psql client
psql "postgresql://user:password@ep-xxx.neon.tech/neondb?sslmode=require"
\dt  # List tables
SELECT * FROM "user";
```

---

## 📊 Database Schema

The authentication system creates these tables automatically:

### `user` table (quoted in SQL: `"user"`)

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | Integer | Primary key |
| `email` | String(255) | User email (unique) |
| `username` | String(100) | Optional username |
| `full_name` | String(255) | Display name |
| `avatar_url` | String(500) | Profile picture URL |
| `oauth_provider` | String(50) | `huggingface`, `google`, `facebook`, `github` |
| `oauth_id` | String(255) | Provider's user ID |
| `hashed_password` | String(255) | For email/password (optional) |
| `is_active` | Boolean | Account status |
| `is_verified` | Boolean | Email verification status |
| `created_at` | DateTime | Account creation |
| `updated_at` | DateTime | Last update |
| `last_login` | DateTime | Last login timestamp |
| `preferences` | Text | User settings (JSON) |

### `contact_oauth_state` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `state_token` | String(255) | CSRF protection token |
| `provider` | String(50) | OAuth provider name |
| `redirect_uri` | String(500) | Callback URL |
| `created_at` | DateTime | Creation timestamp |
| `expires_at` | DateTime | Expiration (10 minutes) |

---

## 🔒 Security Best Practices

### ✅ DO:
- Use HTTPS in production
- Rotate JWT secrets regularly
- Keep OAuth secrets in environment variables (never commit to git)
- Use Neon's connection pooling
- Enable Neon's IP allowlist for production

### ❌ DON'T:
- Commit `.env` file to git (it's in `.gitignore`)
- Share OAuth secrets publicly
- Use weak JWT secrets
- Disable SSL mode on Neon connections

---

## 🚀 Production Deployment

### HuggingFace Spaces

All environment variables are automatically loaded from **Repository secrets**.

### Update OAuth redirect URIs

After deploying, update all OAuth apps with production callback URLs:

- HuggingFace: `https://www.communityone.com/api/auth/callback/huggingface`
- Google: `https://www.communityone.com/api/auth/callback/google`
- Facebook: `https://www.communityone.com/api/auth/callback/facebook`
- GitHub: `https://www.communityone.com/api/auth/callback/github`

---

## 🐛 Troubleshooting

### Database connection fails

```
❌ could not connect to server
```

**Fix:**
- Verify `DATABASE_URL` is correct
- Check Neon project is not suspended (free tier auto-suspends after inactivity)
- Ensure `?sslmode=require` is in connection string

### OAuth redirect mismatch

```
❌ redirect_uri_mismatch
```

**Fix:**
- Check redirect URI in OAuth app settings matches your server
- Ensure `http://` vs `https://` matches
- Verify port number (`:8000` for API)

### JWT token invalid

```
❌ Could not validate credentials
```

**Fix:**
- Ensure `JWT_SECRET_KEY` is set and matches between sessions
- Check token hasn't expired (7-day default)
- Clear browser localStorage and re-login

### Tables not created

```
❌ relation "users" does not exist (table renamed to `"user"`)
```

**Fix:**
- Restart API server to trigger `init_db()`
- Check database connection is successful
- Manually run: `from api.database import init_db; init_db()`

---

## 📚 Additional Resources

- [Neon Documentation](https://neon.tech/docs)
- [OAuth 2.0 RFC](https://datatracker.ietf.org/doc/html/rfc6749)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

---

## ✅ Checklist

Before going live, ensure:

- [ ] Neon database created and connected
- [ ] All 4 OAuth apps configured with production redirect URIs
- [ ] JWT secret generated (32+ characters)
- [ ] Environment variables added to HuggingFace Spaces secrets
- [ ] Database tables created (`"user"`, `contact_oauth_state`)
- [ ] OAuth flows tested with all 4 providers
- [ ] HTTPS enabled on custom domain
- [ ] Neon IP allowlist configured (optional, for extra security)

---

**Need help?** Open an issue on [GitHub](https://github.com/getcommunityone/open-navigator-for-engagement/issues)
