import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const checkAuth = useCallback(async () => {
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    // AuthCallback will exchange the session_id and establish the session first.
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    if (window.location.hash?.includes('session_id=')) {
      setLoading(false);
      return;
    }

    try {
      // Use new session endpoint for auth check
      const response = await fetch(`${API}/auth/session`, {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        if (data.authenticated && data.user) {
          setUser(data.user);
        } else {
          setUser(null);
        }
      } else if (response.status === 401) {
        // Try to refresh token before giving up
        const refreshResponse = await fetch(`${API}/auth/refresh`, {
          method: 'POST',
          credentials: 'include'
        });
        
        if (refreshResponse.ok) {
          // Token refreshed, check session again
          const retryResponse = await fetch(`${API}/auth/session`, {
            credentials: 'include'
          });
          if (retryResponse.ok) {
            const data = await retryResponse.json();
            if (data.authenticated && data.user) {
              setUser(data.user);
              return;
            }
          }
        }
        // Refresh failed, user needs to login
        setUser(null);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = async (email, password) => {
    const response = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    // Store token for WebSocket auth
    if (data.token) {
      localStorage.setItem('auth_token', data.token);
    }
    setUser(data);
    return data;
  };

  const register = async (name, email, password) => {
    const response = await fetch(`${API}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ name, email, password })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    const data = await response.json();
    // Store token for WebSocket auth
    if (data.token) {
      localStorage.setItem('auth_token', data.token);
    }
    setUser(data);
    return data;
  };

  const loginWithGoogle = (role = 'buyer') => {
    const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;
    if (!clientId) {
      console.error('Google OAuth client ID not configured');
      return;
    }
    const redirectUri = `${window.location.origin}/auth/google/callback`;
    const scope = 'email profile';
    const state = encodeURIComponent(JSON.stringify({ role }));
    
    const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
      `client_id=${clientId}` +
      `&redirect_uri=${encodeURIComponent(redirectUri)}` +
      `&response_type=code` +
      `&scope=${encodeURIComponent(scope)}` +
      `&state=${state}` +
      `&access_type=offline` +
      `&prompt=select_account`;
    
    window.location.href = googleAuthUrl;
  };

  const exchangeSession = async (sessionId, intendedRole = null) => {
    const body = { session_id: sessionId };
    if (intendedRole) {
      body.intended_role = intendedRole;
    }
    
    const response = await fetch(`${API}/auth/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Session exchange failed');
    }

    const data = await response.json();
    setUser(data);
    return data;
  };

  /**
   * Enter the demo app. When fresh is true, the backend purges and re-seeds all demo_* data,
   * then issues a normal session (same cookie shape as email login).
   */
  const enterDemo = async ({ persona, buyerSlot = 1, fresh = true }) => {
    const response = await fetch(`${API}/demo/enter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        persona,
        buyer_slot: buyerSlot,
        fresh,
      }),
    });

    if (!response.ok) {
      let detail = 'Demo login failed';
      try {
        const err = await response.json();
        const d = err.detail;
        if (Array.isArray(d)) {
          detail = d.map((e) => (typeof e === 'object' && e.msg) ? e.msg : JSON.stringify(e)).join('; ') || detail;
        } else if (typeof d === 'string') {
          detail = d;
        }
      } catch {
        /* ignore */
      }
      throw new Error(detail);
    }

    const data = await response.json();
    if (data.token) {
      localStorage.setItem('auth_token', data.token);
    }
    setUser(data);
    return data;
  };

  const logout = async () => {
    try {
      await fetch(`${API}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (error) {
      console.error('Logout error:', error);
    }
    // Clear token from localStorage
    localStorage.removeItem('auth_token');
    setUser(null);
    navigate('/login');
  };

  // Set user directly (used after OAuth callback)
  const setAuthUser = useCallback((userData) => {
    if (userData?.token) {
      localStorage.setItem('auth_token', userData.token);
    }
    setUser(userData);
  }, []);

  const value = {
    user,
    loading,
    login,
    register,
    loginWithGoogle,
    exchangeSession,
    enterDemo,
    logout,
    checkAuth,
    setAuthUser
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
