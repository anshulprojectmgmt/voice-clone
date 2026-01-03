"use client";

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface User {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login?: string;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface AuthContextType {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // Load tokens from localStorage on mount
  useEffect(() => {
    const loadAuth = async () => {
      try {
        const storedTokens = localStorage.getItem('auth_tokens');
        if (storedTokens) {
          const parsedTokens: AuthTokens = JSON.parse(storedTokens);
          setTokens(parsedTokens);

          // Fetch user info
          await fetchUserInfo(parsedTokens.access_token);
        }
      } catch (error) {
        console.error('Failed to load auth:', error);
        localStorage.removeItem('auth_tokens');
      } finally {
        setIsLoading(false);
      }
    };

    loadAuth();
  }, []);

  // Auto-refresh token before expiry
  useEffect(() => {
    if (!tokens) return;

    const refreshInterval = setInterval(async () => {
      try {
        await refreshAccessToken();
      } catch (error) {
        console.error('Failed to refresh token:', error);
        await logout();
      }
    }, (tokens.expires_in - 60) * 1000); // Refresh 1 minute before expiry

    return () => clearInterval(refreshInterval);
  }, [tokens]);

  const fetchUserInfo = async (accessToken: string) => {
    const response = await fetch(`${API_URL}/api/v1/auth/me`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch user info');
    }

    const userData = await response.json();
    setUser(userData);
  };

  const login = async (username: string, password: string) => {
    const response = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const authData: AuthTokens = await response.json();

    // Store tokens
    setTokens(authData);
    localStorage.setItem('auth_tokens', JSON.stringify(authData));

    // Fetch user info
    await fetchUserInfo(authData.access_token);

    // Redirect to home
    router.push('/');
  };

  const register = async (username: string, email: string, password: string) => {
    const response = await fetch(`${API_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    const authData: AuthTokens = await response.json();

    // Store tokens
    setTokens(authData);
    localStorage.setItem('auth_tokens', JSON.stringify(authData));

    // Fetch user info
    await fetchUserInfo(authData.access_token);

    // Redirect to home
    router.push('/');
  };

  const logout = async () => {
    try {
      if (tokens) {
        // Call logout API to revoke refresh token
        await fetch(`${API_URL}/api/v1/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${tokens.access_token}`,
          },
          body: JSON.stringify({ refresh_token: tokens.refresh_token }),
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local state regardless of API success
      setUser(null);
      setTokens(null);
      localStorage.removeItem('auth_tokens');
      router.push('/login');
    }
  };

  const refreshAccessToken = async () => {
    if (!tokens) return;

    const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: tokens.refresh_token }),
    });

    if (!response.ok) {
      throw new Error('Failed to refresh token');
    }

    const newTokens: AuthTokens = await response.json();
    setTokens(newTokens);
    localStorage.setItem('auth_tokens', JSON.stringify(newTokens));
  };

  const value: AuthContextType = {
    user,
    tokens,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    refreshAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Helper hook to get auth headers for API requests
export function useAuthHeaders() {
  const { tokens } = useAuth();

  return tokens
    ? { 'Authorization': `Bearer ${tokens.access_token}` }
    : {};
}
