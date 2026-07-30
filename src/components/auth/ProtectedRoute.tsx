import React, { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { isTokenExpired } from '../../services/jwt';

interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: string[];
}

function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_role');
  localStorage.removeItem('username');
  localStorage.removeItem('user_email');
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  // Re-evaluated on window focus / cross-tab storage changes so a token that
  // expires or is cleared in another tab doesn't leave this tab rendering
  // protected content until the next full navigation.
  const [, forceRecheck] = useState(0);

  useEffect(() => {
    const recheck = () => forceRecheck((n) => n + 1);
    window.addEventListener('focus', recheck);
    window.addEventListener('storage', recheck);
    return () => {
      window.removeEventListener('focus', recheck);
      window.removeEventListener('storage', recheck);
    };
  }, []);

  const token = localStorage.getItem('access_token');
  const role = localStorage.getItem('user_role')?.toLowerCase();

  // 1. Not authenticated, a legacy mock token, or an expired JWT → login
  const expired = token ? isTokenExpired(token) : true;
  if (!token || token === 'mock-jwt-token' || expired) {
    clearSession();
    return <Navigate to="/login" replace />;
  }

  // 2. If role is restricted, verify check
  if (allowedRoles && (!role || !allowedRoles.includes(role))) {
    // If user role is not authorized, redirect to dashboard or home
    return <Navigate to="/dashboard" replace />;
  }

  // 3. Render children
  return <>{children}</>;
};
