---
id: ARQ-ERD-002
titulo: Esquema Extendido PostgreSQL - Módulos de Calidad, Costos y Lotes (Estándar SAP)
estado: APROBADO
fecha: 2026-10-21
iso_9001_2026: Clausulas 8.1, 8.4, 8.5, 9.1
---

# [[Modelo_ERD_PostgreSQL|Modelo Entidad-Relación Extendido SGI-ERP]]

## 1. Entidades de Trazabilidad Industrial (Estándar SAP S/4HANA)

### A. Gestión de Lotes y Calidad (`lotes` / `certificados`)
- `id_lote` (UUID, PK)
- `numero_colada` (VARCHAR, Unique) - Certificado 3.1 del fabricante.
- `estado_calidad` (ENUM: 'CUARENTENA', 'LIBERADO', 'RECHAZADO')
- `archivo_certificado_pdf` (VARCHAR)

### B. Centros de Trabajo y Tarifas (`centros_trabajo`)
- `id_centro` (UUID, PK)
- `codigo_centro` (VARCHAR) - Ej. 'CNC-TORNO-01', 'CNC-FRESADORA-02'
- `tarifa_hora_mecanizado` (NUMERIC)
- `tarifa_hora_setup` (NUMERIC)

### C. Auditoría e Inmutabilidad (`auditoria_sistema`)
- `id_auditoria` (UUID, PK)
- `tabla_afectada` (VARCHAR)
- `id_registro` (VARCHAR)
- `estado_anterior` (JSONB)
- `estado_nuevo` (JSONB)
- `usuario_id` (UUID)
- `fecha_hora` (TIMESTAMP WITH TIME ZONE)

---

## 2. Diagrama de Relaciones para Cierre de OP y Costeo Real

$$\text{Centro de Trabajo} \xrightarrow{\text{Tarifa/Hora}} \text{SubLote (MES)} \xrightarrow{\text{Horas Reales}} \text{Costo MO/Máquina OP}$$

$$\text{Lote (Colada 3.1)} \xrightarrow{\text{Certificado OK}} \text{Almacén} \xrightarrow{\text{Consumo BOM}} \text{Costo MP OP}$$

## Relaciones de Arquitectura
- [[Mapeo_Modulos_SGI_vs_SAP]]
- [[ADR-004_Costeo_Real_vs_Estandar_OP]]
- [[PM-04_Compras_MRP_Kardex]]