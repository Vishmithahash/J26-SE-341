import React, { createContext, useContext, useEffect, useState } from 'react';
import type { DisplayDensity, ThemeMode } from '../types/auth';

interface ThemeContextType {
  mode: ThemeMode;
  resolvedTheme: 'light' | 'dark';
  setMode: (mode: ThemeMode) => void;
  density: DisplayDensity;
  setDensity: (density: DisplayDensity) => void;
}

const THEME_KEY = 'qa_theme_mode';
const DENSITY_KEY = 'qa_density_pref';

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      if (saved === 'light' || saved === 'dark' || saved === 'system') {
        return saved;
      }
    } catch {
      // Fallback if localStorage is inaccessible
    }
    return 'system';
  });

  const [density, setDensityState] = useState<DisplayDensity>(() => {
    try {
      const saved = localStorage.getItem(DENSITY_KEY);
      return saved === 'compact' ? 'compact' : 'comfortable';
    } catch {
      return 'comfortable';
    }
  });

  const [systemIsDark, setSystemIsDark] = useState<boolean>(() => {
    return (
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: dark)').matches
    );
  });

  // Listen to OS-level theme changes when in system mode
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => setSystemIsDark(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  const resolvedTheme = mode === 'system' ? (systemIsDark ? 'dark' : 'light') : mode;

  // Synchronize dark class to html element
  useEffect(() => {
    const root = document.documentElement;
    if (resolvedTheme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [resolvedTheme]);

  // Synchronize data-density attribute to html element so compact density affects the layout consistently
  useEffect(() => {
    document.documentElement.setAttribute('data-density', density);
  }, [density]);

  const setMode = (newMode: ThemeMode) => {
    setModeState(newMode);
    try {
      localStorage.setItem(THEME_KEY, newMode);
    } catch {
      // Ignore storage errors
    }
  };

  const setDensity = (newDensity: DisplayDensity) => {
    setDensityState(newDensity);
    try {
      localStorage.setItem(DENSITY_KEY, newDensity);
    } catch {
      // Ignore storage errors
    }
  };

  return (
    <ThemeContext.Provider value={{ mode, resolvedTheme, setMode, density, setDensity }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
