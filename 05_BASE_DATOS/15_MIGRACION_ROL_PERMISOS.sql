-- 15_MIGRACION_ROL_PERMISOS.sql
-- Tabla de asignacion de permisos a roles. La usa 02_DATOS_INICIALES.sql (seccion 3)
-- y la refleja el modelo RolPermiso de app/db/models.py.
-- Aditiva e idempotente, sin perdida de datos. NO la ejecuta ningun agente:
-- la aplica Direccion con respaldo previo de sgi_db y ensayo en BD de prueba.
-- Requiere las tablas roles y permisos ya creadas.
-- Reversion: 15_REVERSION_ROL_PERMISOS.sql

BEGIN;

CREATE TABLE IF NOT EXISTS rol_permisos (
    id_rol VARCHAR(50) NOT NULL REFERENCES roles(id_rol),
    id_permiso VARCHAR(100) NOT NULL REFERENCES permisos(id_permiso),
    PRIMARY KEY (id_rol, id_permiso)
);

COMMIT;
