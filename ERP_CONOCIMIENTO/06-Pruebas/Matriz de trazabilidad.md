---
tipo: matriz-pruebas
estado: borrador
---
---
tipo: trazabilidad
codigo: TRZ-SIST-001
nombre: Matriz General de Trazabilidad Requisitos - Módulos - SQL - QA
fase: F1-F3
estado: aprobado
version: 1.0
autor: Analista Funcional / Arquitecto de Software
sistema_destino: ERP FastAPI + PostgreSQL
---

# TRZ-SIST-001: Matriz General de Trazabilidad Requisitos - Módulos - SQL - QA

## 1. Propósito
Garantizar la cobertura integral de la solución conectando cada Requisito de Negocio con su Proceso asociado, la tabla en la Base de Datos PostgreSQL, el Endpoint API en FastAPI y el Caso de Prueba (QA).

---

## 2. Matriz de Trazabilidad Cruzada

| ID Requisito | Proceso | Descripción Funcional | Tabla PostgreSQL | Endpoint API (FastAPI) | Caso de Prueba |
| :---: | :---: | :--- | :--- | :--- | :---: |
| **REQ-DIS-001** | `PROC-PROD-001` | Estimación de tiempo por Líder y medición cronometrada al pasar a `EN_DISENO`. | `tiempos_diseno`, `ordenes_produccion` | `POST /api/v1/diseno/asignar`<br>`PUT /api/v1/diseno/iniciar` | `TC-DIS-001` |
| **REQ-PROD-001** | `PROC-PROD-001` | Visualización de OP y cronómetro de Setup/Mecanizado en Puesto CNC. | `registro_tiempos_produccion` | `WS /api/v1/ws/puesto-trabajo/{estacion_id}` | `TC-01` |
| **REQ-PROD-002** | `PROC-PROD-001` | Visor temporal de planos PDF con tokens de acceso expirable (TTL). | `planos_op` | `GET /api/v1/planos/token/{id}` | `TC-02` |
| **REQ-PROD-003** | `PROC-PROD-001` | Excepción por desviación de tiempo en Setup (>50%) con modal de justificación. | `registro_tiempos_produccion` | `POST /api/v1/produccion/mecanizado/iniciar` | `TC-03` |
| **REQ-CAL-001** | `PRO-CAL-001` | Control metrológico con micrómetros, calibradores pie de rey y patrones. | `inspecciones_calidad` | `POST /api/v1/calidad/inspeccion` | `TC-04` |
| **REQ-CAL-002** | `PRO-CAL-001` | Registro fotográfico obligatorio y envío de email para Tratamiento Térmico. | `informes_tratamiento_termico` | `POST /api/v1/calidad/tratamiento-termico` | `TC-04` |
| **REQ-CAL-003** | `PRO-CAL-001` | Generación de No Conformidades (NC) y solicitud automática de nuevo material. | `no_conformidades` | `POST /api/v1/calidad/no-conformidad` | `TC-05` |

---

## 3. Preguntas por Validar

### Responsables y suplencias:
- [PENDIENTE: Definir si se requerirá un módulo de auditoría de logs que registre cuando una orden cambie de estado manualmente por un Administrador.]

### Aprobaciones:
- [PENDIENTE: Confirmar si las pruebas unitarias de trazabilidad se ejecutarán de forma automatizada en el pipeline de CI/CD.]

---
# Matriz de trazabilidad requisito-prueba

| ID requisito | Proceso/módulo | Criterio de aceptación | Prueba | Evidencia/resultado | Estado |
|---|---|---|---|---|---|
| REQ-XXX | Por definir | Por definir | Por definir | Pendiente | Borrador |
