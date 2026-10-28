---
id: REQ-PROD-001
titulo: Requisitos Operativos del Puesto de Trabajo Operario CNC
modulo: PM-03 Producción MES
iso_9001_2026: Cláusula 8.5.1 (Control de la Producción)
estado: APROBADO
---

# REQ-PROD-001 - Puesto de Trabajo Operario CNC

## 1. Alcance y Propósito
Define las reglas de interacción del operario en el puesto de trabajo (Torno/Fresadora CNC) mediante la Tablet MES, garantizando la captura en tiempo real de tiempos de *Setup*, producción, piezas $OK$ y piezas en *Scrap*[cite: 3, 6].

---

## 2. Requisitos Operativos en la Tablet MES

1. **Selección y Asignación de OP:**
   - El operario visualiza únicamente las Órdenes de Producción en estado `LIBERADA` asignadas a su centro de trabajo[cite: 3, 6].
   - **Quality Gate:** Si la OP no cumple la regla **RN-OP-004** (falta plano PDF o material en Almacén), la Tablet bloquea la opción "Iniciar Setup"[cite: 3, 6].

2. **Captura Transaccional de Tiempos:**
   - **Inicio de Setup / Alistamiento:** Dispara el cronómetro de preparación[cite: 3, 6].
   - **Inicio de Mecanizado:** Pasa automáticamente el estado a `EN_PROCESO`[cite: 3, 6].
   - **Cierre de Sub-lote:** El operario reporta la cantidad de piezas procesadas[cite: 3, 6].

3. **Notificación de Consumo y Backflushing:**
   - Al finalizar un sub-lote o turno, el sistema descuenta del Kárdex la materia prima exacta correspondiente al BOM y calcula el costo acumulado de la mano de obra/máquina (`ADR-004`)[cite: 3].

---

## 3. Enlaces de Operación
- [[Contexto_Puesto_CNC]]
- [[PM-04_Compras_MRP_Kardex]]
- [[Controles de calidad]]
- [[ADR-004_Costeo_Real_vs_Estandar_OP]]
- [[RN-OP-004_Bloqueo_Liberacion_OP]]

---
## Enlaces de Operación
- [[Contexto_Puesto_CNC]]
- [[PM-04_Compras_MRP_Kardex]]
- [[Controles de calidad]]