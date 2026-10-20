---
tipo: pruebas
codigo: TC-PROD-001
nombre: Suite de Pruebas - Cronómetro Puesto CNC, Visor de Planos y Módulo Calidad
fase: F1-F3
cobertura: Puesto de Trabajo CNC, Auditoría de Tiempos, Calidad, Tratamiento Térmico y NC
estado: aprobado
autor: Analista Funcional / QA Lead
sistema_destino: ERP FastAPI + PostgreSQL
---

# TC-PROD-001: Suite de Pruebas Integrales (Puesto CNC y Calidad)

## 1. Alcance de las Pruebas
Esta suite valida las reglas de negocio críticas para las Fases 1 a 3 del ERP:
- Sincronización y conmutación de tiempos Setup $\rightarrow$ Mecanizado.
- Excepción por desviación de tiempo en Setup (>50%).
- Seguridad del visor temporal de planos (Tokens expirables).
- Registro metrológico y bloqueo de envíos a Tratamiento Térmico sin foto.
- Generación de No Conformidad (NC) y bloqueo de Cierre de OP.

---

## 2. Casos de Prueba Automatizables y Manuales

| ID Caso | Módulo | Precondición | Pasos de Ejecución | Resultado Esperado | Criterio de Éxito |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Puesto CNC | OP en estado `LIBERADA` asignada a operario. | 1. Hacer clic en `Iniciar Setup`. <br> 2. Verificar cronómetro en pantalla. | El estado pasa a `EN_SETUP`. El cronómetro inicia en `00:00:00`. Se registra el `TIMESTAMP` inicial en `registro_tiempos_produccion`. | Código HTTP 200 / Registro creado en BD PostgreSQL. |
| **TC-02** | Seguridad | OP en estado `EN_SETUP`. | 1. Consultar endpoint `/api/v1/planos/{token}`. <br> 2. Finalizar la OP en el puesto. <br> 3. Intentar acceder de nuevo a la URL del plano. | Mientras la OP está activa el plano es visible. Al finalizar la OP, el token expira y la API responde `403 Forbidden`. | El plano desaparece y no es accesible por URL directa. |
| **TC-03** | Excepción Setup | OP con tiempo de Setup estándar de 20 min. | 1. Acumular >30 min en Setup (150% del estándar). <br> 2. Presionar `Iniciar Mecanizado`. | El ERP despliega una ventana modal obligatoria solicitando la razón de la desviación antes de conmutar el estado. | No permite avanzar a Mecanizado sin seleccionar o ingresar justificación. |
| **TC-04** | Calidad / TT | Pieza en inspección que requiere Tratamiento Térmico. | 1. Intentar guardar el informe de TT sin adjuntar imagen. <br> 2. Cargar archivo de imagen y presionar `Enviar a Proveedor`. | Al faltar la foto, la API rechaza el registro (`422 Unprocessable Entity`). Con foto adjunta, registra la URL y dispara el envío de correo. | La tabla `informes_tratamiento_termico` almacena `ruta_fotografia` `NOT NULL`. |
| **TC-05** | No Conformidad | Pieza fuera de tolerancia dimensional. | 1. Marcar resultado como `NO_CONFORME`. <br> 2. Intentar ejecutar `Cierre de OP` desde el rol de Jefe de Operaciones. | El sistema rechaza el cierre e informa que la OP tiene una No Conformidad pendiente sin reposición de material. | Bloqueo en backend (`400 Bad Request`) si existe NC activa en la OP. |

---

## 3. Matriz de Datos de Prueba (Seed SQL para desarrollo)

```sql
-- Datos de prueba para ejecuciones de AntiGravity / Pytest
INSERT INTO usuarios (username, password_hash, nombre_completo, rol) 
VALUES ('operario1', 'hash_secure_123', 'Pedro Pérez', 'OPERARIO');

INSERT INTO estaciones_trabajo (codigo, nombre, area) 
VALUES ('CNC-01', 'Torno CNC Mazak', 'MECANIZADOS');

INSERT INTO ordenes_produccion (consecutivo_op, pedido_comercial_id, descripcion_pieza, cantidad, estado) 
VALUES ('4001001', 'PED-2026-050', 'Eje Principal Agitador Inox 316L', 5, 'LIBERADA');