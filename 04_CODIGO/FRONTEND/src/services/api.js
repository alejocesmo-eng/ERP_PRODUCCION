// src/services/api.js
import axios from 'axios';

// URL origen del backend servidor de archivos estáticos
export const API_ORIGIN = 'http://localhost:8000';

// Instancia de Axios configurada para la versión API v1
const API = axios.create({
  baseURL: `${API_ORIGIN}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
});

API.interceptors.request.use((config) => {
  const token = localStorage.getItem('sgi_token')?.trim();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default API;