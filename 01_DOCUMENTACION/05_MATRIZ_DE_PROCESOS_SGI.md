---

### 2. `01_DOCUMENTACION/05_MATRIZ_DE_PROCESOS_SGI.md`

```markdown
# MATRIZ DE PROCESOS DEL SGI

**Versión:** 1.0  
**Estado:** Documento base de diseño  
**Documento:** 05_MATRIZ_DE_PROCESOS_SGI.md  

---

## 1. FICHA RESUMEN DE PROCESOS MISIONALES

| Código | Proceso | Responsable | Entradas | Salidas Clave | Rol de Calidad |
|---|---|---|---|---|---|
| **PM-01** | Ventas y Clientes | Ventas | Solicitud / Requisitos del cliente | Proyecto Confirmado + Requisitos | Audita integridad comercial |
| **PM-02** | Diseño e Ingeniería | Diseño | Proyecto Confirmado | Planos, BOM, Especificaciones | Verifica completitud de paquetes |
| **PM-03** | Gestión de OPs | Calidad | Información Técnica de Diseño | OP Oficial Generada/Liberada | **Genera la OP** y valida condiciones |
| **PM-04** | Almacén y Materiales | Almacén | OP Liberada / Recepción Insumos | Material Despachado (Trazable) | Audita lotes y certificaciones |
| **PM-05** | Producción | Producción | OP Liberada + Planos Activos | Producto Fabricado | Audita cumplimiento de proceso |
| **PM-06** | Metrología | Metrología | Producto de Piso de Planta | Ficha de Inspección Conforme | Controla calibración de equipos |
| **PM-07** | Entrega y Cierre | Logística | Producto Conforme + Remisión | Entrega al Cliente + Cierre OP | Valida expediente final |

---

## 2. REGLA MAESTRA DE INTERACCIÓN DISEÑO - CALIDAD - PRODUCCIÓN

1. **Diseño:** Prepara planos, lista de materiales (BOM) y especificaciones técnicas[cite: 1].
2. **Calidad:** Realiza validación checklist (datos de venta, planos aprobados, versión activa, BOM definido) y genera la OP en estado `APROBADA`[cite: 1].
3. **Almacén:** Verifica reserva e inventario[cite: 1]. Cuando el stock disponible sea del 100%, la OP pasa a `LIBERADA`[cite: 1].
4. **Producción:** Ejecuta la OP únicamente con planos en versión activa y materiales trazables[cite: 1].