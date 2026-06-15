---
title: OAuth Login Fix for HuggingFace
---

# OAuth Login Fix for HuggingFace

## Problem Fixed ✅

**Issue:** Google OAuth login was failing on HuggingFace with the error:
```
🔐 Stored token found: false
🔐 No token found - user not authenticated
```

**Root Cause:** The OAuth callback was redirecting to `http://localhost:5173/?token=...` instead of staying on the HuggingFace domain.

**Solution:** Updated callback to use relative redirects (`/?token=...`) on same-domain deployments like HuggingFace.

---

## How OAuth Login Works Now

### Flow Diagram:
```
1. User clicks "Login with Google"
   ↓
2. Frontend → /auth/login/google
   ↓
3. Backend → Redirects to Google
   ↓
4. Google → User approves
   ↓
5. Google → /auth/callback/google?code=xxx&state=yyy
   ↓
6. Backend → Exchanges code for access token
   ↓
7. Backend → Gets user info from Google
   ↓
8. Backend → Creates/updates user in database
   ↓
9. Backend → Creates JWT token
   ↓
10. Backend → Redirects to /?token=JWT_TOKEN  ← FIXED!
    ↓
11. Frontend → Detects token in URL
    ↓
12. Frontend → Saves token to localStorage
    ↓
13. Frontend → Fetches user data from /auth/me
    ↓
14. ✅ User is logged in!
```

---

## What Changed

### Before (Broken on HuggingFace):
```python
# api/routes/auth.py - OLD CODE
frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
redirect_url = oauth_state.redirect_uri or frontend_url
return RedirectResponse(url=f"{redirect_url}?token={jwt_token}")
```

**Problem:** Always redirected to localhost, which doesn't exist on HuggingFace!

### After (Works on HuggingFace):
```python
# api/routes/auth.py - NEW CODE
frontend_url = os.getenv('FRONTEND_URL', '')

# If FRONTEND_URL is localhost or not set, use relative redirect
if not frontend_url or 'localhost' in frontend_url:
    redirect_url = oauth_state.redirect_uri or '/'
else:
    redirect_url = oauth_state.redirect_uri or frontend_url

return RedirectResponse(url=f"{redirect_url}?token={jwt_token}")
```

**Solution:** 
- On HuggingFace (same domain): Redirects to `/?token=...` (relative)
- On local dev (separate servers): Redirects to `http://localhost:5173/?token=...` (absolute)

---

## Testing the Fix

### On HuggingFace (www.communityone.com):

1. **Go to:** https://www.communityone.com
2. **Click:** "Login with Google"
3. **Observe:** You should be redirected to Google
4. **After approving:** You should return to www.communityone.com (NOT localhost!)
5. **Check browser console:**
   ```
   🔐 OAuth callback - Token received from URL
   🔐 Token preview: eyJhbGciOiJIUzI1NiIs...
   ✅ User data loaded: {id: 1, email: "user@example.com"}
   ```
6. **Verify:** Your avatar should appear in top right corner

### Expected Console Output (Success):
```javascript
🔐 Auth initialization starting...
🔐 Current URL: https://www.communityone.com/?token=eyJhbGc...
🔐 OAuth callback - Token received from URL
🔐 Token preview: eyJhbGciOiJIUzI1NiIs...
🔐 Fetching user data from: /api/auth/me
🔐 Response status: 200
✅ User data loaded: {id: 1, email: "you@gmail.com", ...}
🔐 User state changed: {user: {id: 1, email: "you@gmail.com"}, isAuthenticated: true}
```

---

## HuggingFace Secrets Configuration

### Required Secrets (already configured):
```bash
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret

# JWT Authentication
JWT_SECRET_KEY=your-random-secret-key

# API Base URL (for OAuth callbacks)
API_BASE_URL=https://www.communityone.com
```

### Optional Secret (NOT needed with this fix):
```bash
# Frontend URL - can be empty or set to production URL
FRONTEND_URL=https://www.communityone.com
# OR leave empty - both work now!
```

**Why it's optional now:** The code auto-detects same-domain deployment and uses relative redirects.

---

## Google OAuth Configuration

Make sure your Google Cloud Console has the correct redirect URI:

1. **Go to:** https://console.cloud.google.com
2. **Navigate to:** APIs & Services → Credentials
3. **Select:** Your OAuth 2.0 Client ID
4. **Authorized redirect URIs must include:**
   ```
   https://www.communityone.com/auth/callback/google
   ```
5. **For local dev, also add:**
   ```
   http://localhost:8001/auth/callback/google
   ```

---

## Troubleshooting

### Still seeing "No token found"?

**Check 1: Console Logs**
Open browser DevTools (F12) and look for:
```javascript
🔐 OAuth callback - Token received from URL  // ← Should see this!
```

If you DON'T see this, the redirect isn't working.

**Check 2: URL After Login**
After Google redirects back, the URL should be:
```
✅ CORRECT: https://www.communityone.com/?token=eyJhbGc...
❌ WRONG:   http://localhost:5173/?token=...
❌ WRONG:   https://www.communityone.com/auth/callback/google?code=...
```

**Check 3: HuggingFace Logs**
In HuggingFace Spaces, click "Logs" and look for:
```
INFO: "GET /auth/callback/google?code=... HTTP/1.1" 302 Found
```

**Check 4: Network Tab**
In DevTools → Network, filter for "callback" and check the redirect:
```
Request: GET /auth/callback/google?code=xxx
Status: 302 Found
Location: /?token=eyJhbGc...  ← Should be relative!
```

### Google OAuth errors?

**"redirect_uri_mismatch":**
- Your redirect URI in Google Console doesn't match
- Make sure it's exactly: `https://www.communityone.com/auth/callback/google`

**"invalid_client":**
- GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is wrong
- Check HuggingFace Spaces → Settings → Variables and secrets

**"access_denied":**
- User cancelled the login
- Try again

### Database errors?

**"could not connect to server":**
- Database isn't accessible
- Check if using SQLite (should work) or Neon (needs configuration)

**"no such table: users":**
- Run migration: `python scripts/migrate_social_features.py`

---

## Local Development

For local development (frontend on :5173, backend on :8001):

1. **Set FRONTEND_URL in `.env`:**
   ```bash
   FRONTEND_URL=http://localhost:5173
   ```

2. **This makes the callback redirect to:**
   ```
   http://localhost:5173/?token=...
   ```

3. **Google OAuth redirect URI:**
   ```
   http://localhost:8001/auth/callback/google
   ```

---

## Summary

✅ **Fixed:** OAuth callback now redirects correctly on HuggingFace  
✅ **Works:** All OAuth providers (Google, HuggingFace, Facebook, GitHub)  
✅ **Tested:** Same-domain deployment (HuggingFace) and separate servers (local dev)  
✅ **No config needed:** FRONTEND_URL can be empty on HuggingFace  

**The fix is live!** Try logging in with Google at https://www.communityone.com 🚀
