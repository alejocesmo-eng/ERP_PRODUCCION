---
id: ADR-006
titulo: Sin credenciales de contingencia en el código; recuperación del acceso administrativo solo por script local con getpass
estado: propuesto
fecha: 2026-10-29
autor: arquitecto-datos (Oficina de Agentes IA)
ot: OT-2026-002
iso_9001_2026: Cláusulas 7.1.3, 7.5.3
relacionados: ["[[OT-2026-002]]", "[[OT-2026-001]]", "[[ADR-005_Secretos_Variables_Entorno_Obligatorias]]", "[[GOB-EST-001]]", "[[CONSTITUCION_OFICINA_IA]]"]
---

# ADR-006: Sin credenciales de contingencia en el código; recuperación del acceso administrativo por script local

> Este ADR no contiene ni cita ningún correo, clave ni hash real o fijo. Se refieren por `archivo:línea` en la OT-2026-002.

## 1. Contexto
- `04_CODIGO/BACKEND/app/api/v1/auth.py` emitía un token con rol `ADMIN` **sin consultar la base de datos** si se usaban un correo fijo y una de tres claves fijas escritas en el código, y además reescribía en silencio el `password_hash` de ese usuario con `db.commit()` dentro del login. `app/routes/auth.py` (no montado) tenía una copia del mismo acceso.
- Esos valores están publicados en el remoto GitHub (OT-2026-001, G1 P-2).
- La justificación original era "permitir el acceso aunque la semilla no se haya cargado". No había ningún otro mecanismo para que un administrador fijara o recuperara su clave.
- `cargar_semilla.py` sobrescribe `password_hash` de todos los usuarios con una clave común cada vez que se ejecuta (`_upsert`).

## 2. Decisión
1. **Ninguna credencial de contingencia en el código.** No existen usuarios, claves, hashes ni rutas de login que omitan la base de datos. El login (`POST /api/v1/auth/token`) solo autentica contra `usuarios.password_hash` con bcrypt (`app/core/security.py`).
2. **El login es de solo lectura.** Ninguna rama del login asigna `password_hash` ni hace `commit`.
3. **Recuperación del acceso administrativo:** solo con el script local versionado `04_CODIGO/BACKEND/fijar_clave_admin.py`, ejecutado por Dirección (o por quien designe) en una consola interactiva. Pide el correo y la clave con `getpass`, sin eco y nunca como argumento. Solo actúa sobre un usuario existente con rol `ADMIN`, cambia únicamente `password_hash` y no imprime el correo, la clave ni el hash. Requiere acceso local a la base de datos (el `.env` del backend), que es el mismo nivel de confianza que ya exige administrar la base.
4. **Verificación previa al retiro de cualquier acceso:** antes de quitar una vía de acceso administrativo se ejecuta la verificación de solo lectura `04_CODIGO/BACKEND/verificar_admin_ca0.py`. Debe confirmar que al menos un ADMIN activo tiene un hash bcrypt propio, distinto de cualquier valor publicado.
5. **Prohibido ejecutar `cargar_semilla.py` sobre la base de datos real**, incluido para "recuperar" el acceso.

## 3. Consecuencias
- Positivas: desaparece una vía de acceso con claves públicas. El login deja de modificar datos. La recuperación queda documentada, es auditable y no depende de secretos en el código.
- Negativas o a tener en cuenta:
  - Si no hay ningún ADMIN con clave conocida por Dirección **y** nadie tiene acceso local a la BD, no hay forma de recuperar el acceso desde la aplicación. Esto es intencional.
  - Los tokens ya emitidos siguen siendo válidos hasta su expiración, porque `deps.py` solo valida la firma. Su invalidación depende de la rotación de `SECRET_KEY` ([[ADR-005_Secretos_Variables_Entorno_Obligatorias]]).
  - Mientras la semilla siga escribiendo una clave común, cualquier BD sembrada tiene usuarios con clave conocida. Lo corrige la OT P0 de la clave común de la semilla.
  - El login no comprueba `usuarios.activo`. Desactivar un ADMIN no le quita el acceso hasta que se haga la OT P1 correspondiente.
- Fuera de este ADR: endpoint o pantalla de cambio de contraseña, política de contraseñas para todos los usuarios, revocación de tokens y bloqueo por intentos fallidos.

## 4. Alternativas descartadas
- **Mantener un administrador de contingencia con clave en variable de entorno:** sigue siendo una vía que omite la BD y, si la variable se filtra, da acceso total sin que quede rastro en `usuarios`.
- **Recuperar con la semilla:** reescribe las claves de todos los usuarios con una clave publicada.
- **`UPDATE` manual con `psql`:** obliga a generar el hash bcrypt fuera de la aplicación y deja el hash en el historial de la consola. El script usa la misma función `get_password_hash` que la aplicación.
- **Endpoint de cambio de contraseña:** necesario a medio plazo, pero no resuelve la recuperación cuando nadie puede iniciar sesión. Queda en una OT aparte.

## 5. Estado
Propuesto. Se aprueba con el G2 de la OT-2026-002 y pasa a `aprobado` en el G3.
