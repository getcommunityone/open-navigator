"""
OAuth authentication routes - HuggingFace, Google, Facebook, GitHub
"""
import os
import hmac
import hashlib
import httpx
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
from dotenv import load_dotenv
from loguru import logger

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.database import get_db
from api.models import User, OAuthState
from api.auth import create_access_token, generate_state_token

# Load environment variables from .env file
load_dotenv()

router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth provider configurations
OAUTH_PROVIDERS = {
    'huggingface': {
        'authorize_url': 'https://huggingface.co/oauth/authorize',
        'token_url': 'https://huggingface.co/oauth/token',
        'userinfo_url': 'https://huggingface.co/api/whoami-v2',
        'scope': 'openid profile email',
        'client_id_env': 'HUGGINGFACE_CLIENT_ID',
        'client_secret_env': 'HUGGINGFACE_CLIENT_SECRET',
    },
    'google': {
        'authorize_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://www.googleapis.com/oauth2/v2/userinfo',
        'scope': 'openid email profile',
        'client_id_env': 'GOOGLE_CLIENT_ID',
        'client_secret_env': 'GOOGLE_CLIENT_SECRET',
    },
    'facebook': {
        'authorize_url': 'https://www.facebook.com/v18.0/dialog/oauth',
        'token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',
        'userinfo_url': 'https://graph.facebook.com/me?fields=id,name,email,picture',
        'scope': 'email public_profile',
        'client_id_env': 'FACEBOOK_APP_ID',
        'client_secret_env': 'FACEBOOK_APP_SECRET',
    },
    'github': {
        'authorize_url': 'https://github.com/login/oauth/authorize',
        'token_url': 'https://github.com/login/oauth/access_token',
        'userinfo_url': 'https://api.github.com/user',
        'scope': 'user:email',
        'client_id_env': 'GITHUB_CLIENT_ID',
        'client_secret_env': 'GITHUB_CLIENT_SECRET',
    },
}


# Response models
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    user_id: int
    email: str
    username: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    oauth_provider: Optional[str]
    state: Optional[str]
    county: Optional[str]
    city: Optional[str]
    school_board: Optional[str]
    profile_completed: Optional[bool]
    is_admin: Optional[bool] = False


# Helper functions
def get_base_url(request: Request) -> str:
    """
    Get the base URL from the request, handling proxy headers
    
    In production (HuggingFace Spaces with nginx reverse proxy):
    - Returns: https://www.communityone.com
    
    In local development:
    - Returns: http://localhost:8001
    """
    # Check for explicit API_BASE_URL override first
    if base_url := os.getenv('API_BASE_URL'):
        # Only use if it's not the default localhost value
        if 'localhost' not in base_url and '127.0.0.1' not in base_url:
            return base_url
    
    # Detect from request headers (handles nginx reverse proxy)
    scheme = request.headers.get('x-forwarded-proto', request.url.scheme)
    host = request.headers.get('x-forwarded-host', request.headers.get('host', request.url.netloc))
    
    # Clean up host (remove port if it's standard)
    if ':' in host:
        host_parts = host.split(':')
        port = host_parts[1]
        # Remove standard ports
        if (scheme == 'https' and port == '443') or (scheme == 'http' and port == '80'):
            host = host_parts[0]
    
    return f"{scheme}://{host}"


