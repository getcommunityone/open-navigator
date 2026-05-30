import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  id: number;
  email: string;
  username?: string;
  full_name?: string;
  avatar_url?: string;
  oauth_provider?: string;
  state?: string;
  county?: string;
  city?: string;
  school_board?: string;
  profile_completed?: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (provider: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
  clearAuthError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);

  // Use /api for both dev and prod - Vite proxy handles dev routing
  const API_URL = '/api';

  // Load user from localStorage on mount
  useEffect(() => {
    // Check for token in URL FIRST (OAuth callback)
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get('token');
    const urlError = urlParams.get('error');
    
    if (urlError) {
      // Show OAuth error to user
      setAuthError(urlError);
      // Clean URL (remove error from address bar)
      window.history.replaceState({}, document.title, window.location.pathname);
      setIsLoading(false);
      return;
    }
    
    if (urlToken) {
      localStorage.setItem('auth_token', urlToken);
      setToken(urlToken);
      fetchUser(urlToken);
      
      // Clean URL (remove token from address bar)
      window.history.replaceState({}, document.title, window.location.pathname);
      return; // Exit early, fetchUser will handle loading state
    }
    
    // Check for stored token
    const storedToken = localStorage.getItem('auth_token');
    
    if (storedToken) {
      setToken(storedToken);
      fetchUser(storedToken);
    } else {
      setIsLoading(false);
    }
  }, []);

  const fetchUser = async (authToken: string) => {
    try {
      const response = await fetch(`${API_URL}/auth/me`, {
        headers: {
          'Authorization': `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const userData = await response.json();
        console.log('✅ User data received:', {
          email: userData.email,
          full_name: userData.full_name,
          oauth_provider: userData.oauth_provider,
          avatar_url: userData.avatar_url ? `${userData.avatar_url.substring(0, 50)}...` : 'null',
        });
        setUser(userData);
      } else {
        // Token is invalid
        console.error('❌ Auth token invalid, status:', response.status);
        localStorage.removeItem('auth_token');
        setToken(null);
      }
    } catch (error) {
      console.error('Error fetching user:', error);
      localStorage.removeItem('auth_token');
      setToken(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = (provider: string) => {
    // Redirect to OAuth endpoint
    const redirectUri = encodeURIComponent(window.location.origin);
    const authUrl = `${API_URL}/auth/login/${provider}?redirect_uri=${redirectUri}`;
    window.location.href = authUrl;
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setUser(null);
  };

  const clearAuthError = () => {
    setAuthError(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isAuthenticated: !!user,
        isLoading,
        authError,
        clearAuthError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
