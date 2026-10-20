-- =============================================================================
-- DATOS INICIALES Y SEMILLA DE PRUEBAS COMPLETA (SEED - SGI ISO 9001:2026)
-- =============================================================================

-- 1. ROLES DEL SISTEMA
INSERT INTO roles (id_rol, nombre_rol, descripcion) VALUES
('ADMIN', 'Administrador', 'Acceso total a la plataforma y configuraciones maestras'),
('VENTAS', 'Ventas / Comercial', 'Creación y seguimiento de proyectos con clientes'),
('DISENO', 'Diseño e Ingeniería', 'Gestión de planos, revisiones, BOM y solicitud de OP'),
('ALMACEN', 'Almacén e Inventario', 'Recepción de compras, entregas, stock y retales'),
('PRODUCCION', 'Producción / Planta', 'Ejecución de OPs, registros de avance y tiempos'),
('CALIDAD', 'Calidad e Inspección', 'Inspección de piezas, no conformidades y aprobación de OP')
ON CONFLICT (id_rol) DO NOTHING;

-- 2. PERMISOS CLAVE POR MÓDULO
INSERT INTO permisos (id_permiso, modulo, descripcion) VALUES
('PERM_ADMIN_ALL', 'ADMIN', 'Acceso administrativo total'),
('PERM_PROYECTO_CREAR', 'VENTAS', 'Permite crear nuevos proyectos'),
('PERM_PLANO_GESTION', 'DISENO', 'Subir y versionar planos técnicos'),
('PERM_OP_LIBERAR', 'PRODUCCION', 'Liberar Orden de Producción hacia planta'),
('PERM_CALIDAD_APROBAR', 'CALIDAD', 'Dictaminar inspección y habilitar cierre de OP')
ON CONFLICT (id_permiso) DO NOTHING;

-- 3. ASIGNACIÓN DE PERMISOS A ROLES
INSERT INTO rol_permisos (id_rol, id_permiso) VALUES
('ADMIN', 'PERM_ADMIN_ALL'),
('VENTAS', 'PERM_PROYECTO_CREAR'),
('DISENO', 'PERM_PLANO_GESTION'),
('PRODUCCION', 'PERM_OP_LIBERAR'),
('CALIDAD', 'PERM_CALIDAD_APROBAR')
ON CONFLICT DO NOTHING;

