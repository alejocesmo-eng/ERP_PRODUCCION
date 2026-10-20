# 02 — MATRIZ DE RESPONSABILIDADES Y CONTROL DE ACCESO (ISO 9001:2026)

**Versión:** 2.0 (Consolidada y Aprobada)  
**Estado:** Documento Maestro de Gobierno del SGI  
**Documento:** 02_MATRIZ_DE_RESPONSABILIDADES.md  

---

## 1. OBJETIVO Y ALCANCE

Definir la estructura de responsabilidades (Matriz RACI), autoridad y permisos para cada etapa del proceso **Proyecto / Pedido → Producción $\rightarrow$ Entrega**[cite: 12, 14]. 

Este documento sirve como especificación directa para:
* Configuración de roles y permisos en la base de datos (PostgreSQL) y Backend (FastAPI - RBAC)[cite: 7, 14].
* Control de estados e inmutabilidad de documentos en las vistas (React)[cite: 12, 14].
* Reglas de negocio bloqueantes y flujos de aprobación[cite: 12, 14].
* Trazabilidad y registros de auditoría SGI[cite: 12, 14].

---

## 2. ÁREAS Y ROLES INVOLUCRADOS

| Área / Rol | Responsabilidad Principal en el SGI |
|---|---|
| **Ventas / Comercial** | Registrar la información comercial del proyecto, cliente, sede/ubicación, requisitos y fecha comprometida[cite: 12]. |
| **Diseño e Ingeniería** | Evaluar el proyecto, elaborar planos, gestionar revisiones, definir el BOM (materiales) y generar solicitudes a Compras[cite: 12]. |
| **Calidad (Transversal)** | Supervisar de forma transversal, auditar requisitos, validar el expediente técnico y **emitir/liberar formalmente la OP**[cite: 12]. |
| **Almacén / Materiales** | Recepcionar compras con factura, gestionar inventarios (incluyendo retales), reservar el 100% de materia prima y despachar[cite: 12]. |
| **Producción** | Ejecutar la fabricación en planta usando únicamente planos autorizados vigentes, consumir materiales y reportar avance[cite: 12]. |
| **Metrología / Inspección**| Inspeccionar producto terminado con instrumentos calibrados y emitir certificados de conformidad[cite: 12]. |
| **Sistema (Automático)** | Controlar reglas de negocio, validar condiciones de estado, impedir acciones no autorizadas y registrar auditoría[cite: 12]. |

---

## 3. MATRIZ DE RESPONSABILIDADES RACI POR ETAPA OPERATIVA

**Leyenda RACI:**
* **R (Responsible / Ejecutor):** Quien realiza la actividad[cite: 7].
* **A (Accountable / Aprobador):** Quien asume la responsabilidad final y aprueba el cambio de estado[cite: 7].
* **C (Consulted / Consultado):** Especialista o área consultada previamente[cite: 7].
* **I (Informed / Informado):** Rol que recibe notificación automática[cite: 7].

| Etapa del Proceso | Ventas | Diseño | Calidad | Almacén | Producción | Metrología | Sistema |
|---|:---:|:---: |:---:|:---:|:---:|:---:|:---:|
| **1. Crear / Registrar Proyecto o Pedido** | **R / A** | I | I | I | I | I | **R** |
| **2. Consultar Expediente del Proyecto** | **R** | **R** | **R** | **R** | **R** | **R** | **R** |
| **3. Evaluar y Diseñar Producto** | I | **R / A** | C | I | I | I | **R** |
| **4. Definir BOM y Solicitar Material a Compras**| I | **R / A** | C | C | I | I | **R** |
| **5. Consultar y Seleccionar Retales** | I | **R** | I | **R** | I | I | **R** |
| **6. Cargar y Gestionar Revisiones de Planos** | I | **R / A** | C | I | I | I | **R** |
| **7. Validar Paquete Técnico Pre-OP** | I | C | **R / A** | I | I | I | **R** |
| **8. Emitir Orden de Producción (Generar OP)** | I | C | **R / A** | I | I | I | **R** |
| **9. Recepcionar Compra y Adjuntar Factura** | I | I | C | **R / A** | I | I | **R** |
| **10. Confirmar Reserva de Stock 100% (RN-OP-004)**| I | I | C | **R / A** | I | I | **R** |
| **11. Liberar OP a Producción** | I | I | **R / A** | C | I | I | **R** |
| **12. Entregar Material / Entregas Parciales** | I | I | I | **R / A** | **R** | I | **R** |
| **13. Iniciar / Ejecutar Fabricación en Planta**| I | I | I | C | **R / A** | I | **R** |
| **14. Registrar Consumo y Cantidades Producidas**| I | I | I | C | **R / A** | I | **R** |
| **15. Inspección Dimensional y Calibración** | I | I | C | I | I | **R / A** | **R** |
| **16. Consultar Trazabilidad Auditora Completa** | Según Rol| **R** | **R** | **R** | **R** | **R** | **R** |

