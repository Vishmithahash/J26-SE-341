import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { api, setOnUnauthorizedCallback } from '../services/api';

const AuthContext = createContext(undefined);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => api.getToken());
  const [isLoading, setIsLoading] = useState(true);

  // Monotonically increasing counter to prevent stale asynchronous responses
  // from restoring a logged-out account or overwriting a newly signed-in account.
  const sessionCounterRef = useRef(0);

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

  const login = async (email, password) => {
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

  const signup = async (name, email, password) => {
    return api.signup(name, email, password);
  };

  const updateUserDisplay = async (name) => {
    const updated = await api.updateProfile(name);
    setUser(updated);
    return updated;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: Boolean(user && token),
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
