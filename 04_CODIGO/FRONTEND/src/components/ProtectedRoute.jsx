import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';

export const ProtectedRoute = () => {
  const token = localStorage.getItem('sgi_token')?.trim();

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};