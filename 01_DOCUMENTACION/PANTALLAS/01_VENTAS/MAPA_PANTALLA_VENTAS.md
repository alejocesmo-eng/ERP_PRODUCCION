# MAPA DE PANTALLAS

## 1. Objetivo

Definir las pantallas funcionales del Sistema de Gestión Integral,
los usuarios que pueden acceder a ellas, la información que muestran,
las acciones disponibles y las validaciones que debe realizar el sistema.

Este documento corresponde a la especificación funcional inicial.
El diseño visual será definido posteriormente.

---

# 2. VENTAS

## 2.1 Dashboard

### Objetivo
Mostrar un resumen del estado de los proyectos relacionados con Ventas.

### Acceso
Rol: Ventas.

### Información
- Proyectos nuevos.
- Proyectos en evaluación.
- Proyectos en diseño.
- Proyectos listos para producción.
- Proyectos en producción.
- Actividad reciente.

---

## 2.2 Lista de proyectos

### Objetivo
Consultar y localizar proyectos.

### Acciones
- Crear proyecto.
- Buscar.
- Filtrar.
- Consultar detalle.

### Información
- Código.
- Nombre.
- Cliente.
- Estado.
- Fecha de creación.
- Fecha requerida.
- Responsable.

### Restricciones
Ventas no puede:
- modificar información técnica de Diseño;
- modificar planos;
- liberar OP;
- modificar inventario;
- entregar materiales.

---

## 2.3 Crear proyecto

### Objetivo
Registrar un nuevo proyecto recibido por Ventas.

### Información
- Nombre.
- Cliente.
- Número de cotización/orden, si aplica.
- Cantidad.
- Fecha requerida.
- Prioridad.
- Descripción.
- Responsable.
- Documentación inicial.

### Al crear
El sistema debe:
1. Generar código único.
2. Registrar usuario creador.
3. Registrar fecha y hora.
4. Crear el proyecto.
5. Asignar estado NUEVO.
6. Habilitar el proyecto para Diseño.

---

## 2.4 Detalle del proyecto

### Objetivo
Mostrar toda la información relacionada con el proyecto
según los permisos del usuario.

### Secciones
- Resumen.
- Diseño.
- Materiales.
- Retales.
- Planos.
- Solicitudes de material.
- Orden de producción.
- Producción.
- Historial.
- Auditoría.

### Información principal
- Código.
- Nombre.
- Cliente.
- Cantidad.
- Fecha requerida.
- Responsable.
- Estado.

### Línea de proceso
Ventas → Evaluación → Diseño → Materiales → Planos → OP → Producción → Cierre.