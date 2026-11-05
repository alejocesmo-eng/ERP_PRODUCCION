---
id: ADR-005
titulo: Secretos de infraestructura solo por variables de entorno obligatorias y claves JWT separadas para sesión y planos
estado: propuesto
fecha: 2026-10-29
autor: arquitecto-datos (Oficina de Agentes IA)
ot: OT-2026-001
iso_9001_2026: Cláusulas 7.1.3, 7.5.3
relacionados: ["[[OT-2026-001]]", "[[GOB-EST-001]]", "[[Estándares de desarrollo]]", "[[CONSTITUCION_OFICINA_IA]]"]
---

# ADR-005: Secretos de infraestructura solo por variables de entorno obligatorias

> Este ADR no contiene ni cita ningún valor secreto. Los nombres de variable son públicos; sus valores viven solo en archivos `.env` locales no versionados.

## 1. Contexto
- `docker-compose.yml`, `04_CODIGO/BACKEND/app/core/config.py`, `04_CODIGO/BACKEND/app/api/v1/planos.py` y la nota "Estándares de desarrollo" contenían usuario/clave de PostgreSQL y claves de firma JWT en texto plano o como valores por defecto codificados.
- Esos archivos (y `04_CODIGO/BACKEND/.env`, versionado por error desde el commit inicial) están publicados en el remoto `origin` de GitHub. Las credenciales se consideran expuestas.
- Con valores por defecto en el código, un despliegue sin configuración arranca "en silencio" con una clave conocida públicamente: cualquiera podría firmar tokens de sesión válidos.
- Existían dos claves JWT: `SECRET_KEY` (sesión; `app/core/security.py`, `app/api/deps.py`, `app/core/deps.py`) y `JWT_SECRET_KEY_PLANOS` (enlaces temporales del visor de planos; `app/api/v1/planos.py`). El módulo `app/api/v1/endpoints/planos.py` firma con `SECRET_KEY`, pero **no está montado** en `app/main.py` (código muerto).

## 2. Decisión
1. **Sin valores por defecto para secretos.** `DATABASE_URL`, `SECRET_KEY` y `JWT_SECRET_KEY_PLANOS` son obligatorias. Si faltan o están vacías, el backend **no arranca** y el error nombra la variable faltante, sin mostrar ningún valor. `ALGORITHM` y `ACCESS_TOKEN_EXPIRE_MINUTES` no son secretos y conservan sus valores por defecto actuales.
2. **Compose falla si falta una variable.** `docker-compose.yml` usa la interpolación `${VAR:?mensaje}`; sin `.env`, `docker compose` se detiene con un mensaje que nombra la variable.
3. **Dos archivos `.env` locales, no versionados**, cada uno con su plantilla versionada `.env.example`:
   - raíz del repositorio: lo consume `docker compose` (`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `SECRET_KEY`, `JWT_SECRET_KEY_PLANOS`). La `DATABASE_URL` del servicio `backend` se construye en el compose desde `POSTGRES_*` con host `db`.
   - `04_CODIGO/BACKEND/`: lo consume `load_dotenv()` del backend sin Docker (`DATABASE_URL` con host `localhost`, `SECRET_KEY`, `JWT_SECRET_KEY_PLANOS`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`).
4. **Se mantienen dos claves JWT separadas** (resuelve C-4 de la OT-2026-001): `SECRET_KEY` firma sesiones; `JWT_SECRET_KEY_PLANOS` firma los enlaces temporales del visor de planos. No se unifican: separar las claves limita el alcance de una filtración y no cambia el comportamiento actual. Los nombres canónicos son exactamente esos (se descarta `JWT_SECRET_KEY`, que solo existía en la nota de la bóveda).
5. Las claves se generan fuera del repositorio, con al menos 32 bytes aleatorios (por ejemplo, `secrets.token_hex(32)`), son distintas entre sí y distintas de cualquier valor publicado antes.

## 3. Consecuencias
- Positivas: ningún secreto en archivos versionados; los errores de configuración son explícitos; se cumplen GOB-EST-001 §2.2 y AGENTS.md §8.
- Negativas o a tener en cuenta:
  - Todo módulo que importe `app.core.config` (directa o indirectamente: `app.db.database`, `cargar_semilla.py`, `verificar_bd.py`, `migrar_mantenimientos.py`, toda la suite de pruebas) necesita las variables definidas o un `.env` localizable.
  - `app/api/v1/planos.py` depende de que `app.core.config` (vía `app.db.database`) haya ejecutado `load_dotenv()` antes de leer `JWT_SECRET_KEY_PLANOS`; hoy se cumple por el orden de importación.
  - Rotar `SECRET_KEY` invalida todas las sesiones activas; rotar `JWT_SECRET_KEY_PLANOS` invalida los enlaces de planos vigentes.
  - La clave de PostgreSQL se usa dentro de una URL: debe ser alfanumérica (hexadecimal) o ir codificada en URL.
- Fuera de este ADR: migración a `pydantic-settings`, gestión de secretos en producción, limpieza del historial de git, credenciales de aplicación (`auth.py`, semilla).

## 4. Alternativas descartadas
- Valor de desarrollo generado al vuelo si falta la clave: oculta errores de configuración e invalida sesiones en cada reinicio.
- Una sola clave JWT para sesión y planos: menos variables, pero un enlace de plano filtrado quedaría firmado con la clave de sesión.
- Un único `.env` en la raíz para ambos modos: la `DATABASE_URL` no sirve a la vez para `db` (Docker) y `localhost` (backend local).

## 5. Estado
Propuesto. Se aprueba junto con el G2 de la OT-2026-001 y pasa a `aprobado` en el G3.
