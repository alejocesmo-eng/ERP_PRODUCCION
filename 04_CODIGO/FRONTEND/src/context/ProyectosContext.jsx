// src/context/ProyectosContext.jsx
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import API from '../services/api';

const ProyectosContext = createContext();

export const ProyectosProvider = ({ children }) => {
  const [proyectos, setProyectos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const cargarProyectosGlobal = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await API.get('/proyectos/');
      const data = Array.isArray(res.data) ? res.data : [];
      setProyectos(data);
    } catch (err) {
      console.error("Error al sincronizar proyectos en ProyectosContext:", err);
      setError(err.response?.data?.detail || "Error al conectar con el servidor.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    cargarProyectosGlobal();
  }, [cargarProyectosGlobal]);

  return (
    <ProyectosContext.Provider
      value={{
        proyectos,
        loading,
        error,
        recargarProyectos: cargarProyectosGlobal
      }}
    >
      {children}
    </ProyectosContext.Provider>
  );
};

export const useProyectos = () => {
  const context = useContext(ProyectosContext);
  if (!context) {
    throw new Error("useProyectos debe utilizarse dentro de un ProyectosProvider");
  }
  return context;
};

export default ProyectosContext;