def get_or_create_user(
    db: Session,
    email: str,
    provider: str,
    oauth_id: str,
    full_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    username: Optional[str] = None,
) -> User:
    """Get existing user or create new one from OAuth data"""
    
    # Try to find existing user by OAuth ID first
    user = db.query(User).filter(
        User.oauth_provider == provider,
        User.oauth_id == oauth_id
    ).first()
    
    if user:
        # Update user info if changed
        user.full_name = full_name or user.full_name
        user.avatar_url = avatar_url or user.avatar_url
        user.username = username or user.username
        user.last_login = datetime.utcnow()
        db.commit()
        return user
    
    # Try to find by email
    user = db.query(User).filter(User.email == email).first()
    
    if user:
        # Link OAuth account to existing user
        user.oauth_provider = provider
        user.oauth_id = oauth_id
        user.full_name = full_name or user.full_name
        user.avatar_url = avatar_url or user.avatar_url
        user.username = username or user.username
        user.last_login = datetime.utcnow()
        user.is_verified = True  # OAuth emails are verified
        db.commit()
        return user
    
    # Create new user
    user = User(
        email=email,
        username=username,
        full_name=full_name,
        avatar_url=avatar_url,
        oauth_provider=provider,
        oauth_id=oauth_id,
        is_verified=True,
        is_active=True,
        last_login=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# OAuth routes
@router.get("/login/{provider}")
async def oauth_login(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    redirect_uri: Optional[str] = None
):
    """
    Initiate OAuth login flow
    
    Supported providers: huggingface, google, facebook, github
    """
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    config = OAUTH_PROVIDERS[provider]
    client_id = os.getenv(config['client_id_env'])
    client_secret = os.getenv(config['client_secret_env'])

    # Missing OAuth credentials is a configuration problem, not a server crash.
    # Return a clear 503 so the cause is visible instead of a swallowed 500.
    if not client_id or not client_secret:
        missing = config['client_id_env'] if not client_id else config['client_secret_env']
        logger.error("OAuth not configured for {}: missing env var {}", provider, missing)
        raise HTTPException(
            status_code=503,
            detail=(
                f"{provider.title()} sign-in is temporarily unavailable "
                f"(server is missing {missing}). Please try another sign-in method "
                "or contact johnbowyer@communityone.com."
            ),
        )

    # Generate state token for CSRF protection and persist it.
    # A failure here is almost always a missing/unmigrated oauth_states table —
    # surface that explicitly rather than letting it fall through as a generic 500.
    state = generate_state_token()
    try:
        oauth_state = OAuthState(
            state_token=state,
            provider=provider,
            redirect_uri=redirect_uri,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
        )
        db.add(oauth_state)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Failed to persist OAuth state for {}: {}", provider, e)
        raise HTTPException(
            status_code=503,
            detail=(
                f"{provider.title()} sign-in is temporarily unavailable "
                "(could not start the login session). Please try again shortly "
                "or contact johnbowyer@communityone.com."
            ),
        )
    
    # Build callback URL dynamically from request (handles both local and production)
    base_url = get_base_url(request)
    callback_url = f"{base_url}/api/auth/callback/{provider}"
    
    # Build authorization URL
    params = {
        'client_id': client_id,
        'redirect_uri': callback_url,
        'scope': config['scope'],
        'state': state,
        'response_type': 'code',
    }
    
    auth_url = f"{config['authorize_url']}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback/{provider}", name="oauth_callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """OAuth callback handler"""
    
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter")
    
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
    
    # Verify state token
    oauth_state = db.query(OAuthState).filter(
        OAuthState.state_token == state,
        OAuthState.provider == provider
    ).first()
    
    if not oauth_state or oauth_state.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired state token")
    
    config = OAUTH_PROVIDERS[provider]
    client_id = os.getenv(config['client_id_env'])
    client_secret = os.getenv(config['client_secret_env'])
    
    # Build callback URL dynamically from request (must match the one sent to authorize)
    base_url = get_base_url(request)
    callback_url = f"{base_url}/api/auth/callback/{provider}"
    
    # Exchange code for access token
    try:
        logger.info(f"🔐 [{provider.upper()}] Starting token exchange")
        logger.info(f"🔐 [{provider.upper()}] Token URL: {config['token_url']}")
        logger.info(f"🔐 [{provider.upper()}] Callback URL: {callback_url}")
        logger.info(f"🔐 [{provider.upper()}] Client ID configured: {bool(client_id)}")
        logger.info(f"🔐 [{provider.upper()}] Client Secret configured: {bool(client_secret)}")
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                config['token_url'],
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code': code,
                    'redirect_uri': callback_url,
                    'grant_type': 'authorization_code',
                },
                headers={'Accept': 'application/json'}
            )
            
            logger.info(f"📊 [{provider.upper()}] Token response status: {token_response.status_code}")
            
            if token_response.status_code != 200:
                logger.error(f"❌ [{provider.upper()}] Token exchange failed!")
                logger.error(f"❌ [{provider.upper()}] Response: {token_response.text}")
                
                # Parse error response for user-friendly message
                error_msg = "Authentication failed"
                try:
                    error_data = token_response.json()
                    # Facebook error format: {"error": {"message": "...", "type": "..."}}
                    if 'error' in error_data:
                        if isinstance(error_data['error'], dict):
                            error_msg = error_data['error'].get('message', error_msg)
                            # Special handling for Facebook's "error validating web secret"
                            if provider == 'facebook' and 'validating' in error_msg.lower() and 'secret' in error_msg.lower():
                                error_msg = "Invalid App Secret. Please update FACEBOOK_APP_SECRET in your .env file with the correct secret from Facebook Developer Console."
                        else:
                            error_msg = str(error_data['error'])
                    # Google/other providers: {"error": "...", "error_description": "..."}
                    elif 'error_description' in error_data:
                        error_msg = error_data['error_description']
                    elif 'error' in error_data:
                        error_msg = error_data['error']
                except:
                    error_msg = f"Authentication failed (HTTP {token_response.status_code})"
                
                # Log full error for debugging
                logger.error(f"OAuth token exchange failed for {provider}: {token_response.text}")
                
                # Redirect to frontend with error
                frontend_url = os.getenv('FRONTEND_URL', '')
                redirect_url = oauth_state.redirect_uri or (frontend_url if frontend_url and 'localhost' not in frontend_url else '/')
                params = urlencode({'error': f'{provider.title()} login failed: {error_msg}'})
                return RedirectResponse(url=f"{redirect_url}?{params}")
            
            token_data = token_response.json()
            logger.info(f"✅ [{provider.upper()}] Token response keys: {list(token_data.keys())}")
            access_token = token_data.get('access_token')
            
            if not access_token:
                logger.error(f"❌ [{provider.upper()}] No access token in response!")
                logger.error(f"No access token in response from {provider}: {token_data}")
                frontend_url = os.getenv('FRONTEND_URL', '')
                redirect_url = oauth_state.redirect_uri or (frontend_url if frontend_url and 'localhost' not in frontend_url else '/')
                params = urlencode({'error': f'{provider.title()} login failed: No access token received'})
                return RedirectResponse(url=f"{redirect_url}?{params}")
            
            logger.info(f"✅ [{provider.upper()}] Got access token (first 20 chars): {access_token[:20]}...")
            
            # Get user info from provider
            logger.info(f"🔍 [{provider.upper()}] Fetching user info...")
            user_info = await get_user_info(provider, access_token, config)
            logger.info(f"📊 [{provider.upper()}] User info result: {user_info is not None}")
        
        # Validate we got user info (email is now always set, even if placeholder for Facebook)
        if not user_info:
            logger.error(f"❌ [{provider.upper()}] Could not retrieve user info! Check API response logs above.")
            logger.error(f"Could not retrieve user info from {provider}. Check API response logs above.")
            frontend_url = os.getenv('FRONTEND_URL', '')
            redirect_url = oauth_state.redirect_uri or (frontend_url if frontend_url and 'localhost' not in frontend_url else '/')
            params = urlencode({'error': f'{provider.title()} login failed: Could not retrieve user information'})
            return RedirectResponse(url=f"{redirect_url}?{params}")
    
    except Exception as e:
        logger.error(f"Unexpected error during {provider} OAuth: {str(e)}")
        frontend_url = os.getenv('FRONTEND_URL', '')
        redirect_url = oauth_state.redirect_uri or (frontend_url if frontend_url and 'localhost' not in frontend_url else '/')
        params = urlencode({'error': f'{provider.title()} login failed: {str(e)}'})
        return RedirectResponse(url=f"{redirect_url}?{params}")
    
    # Get or create user
    user = get_or_create_user(
        db=db,
        email=user_info['email'],
        provider=provider,
        oauth_id=user_info['oauth_id'],
        full_name=user_info.get('full_name'),
        avatar_url=user_info.get('avatar_url'),
        username=user_info.get('username'),
    )
    
    # Clean up state token
    db.delete(oauth_state)
    db.commit()
    
    # Create JWT token (sub must be string, not int)
    jwt_token = create_access_token(data={"sub": str(user.user_id)})
    
    # Redirect to frontend with token
    # On HuggingFace/production, frontend and backend are same domain - use relative path
    # On local dev, frontend is separate server - use FRONTEND_URL
    frontend_url = os.getenv('FRONTEND_URL', '')
    
    # If FRONTEND_URL is localhost or not set, assume same-domain deployment (HuggingFace)
    if not frontend_url or 'localhost' in frontend_url:
        # Use relative redirect (works on HuggingFace where both are same domain)
        redirect_url = oauth_state.redirect_uri or '/'
    else:
        # Use absolute URL for separate frontend server
        redirect_url = oauth_state.redirect_uri or frontend_url
    
    # Append token as URL parameter
    params = urlencode({'token': jwt_token})
    full_redirect_url = f"{redirect_url}?{params}" if '?' not in redirect_url else f"{redirect_url}&{params}"
    
    return RedirectResponse(url=full_redirect_url)


async def get_user_info(provider: str, access_token: str, config: dict) -> dict:
    """Get user information from OAuth provider"""
    
    async with httpx.AsyncClient() as client:
        headers = {'Authorization': f'Bearer {access_token}'}
        
        user_info = {}
        
        if provider == 'huggingface':
            resp = await client.get(config['userinfo_url'], headers=headers)
            data = resp.json()
            user_info = {
                'email': data.get('email'),
                'oauth_id': str(data.get('id')),
                'full_name': data.get('fullname') or data.get('name'),
                'avatar_url': data.get('avatarUrl'),
                'username': data.get('name'),
            }
        
        elif provider == 'google':
            resp = await client.get(config['userinfo_url'], headers=headers)
            data = resp.json()
            user_info = {
                'email': data.get('email'),
                'oauth_id': data.get('id'),
                'full_name': data.get('name'),
                'avatar_url': data.get('picture'),
                'username': data.get('email', '').split('@')[0],
            }
        
        elif provider == 'facebook':
            # Facebook requires appsecret_proof for server-side API calls
            # Generate HMAC-SHA256 hash of access token using app secret
            app_secret = os.getenv('FACEBOOK_APP_SECRET')
            if not app_secret:
                logger.error("❌ [FACEBOOK] FACEBOOK_APP_SECRET not configured!")
                return None
            
            # Create appsecret_proof
            appsecret_proof = hmac.new(
                app_secret.encode('utf-8'),
                access_token.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Facebook uses access token as query parameter, not Bearer header
            # Add appsecret_proof for security
            userinfo_url_with_token = f"{config['userinfo_url']}&access_token={access_token}&appsecret_proof={appsecret_proof}"
            
            logger.info(f"🔍 [FACEBOOK] Requesting user info from: {config['userinfo_url']}")
            logger.info(f"🔍 [FACEBOOK] Access token (first 20 chars): {access_token[:20]}...")
            logger.info(f"🔐 [FACEBOOK] Generated appsecret_proof: {appsecret_proof[:20]}...")
            
            try:
                resp = await client.get(userinfo_url_with_token)
                
                # Enhanced logging for debugging
                logger.info(f"📊 [FACEBOOK] API response status: {resp.status_code}")
                logger.info(f"📊 [FACEBOOK] API response headers: {dict(resp.headers)}")
                logger.info(f"📊 [FACEBOOK] API response body: {resp.text[:1000]}")
                
                if resp.status_code != 200:
                    logger.error(f"❌ [FACEBOOK] Userinfo request failed!")
                    logger.error(f"❌ [FACEBOOK] Status: {resp.status_code}")
                    logger.error(f"❌ [FACEBOOK] Full response: {resp.text}")
                    return None
                
                data = resp.json()
                logger.info(f"✅ [FACEBOOK] Successfully parsed JSON response")
                logger.info(f"✅ [FACEBOOK] Data keys: {list(data.keys())}")
                
                # Validate we got required data
                if not data.get('id'):
                    logger.error(f"❌ [FACEBOOK] Missing user ID in response!")
                    logger.error(f"❌ [FACEBOOK] Full response data: {data}")
                    return None
                
                logger.info(f"✅ [FACEBOOK] Got user ID: {data.get('id')}")
                
                # Facebook may not return email if permission not approved in App Review
                # Generate a placeholder email using Facebook ID if email not available
                email = data.get('email')
                if not email:
                    fb_id = data.get('id')
                    email = f"facebook_{fb_id}@communityone.placeholder"
                    logger.warning(f"⚠️  [FACEBOOK] No email returned for user {fb_id}. Using placeholder: {email}")
                else:
                    logger.info(f"✅ [FACEBOOK] Got email: {email}")
                
                user_info = {
                    'email': email,
                    'oauth_id': str(data.get('id')),
                    'full_name': data.get('name'),
                    'avatar_url': data.get('picture', {}).get('data', {}).get('url') if isinstance(data.get('picture'), dict) else None,
                    'username': data.get('name', '').replace(' ', '_').lower(),
                }
                logger.info(f"✅ [FACEBOOK] Created user_info: {user_info}")
                
            except Exception as e:
                logger.error(f"❌ [FACEBOOK] Exception during user info fetch: {str(e)}")
                logger.error(f"❌ [FACEBOOK] Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"❌ [FACEBOOK] Traceback: {traceback.format_exc()}")
                return None
        
        elif provider == 'github':
            # Get user profile
            resp = await client.get(config['userinfo_url'], headers=headers)
            data = resp.json()
            
            # Get user email if not public
            email = data.get('email')
            if not email:
                resp_emails = await client.get('https://api.github.com/user/emails', headers=headers)
                emails = resp_emails.json()
                email = next((e['email'] for e in emails if e.get('primary')), emails[0]['email'] if emails else None)
            
            user_info = {
                'email': email,
                'oauth_id': str(data.get('id')),
                'full_name': data.get('name'),
                'avatar_url': data.get('avatar_url'),
                'username': data.get('login'),
            }
        
        return user_info


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get current authenticated user info"""
    
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(' ')[1]
    
    # Decode token and get user
    from api.auth import decode_access_token
    payload = decode_access_token(token)
    user_id = int(payload.get('sub'))  # Convert back to int for DB query
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.patch("/profile", response_model=UserResponse)
def update_user_profile(
    profile_data: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update user profile (location preferences)"""
    
    # Get token from Authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(' ')[1]
    
    # Decode token and get user
    from api.auth import decode_access_token
    payload = decode_access_token(token)
    user_id = int(payload.get('sub'))
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update allowed fields
    allowed_fields = ['state', 'county', 'city', 'school_board', 'profile_completed']
    for field, value in profile_data.items():
        if field in allowed_fields and hasattr(user, field):
            setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/logout")
def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Logged out successfully. Please remove the token from client."}
