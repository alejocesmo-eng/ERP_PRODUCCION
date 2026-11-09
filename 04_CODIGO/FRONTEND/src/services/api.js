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

// Catálogo de stock de producto terminado (solo lectura, no reserva unidades).
// Contrato OT-2026-008 sección 2.4: GET /ventas/stock-pt?q=&solo_con_saldo=&limit=&offset=
export const consultarStockPT = ({ q = '', soloConSaldo = true, limit = 50, offset = 0 } = {}) =>
  API.get('/ventas/stock-pt', {
    params: { q: q || undefined, solo_con_saldo: soloConSaldo, limit, offset },
  });

// Convierte el 400 STOCK_INSUFICIENTE (detail objeto) en un texto para el usuario.
// Devuelve null si el detail no es de ese tipo, para que el llamador use su lógica habitual.
export const mensajeStockInsuficiente = (detail) => {
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  if (detail.codigo !== 'STOCK_INSUFICIENTE') return detail.mensaje || null;
  const unidad = detail.unidad || 'und';
  return `Cantidad mayor al disponible para venta${detail.sku ? ` (${detail.sku})` : ''}. Máximo: ${detail.disponible ?? 0} ${unidad}. Reduzca la cantidad o consulte a Almacén.`;
};

// Texto legible del error de una petición: detail de texto (400/403/409) o lista de
// validación de FastAPI (422: [{loc, msg}]) con el nombre del campo, sin la ruta body->.
export const mensajeError = (fallo, porDefecto) => {
  const detail = fallo?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        const campo = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : '';
        return campo && campo !== 'body' ? `${campo}: ${item?.msg || 'valor inválido'}` : item?.msg || 'valor inválido';
      })
      .join(' · ');
  }
  return mensajeStockInsuficiente(detail) || porDefecto;
};

export default API;