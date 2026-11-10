# Pendientes de seguridad

Pendientes detectados durante el paso 1 de permisos (exigir token en las rutas sin protección).
Cada pendiente se cierra con su propio cambio y se marca aquí con la fecha y el commit.

## PEND-SEG-001 — `/static/planos/*` se sirve sin autenticación

- **Estado:** abierto (registrado el 2026-11-09).
- **Dónde:** `04_CODIGO/BACKEND/app/main.py:51` monta `app.mount("/static", StaticFiles(directory="static"))`.
  Los PDF, STEP y DXF de `static/planos/` se descargan con su URL directa, sin token.
- **Impacto:** los planos del cliente (propiedad intelectual) y los archivos congelados de
  una OP liberada quedan accesibles para cualquiera que conozca o adivine el nombre del
  archivo. Proteger `GET /planos/descargar-cad` no basta mientras exista esta vía.
- **Quién la usa hoy:** el visor de planos (`VisorPlanoModal`, iframe con la URL del archivo),
  los enlaces `href={archivo_url}` de `ModalConsultaOP` y `ProduccionView`, y las columnas
  `archivo_*_url` y `planos_archivos.ruta`, que guardan rutas `/static/planos/...`.
- **Restricción:** un iframe o un enlace no envían la cabecera `Authorization`; la solución
  no puede ser solo exigir Bearer en `/static`.
- **Opciones para decidir:**
  1. Servir los planos solo por rutas de la API: token temporal firmado para el visor
     (como `/planos/visor-seguro`) y descarga con Bearer para STEP/DXF; retirar
     `static/planos` del montaje público.
  2. URLs firmadas con caducidad para cada archivo, validadas por un middleware sobre `/static/planos`.
- **Relacionado:** ruta `/planos/visor-seguro`, que ya usa token temporal y queda fuera del
  paso 1 a propósito.

## PEND-SEG-002 — El rol se sigue leyendo del token: un cambio de rol no aplica hasta que expire

- **Estado:** abierto (registrado el 2026-11-10). Aprobado dejarlo para después.
- **Dónde:** `04_CODIGO/BACKEND/app/api/deps.py`, `obtener_usuario_actual`. Desde `b2984e6`
  revisa en cada petición que el usuario del token exista y no esté desactivado, pero
  devuelve el `rol` que viene dentro del JWT, no el `usuarios.id_rol` actual.
- **Impacto:** si se le cambia el rol a un usuario (por ejemplo, se le quita ADMIN), su token
  conserva el rol anterior hasta que expira: `ACCESS_TOKEN_EXPIRE_MINUTES`, 480 min por
  defecto (`app/core/config.py:21`). Desactivarlo sí corta el acceso de inmediato.
- **Solución propuesta:** en la misma consulta de `usuario_vigente`, leer `id_rol` y usarlo
  en lugar del rol del token (o rechazar con 401 si no coinciden, para forzar un nuevo
  login). Probarlo con las pruebas marcadas `usuario_real`.
- **Relacionado:** PEND-SEG-003 (el frontend debe reaccionar al 401 que esto produzca).

## PEND-SEG-003 — El frontend no maneja el 401 ni la expiración del token

- **Estado:** abierto (registrado el 2026-11-10). Aprobado dejarlo para después.
- **Dónde:**
  - `04_CODIGO/FRONTEND/src/services/api.js`: solo tiene interceptor de petición (agrega el
    token); no hay interceptor de respuesta para el 401.
  - `components/ProtectedRoute.jsx:5-8` y `routes.jsx:27-33`: solo comprueban que exista
    `sgi_token` en `localStorage`; no revisan la expiración ni la firma.
  - Las vistas con `fetch` propio (`GanttCargaMaquinasView`, `MantenimientoPlantaView`,
    `CalidadRncCapaView`, `CostosLiquidacionOpView`) tampoco tratan el 401.
- **Impacto:** desde `b2984e6` un usuario desactivado o eliminado recibe 401 en cada
  petición, y lo mismo pasa cuando el token expira. La aplicación muestra errores en cada
  pantalla en lugar de cerrar la sesión y volver al login; con un token vencido, `/login`
  redirige a la aplicación porque el token sigue en `localStorage`.
- **Solución propuesta:** interceptor de respuesta en `api.js` (y en el `fetch` común de esas
  vistas) que ante un 401 borre `sgi_token` y `sgi_sesion` y lleve a `/login` con un aviso
  ("Su sesión expiró o el usuario fue desactivado"); `ProtectedRoute` que descarte un token
  con `exp` vencido.
