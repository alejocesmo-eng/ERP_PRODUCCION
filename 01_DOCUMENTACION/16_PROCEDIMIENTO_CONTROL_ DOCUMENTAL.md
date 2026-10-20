# 16 — PROCEDIMIENTO DE CONTROL DOCUMENTAL Y REGISTROS (ISO 9001:2026)

**Código:** PR-SGI-DOC-001  
**Versión:** 1.0  
**Estado:** Procedimiento Aprobado  
**Prioridad:** P2 — Media (AC-014)  

---

## 1. OBJETIVO Y ALCANCE

Normar la creación, revisión, aprobación, distribución, inmutabilidad, retención y disposición de la información documentada del SGI, incluyendo documentos internos, documentos de origen externo (planos/especificaciones del cliente, normas técnicas) y registros del software[cite: 8, 15].

---

## 2. REGLAS DE CONTROL EN EL ERP Y CICLO DE VIDA

1. **Inmutabilidad y Versionamiento:** Todo documento técnico o plano aprobado (`REV-01`, `REV-02`) se congela automáticamente[cite: 8, 15]. Las versiones anteriores pasan automáticamente a estado `OBSOLETO`[cite: 8, 15].
2. **Control de Documentos Externos:** Los planos e instructivos suministrados por el cliente se registran en el expediente del proyecto en formato PDF con estado "VIGENTE_CLIENTE" antes de pasar a Ingeniería[cite: 8, 15].
3. **Retención de Registros en Base de Datos:** Los registros de auditoría (`trazabilidad_auditora`), inspecciones metrológicas y OPs finalizadas se conservan digitalmente por un período mínimo de 5 años[cite: 8, 12].

---

## 3. LISTADO MAESTRO DE DOCUMENTOS SGI

| Código Documento | Nombre del Artefacto / Registro | Proceso Origen | Responsable de Aprobación |
|---|---|---|---|
| `00_OBJETIVO_Y_ALCANCE.md` | Alcance y Contexto del SGI | PE-01 Dirección | Alta Dirección[cite: 6, 7] |
| `02_MATRIZ_RESPONSABILIDADES.md`| Matriz RACI y Permisos RBAC | PA-01 / PA-04 | Dirección / Calidad / TI[cite: 7] |
| `06_MATRIZ_DE_RIESGOS.md` | Matriz de Riesgos y Controles | PE-02 Riesgos | Líder SGI / Dueños de Proceso[cite: 6] |
| `07_MATRIZ_DE_INDICADORES.md` | Matriz de KPIs Automáticos | PE-01 Dirección | Analítica / Calidad[cite: 6] |
| `10_MATRIZ_TRAZABILIDAD_ISO.md` | Matriz de Trazabilidad ISO 9001 | PC-01 Calidad | Líder Calidad[cite: 7] |