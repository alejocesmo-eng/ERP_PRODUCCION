#---
tipo: changelog
codigo: CHG-SIST-001
nombre: Registro de Cambios, Hitos y Hoja de Ruta hacia el MVP (31/12/2026)
fase: F1-F5
estado: aprobado
version: 1.0
autor: Arquitecto de Software / Project Lead
sistema_destino: ERP FastAPI + PostgreSQL
---

# CHG-SIST-001: Registro de Cambios y Hoja de Ruta hacia el MVP

## 1. Hoja de Ruta de Entregables (MVP: 31/12/2026)

```mermaid
gantt
    title Cronograma de Hitos ERP Manufactura
    dateFormat  YYYY-MM-DD
    section Fase 1: Core & DB
    Arquitectura & Script SQL Completo       :done,    des1, 2026-10-01, 2026-10-19
    Módulo Usuarios / RBAC / FastAPI Core   :active,  des2, 2026-10-20, 2026-11-30
    section Fase 3: Producción & CNC
    Puesto CNC / WebSockets / Planos TTL     :         des3, 2026-12-01, 2027-02-28
    Control de Tiempos de Diseño             :         des4, 2027-03-01, 2027-04-15
    section Calidad & Pruebas
    Módulo Metrología, TT y NC               :         des5, 2027-04-16, 2027-06-30
    Pruebas Integrales y Despliegue MVP      :         des6, 2027-07-01, 2026-12-31 Registro de decisiones

Añadir una nota por decisión relevante usando la plantilla `Plantilla ADR.md`.

## Decisiones
-
