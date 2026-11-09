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
