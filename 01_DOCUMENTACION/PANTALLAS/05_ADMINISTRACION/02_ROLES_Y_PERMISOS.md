# Pantalla: Matriz de Roles y Permisos por Módulo (RBAC)

##  Objetivo
Definir y visualizar de forma centralizada la matriz de control de acceso basada en roles (Role-Based Access Control) para todas las acciones del sistema.

## Matriz de Permisos por Acción
| Módulo        | Acción / Evento       | Administrador | Ventas | Diseño | Almacén   | Producción | Calidad |
| :--- | :---   | :---: | :---:         | :---:         | :---: | :---: | :---: |
| **Ventas**    | Crear Proyecto        | ✅            | ✅    | ❌    | ❌        | ❌        | ❌ |
| **Diseño**    | Subir Plano / Rev.    | ✅            | ❌    | ✅    | ❌        | ❌        | ❌ |
| **Almacén**   | Ajustar Stock         | ✅            | ❌    | ❌    | ✅        | ❌        | ❌ |
| **Producción** | Liberar OP           | ✅            | ❌    | ❌    | ❌        | ✅        | ❌ |
| **Calidad**   | Aprobar OP / Cierre   | ✅            | ❌    | ❌    | ❌        | ❌        | ✅ |

##  Regla de Seguridad
- El sistema utiliza evaluaciones mediante fórmulas `LOOKUP(USEREMAIL(), "Usuarios", "Email", "Rol")` para restringir botones, vistas y opciones de edición/borrado.