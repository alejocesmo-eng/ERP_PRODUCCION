// src/AppLayout.jsx
import React from 'react';
import SidebarNavigation from './components/SidebarNavigation';
import { Outlet } from 'react-router-dom';
import { ProyectosProvider } from './context/ProyectosContext';

export default function AppLayout() {
  return (
    <ProyectosProvider>
      <div className="flex min-h-screen bg-slate-100 font-sans text-slate-900">
        <SidebarNavigation />
        <main className="flex-1 p-6 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </ProyectosProvider>
  );
}