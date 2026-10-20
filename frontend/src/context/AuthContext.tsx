import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api, setOnUnauthorizedCallback } from '../services/api';
import type { User } from '../types/auth';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (name: string, email: string, password: string) => Promise<User>;
  logout: () => void;
  updateUserDisplay: (name: string) => Promise<User>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => api.getToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Monotonically increasing counter to prevent stale asynchronous responses
  // from restoring a logged-out account or overwriting a newly signed-in account.
  const sessionCounterRef = useRef<number>(0);

  const logout = useCallback(() => {
    sessionCounterRef.current += 1;
    api.logout();
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const currentToken = api.getToken();
    const thisSession = ++sessionCounterRef.current;

    if (!currentToken) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const userData = await api.getMe();
      // Ensure this request has not been superseded by a subsequent login or logout
      if (sessionCounterRef.current === thisSession && api.getToken() === currentToken) {
        // Unknown roles must fail closed
        if (userData.role === 'ADMIN' || userData.role === 'USER') {
          setUser(userData);
          setToken(currentToken);
        } else {
          logout();
        }
      }
    } catch {
      if (sessionCounterRef.current === thisSession) {
        logout();
      }
    } finally {
      if (sessionCounterRef.current === thisSession) {
        setIsLoading(false);
      }
    }
  }, [logout]);

  useEffect(() => {
    setOnUnauthorizedCallback(() => {
      logout();
    });
    refreshUser();
  }, [logout, refreshUser]);

  const login = async (email: string, password: string): Promise<User> => {
    // Increment generation and clear previous account data immediately to avoid carry-over
    const thisSession = ++sessionCounterRef.current;
    setUser(null);

    const res = await api.login(email, password);

    // Fail closed if role is unknown
    if (res.user.role !== 'ADMIN' && res.user.role !== 'USER') {
      logout();
      throw new Error('Account has an unrecognized role. Access denied.');
    }

    if (sessionCounterRef.current === thisSession) {
      setToken(res.access_token);
      setUser(res.user);
    }
    return res.user;
  };

  const signup = async (name: string, email: string, password: string): Promise<User> => {
    return api.signup(name, email, password);
  };

  const updateUserDisplay = async (name: string): Promise<User> => {
    const updated = await api.updateProfile(name);
    setUser(updated);
    return updated;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        signup,
        logout,
        updateUserDisplay,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
