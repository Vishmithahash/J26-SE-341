import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { AccessDeniedPage } from '../../pages/AccessDeniedPage';

export const ProtectedRoute = ({
  children,
  requiredRole,
}) => {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950"
        role="status"
        aria-label="Validating session"
      >
        <div className="flex flex-col items-center gap-3 text-slate-500">
          <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-medium tracking-wide">Validating session...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    // Only pass internal safe return path (prevent protocol-relative open redirects)
    const rawPath = `${location.pathname}${location.search}`;
    const safePath =
      rawPath.startsWith('/') && !rawPath.startsWith('//') && !rawPath.includes('\\')
        ? rawPath
        : '/';
    return <Navigate to="/sign-in" state={{ from: safePath }} replace />;
  }

  // Unknown roles must fail closed
  if (user.role !== 'ADMIN' && user.role !== 'USER') {
    return <AccessDeniedPage />;
  }

  // Check required role
  if (requiredRole && user.role !== requiredRole) {
    return <AccessDeniedPage />;
  }

  return <>{children}</>;
};