-- 4. USUARIOS BASE DE PRUEBA
INSERT INTO usuarios (email, password_hash, nombre_completo, id_rol) VALUES
('admin@hd.com', '$2b$10$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'Administrador del Sistema', 'ADMIN'),
('ventas@hd.com', 'admin123', 'Laura Gómez - Comercial', 'VENTAS'),
('diseno@hd.com', 'admin123', 'Carlos Ruiz - Lider Ingeniería', 'DISENO'),
('calidad@hd.com', 'admin123', 'Ing. Roberto Silva - Calidad', 'CALIDAD')
ON CONFLICT (email) DO NOTHING;

-- 5. CATÁLOGOS BASE DE MAQUINARIA Y EMPLEADOS
INSERT INTO maquinas (id_maquina, nombre_maquina, tipo_maquina, estado) VALUES
('MAQ-0357', 'Torno CNC Mazak 0357', 'Torno CNC', 'OPERATIVA'),
('MAQ-0412', 'Centro de Mecanizado Haas VF-2', 'Fresadora CNC', 'OPERATIVA'),
('MAQ-0105', 'Corte por Plasma Hypertherm 105', 'Corte Plasma', 'OPERATIVA')
ON CONFLICT (id_maquina) DO NOTHING;

INSERT INTO empleados (id_empleado, nombre_completo, cargo, area) VALUES
('EMP-001', 'Juan Pérez', 'Operador CNC Senior', 'Producción'),
('EMP-002', 'Andrés Molina', 'Diseñador CAD/CAM', 'Diseño'),
('EMP-003', 'Sonia Rodríguez', 'Inspector Metrólogo', 'Calidad')
ON CONFLICT (id_empleado) DO NOTHING;

-- 6. PEDIDOS COMERCIALES (GESTIONADOS POR VENTAS)
-- NOTA: numero_pedido es el agrupador comercial del cliente.
--       Cada línea representa una pieza o item específico solicitado dentro del pedido.

INSERT INTO proyectos (
    id_proyecto,
    numero_pedido,
    codigo_proyecto,
    cliente_nombre,
    contacto_nombre,
    contacto_telefono,
    contacto_email,
    ubicacion_cliente,
    cantidad,
    detalle_producto,
    requisitos_cliente,
    confirmado,
    creado_en
) VALUES
-- PEDIDO 5001 (Empresa Test S.A. - Planta Funza) -> Contiene 3 Piezas Distintas
(
    'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
    '5001',
    '101',
    'Empresa Test S.A.',
    'Ing. Carlos Pérez',
    '3001234567',
    'carlos@cliente.com',
    'Planta Funza - Bodega 3',
    10,
    'Estructura Mecanizada Principal',
    'Tolerancia dimensional +/- 0.05mm. Acabado superficial N6.',
    TRUE,
    CURRENT_TIMESTAMP - INTERVAL '5 days'
),
(
    'b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e',
    '5001',
    '102',
    'Empresa Test S.A.',
    'Ing. Carlos Pérez',
    '3001234567',
    'carlos@cliente.com',
    'Planta Funza - Bodega 3',
    5,
    'Placa Base de Apoyo Técnico',
    'Material Acero AISI 1045. Rectificado de caras paralelas.',
    TRUE,
    CURRENT_TIMESTAMP - INTERVAL '5 days'
),
(
    'e5f6a7b8-9c0d-1e2f-3a4b-5c6d7e8f9a0b',
    '5001',
    '103',
    'Empresa Test S.A.',
    'Ing. Carlos Pérez',
    '3001234567',
    'carlos@cliente.com',
    'Planta Funza - Bodega 3',
    20,
    'Perno Especial Guía con Roscado M16',
    'Tratamiento pavonado negro anticorrosivo.',
    TRUE,
    CURRENT_TIMESTAMP - INTERVAL '5 days'
),

-- PEDIDO 5002 (Industrias Alfa S.A.S. - Sede Yumbo) -> Contiene 2 Piezas
(
    'c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f',
    '5002',
    '104',
    'Industrias Alfa S.A.S.',
    'Ing. María López',
    '3109876543',
    'maria@alfa.com',
    'Sede Yumbo - Bloque B',
    15,
    'Bushing de Bronce Fosilizado',
    'Tratamiento térmico especial y prueba de dureza Brinell.',
    TRUE,
    CURRENT_TIMESTAMP - INTERVAL '2 days'
),
(
    'f6a7b89c-0d1e-2f3a-4b5c-6d7e8f9a0b1c',
    '5002',
    '105',
    'Industrias Alfa S.A.S.',
    'Ing. María López',
    '3109876543',
    'maria@alfa.com',
    'Sede Yumbo - Bloque B',
    8,
    'Eje Roscado de Transmisión Inoxidable',
    'Rosca izquierda M24x2. Acero AISI 316L.',
    TRUE,
    CURRENT_TIMESTAMP - INTERVAL '2 days'
),

-- PEDIDO 5003 (Metalmecánica del Norte - Planta Tocancipá) -> En Revisión Comercial
(
    'd4e5f6a7-b89c-0d1e-2f3a-4b5c6d7e8f9a',
    '5003',
    'PED-5003',
    'Metalmecánica del Norte',
    'Ing. Fernando Torres',
    '3154567890',
    'ftorres@metdelnorte.com',
    'Planta Tocancipá',
    2,
    'Eje Principal de Transmisión Industrial',
    'Tolerancias ISO h6 para alojamientos de rodamientos.',
    FALSE,
    CURRENT_TIMESTAMP
)
ON CONFLICT (id_proyecto) DO NOTHING;

-- 7. PAQUETES TÉCNICOS Y ASIGNACIÓN A PLANTAS POR DISEÑO (PM-02)
-- Distribución a Mecanizados, Metalistería y Servicios con cálculo de tiempos en DÍAS.

INSERT INTO planos (
    id_plano,
    id_proyecto,
    codigo_plano,
    revision,
    dibujante_asignado,
    unidad_planta,
    estado_diseno,
    causa_espera,
    material_requerido,
    insumos_opcionales,
    dias_estimados_diseno,
    dias_espera_planificacion,
    fecha_inicio_programada,
    fecha_entrega_cliente,
    fecha_entrega_produccion,
    archivo_url,
    estado,
    creado_en
) VALUES
-- OP 101 (Mecanizados) -> LIBERADA
(
    gen_random_uuid(),
    'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
    'PL-5001-01',
    'REV-01',
    'Carlos Ruiz',
    'Mecanizados',
    'LIBERADA',
    NULL,
    'Acero AISI 1045 / Barra Redonda 3"',
    'Refrigerante soluble y brocas HSS',
    2,
    1,
    CURRENT_DATE - INTERVAL '3 days',
    CURRENT_DATE + INTERVAL '10 days',
    CURRENT_DATE + INTERVAL '3 days',
    'https://sgi-docs.s3.amazonaws.com/planos/PL-5001-01_REV01.pdf',
    'APROBADO',
    CURRENT_TIMESTAMP - INTERVAL '4 days'
),

-- OP 102 (Metalistería) -> EN DISEÑO
(
    gen_random_uuid(),
    'b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e',
    'PL-5001-02',
    'REV-01',
    'Andrés Molina',
    'Metalisteria',
    'EN_DISENO',
    NULL,
    'Lámina Acero HR 1/2" (12.7mm)',
    'Soldadura E7018 1/8"',
    3,
    0,
    CURRENT_DATE - INTERVAL '1 days',
    CURRENT_DATE + INTERVAL '12 days',
    CURRENT_DATE + INTERVAL '5 days',
    NULL,
    'BORRADOR',
    CURRENT_TIMESTAMP - INTERVAL '2 days'
),

-- OP 103 (Mecanizados) -> PLANIFICADA
(
    gen_random_uuid(),
    'e5f6a7b8-9c0d-1e2f-3a4b-5c6d7e8f9a0b',
    'PL-5001-03',
    'REV-01',
    'Carlos Ruiz',
    'Mecanizados',
    'PLANIFICADA',
    'Verificación de tratamiento de pavonado en taller externo',
    'Barra Hexagonal Acero 1045 1"',
    'Aceite de corte mineral',
    1,
    2,
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '7 days',
    CURRENT_DATE + INTERVAL '2 days',
    NULL,
    'BORRADOR',
    CURRENT_TIMESTAMP - INTERVAL '1 days'
),

-- OP 104 (Servicios) -> PLANIFICADA
(
    gen_random_uuid(),
    'c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f',
    'PL-5002-01',
    'REV-01',
    'Carlos Ruiz',
    'Servicios',
    'PLANIFICADA',
    'En espera de confirmación de plano patrón por el cliente',
    'Bronce SAE 660 / Barra Hueca 4"x2"',
    'Herramientas de torneado de interiores',
    2,
    1,
    CURRENT_DATE,
    CURRENT_DATE + INTERVAL '8 days',
    CURRENT_DATE + INTERVAL '2 days',
    NULL,
    'BORRADOR',
    CURRENT_TIMESTAMP
);