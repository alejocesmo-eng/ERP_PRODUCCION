# DIRECTIVAS DE DESARROLLO Y GOBERNANZA TÉCNICA (SGI-ERP)

## 1. PRINCIPIO FUNDAMENTAL DE NO REGRESIÓN

- QUEDA ESTRICTAMENTE PROHIBIDO modificar o refactorizar archivos de autenticación, seguridad, middlewares o modelos base compartidos a menos que la instrucción lo pida de forma explícita.
- Lo que ya funciona y está probado debe permanecer 100% operativo tras cada intervención.
- Antes de renombrar o quitar un atributo en `app/db/models.py`, revisa todos los archivos en `app/api/v1/` que lo importan para evitar romper endpoints en cascada.

## 2. MODULARIZACIÓN Y EDICIÓN QUIRÚRGICA EN FRONTEND

- Prohibido inflar archivos extensos (ej. `ProyectosView.jsx`) con cientos de líneas nuevas de código embebido.
- Todo nuevo flujo (como Cotizaciones, Visores CAD o Canvas MES) debe construirse como componentes independientes (`.jsx`) dentro de su carpeta correspondiente e importarse limpiamente.
- Antes de aplicar reemplazos en archivos de React, lee siempre las líneas exactas para garantizar el balance correcto de etiquetas JSX (cierres de `<div>`, condicionales `{...}` y fragmentos).

## 3. GOVERNANZA DE NEGOCIO Y ESTÁNDAR VISUAL

- 100% Español técnico profesional en etiquetas, tablas, tooltips y mensajes de error.
- Prohibición explícita de nomenclaturas de marcas de ERP comercial externas. Usar terminología neutra ("Sistema Central", "ERP Planta").
- UI de alta densidad: Tailwind CSS con `text-xs`, paleta institucional (slate, emerald, amber, purple, blue) y badges semánticos.

## 4. INTEGRIDAD DE DATOS Y PRUEBAS

- Cualquier adición a la base de datos debe reflejarse en `cargar_semilla.py` con registros de prueba funcionales para cada rol operativo (Jefe de Ingeniería, Dibujante, Líder de Producción, Operario).