---

## 4. MATRIZ DE AUTORIZACIÓN: ROL + PROCESO + ACCIÓN + ESTADO

Los permisos no se asignan de forma genérica. Se evalúan mediante la combinación estricta de **ROL + PROCESO + ACCIÓN + ESTADO DEL DOCUMENTO**[cite: 12].

               PERMISO DE EJECUCIÓN
                      │
┌───────────────────────┼───────────────────────┐
▼                       ▼                       ▼
ROL DEL USUARIO       PROCESO SGI             ESTADO ACTUAL
(Ej. Diseñador)    (Ej. Ingeniería)         (Ej. BORRADOR)


| Rol ERP | Proceso | Acción Permitida | Estado Requerido | Restricción / Condición de Bloqueo |
|---|---|---|---|---|
| `VENTAS` | Comercial | Crear y Modificar Proyecto/Pedido | `BORRADOR` | No puede editar información técnica de Ingeniería ni emitir OPs. |
| `VENTAS` | Comercial | Confirmar Requisitos de Proyecto | `BORRADOR` | Requiere cliente, fecha comprometida y especificaciones completas (`RN-VT-001`). |
| `DISEÑO` | Ingeniería | Cargar Plano, Definir BOM y Solicitar Insumo | `CONFIRMADO` / `BORRADOR` | Puede editar libremente mientras la OP o el plano no estén aprobados/liberados. |
| `DISEÑO` | Ingeniería | Aprobar Nueva Revisión de Plano | `EN_REVISION` | La aprobación de `REV-02` marca automáticamente `REV-01` como `OBSOLETO`. |
| `DISEÑO` | Ingeniería | Modificar Documentación Aprobada | `LIBERADA` / `EN_PROCESO` | **BLOQUEADO:** Una vez liberada la OP, Diseño sólo tiene acceso de Lectura. |
| `CALIDAD` | Control OP | Validar Checklist Técnico y Generar OP | `EN_REVISION_CALIDAD` | Exclusividad del rol Calidad. No puede modificar dimensiones técnicas. |
| `CALIDAD` | Control OP | Liberar OP a Producción | `APROBADA` | **Bloqueo `RN-OP-004`:** Inhabilitado si la reserva de stock es < 100%. |
| `ALMACEN` | Inventarios | Registrar Entrada de Compra + Factura | Cualquier Estado | Debe cotarse contra número de solicitud de compra. |
| `ALMACEN` | Inventarios | Entregar Material (Total o Parcial) | `LIBERADA` / `EN_PROCESO` | **BLOQUEADO:** No puede entregar material a OPs en estado `BORRADOR` o `CANCELADA`. |
| `PRODUCCION`| Planta | Cargar en Estación y Reportar Avance | `LIBERADA_PRODUCCION` | Opera únicamente con la revisión del plano vigente y autorizada en PDF[cite: 12]. |
| `METROLOGIA`| Calidad Prod. | Registrar Ficha Dimensional | `EN_INSPECCION` | Inhabilita la selección de instrumentos con fecha de calibración vencida (`RN-MT-001`)[cite: 12]. |

---

## 5. FLUJOS DE CONTROL Y REGLAS DE DECISIÓN DEL SISTEMA

### A. Regla de Liberación de Orden de Producción (OP)

```text
                  SOLICITUD DE LIBERACIÓN DE OP
                                │
                                ▼
                   SISTEMA EVALÚA CONDICIONES
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
 REQUISITOS COMPLETOS                               FALTA REQUISITO
   - Requisitos de Venta Confirmados                  - Falta Plano Aprobado
   - Plano Aprobado (Rev. Vigente)                    - BOM Incompleto
   - BOM Definido                                     - Stock Reservado < 100%
   - Stock Reservado = 100%                             │
        │                                               ▼
        ▼                                      BLOQUEAR LIBERACIÓN
   LIBERAR OP                                           │
        │                                      Mostrar Causa / Motivo
        ▼
   PRODUCCIÓN
B. Regla de Entrega de Materiales en Almacén
Plaintext
                  SOLICITUD / REQUERIMIENTO DE MATERIAL
                                │
                                ▼
                       ALMACÉN REVISA STOCK
                                │
                                ▼
                   SISTEMA VALIDA CONDICIONES
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
   OP NO LIBERADA /                                OP LIBERADA /
MATERIAL NO AUTORIZADO                            STOCK DISPONIBLE
        │                                               │
        ▼                                               ▼
     BLOQUEAR                                  AUTORIZAR ENTREGA
                                                        │
                                                        ▼
                                           REGISTRAR MOVIMIENTO (TOTAL/PARCIAL)
                                                        │
                                                        ▼
                                             TRAZABILIDAD (LOTE/COLADA)