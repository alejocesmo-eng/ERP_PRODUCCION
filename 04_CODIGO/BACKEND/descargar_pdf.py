import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def construir_pdf_guia_tecnica():
    pdf_filename = "Manual_Tecnico_Arquitectura_SGI_MES_ISO9001.pdf"
    
    # Configuración de márgenes e impresión
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    story = []
    styles = getSampleStyleSheet()

    # Estilos tipográficos
    titulo_style = ParagraphStyle(
        'TituloPrincipal',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=4
    )

    subtitulo_style = ParagraphStyle(
        'SubtituloPrincipal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )

    seccion_style = ParagraphStyle(
        'EncabezadoSeccion',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'CuerpoTexto',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )

    code_style = ParagraphStyle(
        'CodigoSQL',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#0F172A')
    )

    # Encabezado Corporativo
    story.append(Paragraph("SISTEMA DE GESTIÓN INTEGRAL (SGI — ISO 9001:2026)", titulo_style))
    story.append(Paragraph("Manual Técnico de Arquitectura, Modelo Entidad-Relación y Módulo MES", subtitulo_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=10))

    # 1. Resumen de Arquitectura
    story.append(Paragraph("1. Arquitectura de Software y Stack Tecnológico", seccion_style))
    texto_stack = (
        "<b>Frontend:</b> React 18, Vite, Tailwind CSS, React Router DOM v6. Visor dinámico de planos técnicos "
        "PDF embebido con control de zoom en tiempo real.<br/>"
        "<b>Backend:</b> Python 3.14 (.venv) con servicios API REST (FastAPI / Flask).<br/>"
        "<b>Base de Datos:</b> PostgreSQL / SQLite con soporte para triggers y trazabilidad de lote a lote."
    )
    story.append(Paragraph(texto_stack, body_style))
    story.append(Spacer(1, 10))

    # 2. Relaciones del Modelo de Datos (Tabla)
    story.append(Paragraph("2. Modelo Entidad-Relación y Tablas (PostgreSQL)", seccion_style))
    
    data_tablas = [
        ["Tabla (Entidad)", "PK", "FK", "Descripción y Trazabilidad ISO 9001"],
        ["ventas_proyectos", "id_proyecto", "N/A", "Pedidos de venta y OTs principales."],
        ["planos_tecnicos", "id_plano", "id_proyecto", "Planos liberados en Nivel 2 y visor PDF."],
        ["bom_materia_prima", "id_bom", "id_plano", "Solicitudes de PR e insumos del diseño."],
        ["entregas_parciales_bom", "id_entrega", "id_bom", "Remisiones parciales recibidas del proveedor."],
        ["mes_sublotes", "id_sublote", "id_plano", "Fraccionamiento de OTs a máquinas/operarios."],
        ["mes_registro_tiempos", "id_tiempo", "id_sublote", "Tiempos en segundo plano (Setup, Prod, Pausas)."],
        ["mes_reportes_cierre", "id_reporte", "id_sublote", "Auditoría de calidad final (OK vs Scrap)."]
    ]

    t_model = Table(data_tablas, colWidths=[110, 65, 65, 312])
    t_model.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F8FAFC')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t_model)
    story.append(Spacer(1, 10))

    # 3. Esquema DDL SQL
    story.append(Paragraph("3. Estructura DDL en SQL (Base de Datos)", seccion_style))
    sql_code = (
        "CREATE TABLE ventas_proyectos (id_proyecto SERIAL PRIMARY KEY, codigo_op VARCHAR(20) UNIQUE NOT NULL, numero_pedido VARCHAR(20) NOT NULL);<br/>"
        "CREATE TABLE planos_tecnicos (id_plano SERIAL PRIMARY KEY, id_proyecto INT REFERENCES ventas_proyectos(id_proyecto), codigo_plano VARCHAR(50) NOT NULL);<br/>"
        "CREATE TABLE bom_materia_prima (id_bom SERIAL PRIMARY KEY, id_plano INT REFERENCES planos_tecnicos(id_plano), solicitud_pr VARCHAR(20) NOT NULL);<br/>"
        "CREATE TABLE entregas_parciales_bom (id_entrega SERIAL PRIMARY KEY, id_bom INT REFERENCES bom_materia_prima(id_bom), numero_remision VARCHAR(50));<br/>"
        "CREATE TABLE mes_sublotes (id_sublote VARCHAR(50) PRIMARY KEY, id_plano INT REFERENCES planos_tecnicos(id_plano), maquina_codigo VARCHAR(30));<br/>"
        "CREATE TABLE mes_registro_tiempos (id_tiempo SERIAL PRIMARY KEY, id_sublote VARCHAR(50) REFERENCES mes_sublotes(id_sublote), fase VARCHAR(20));<br/>"
        "CREATE TABLE mes_reportes_cierre (id_reporte SERIAL PRIMARY KEY, id_sublote VARCHAR(50) REFERENCES mes_sublotes(id_sublote), piezas_ok INT, piezas_scrap INT);"
    )
    story.append(Paragraph(sql_code, code_style))
    story.append(Spacer(1, 10))

    # 4. Reglas Misionat
    story.append(Paragraph("4. Reglas Misiones y Funcionamiento MES en Planta", seccion_style))
    reglas = [
        "<b>• Entregas Parciales BOM:</b> Habilita sub-lotes proporcionales según las remisiones parciales del proveedor.",
        "<b>• Medición en Días:</b> La permanencia en las 5 fases principales se calcula en Días/Horas para costeo del Líder.",
        "<b>• Registro de Pausas:</b> Opciones táctiles para paradas (almuerzo, baño, falta de material, falla de herramienta).",
        "<b>• Cronómetros Ocultos:</b> Medición en segundo plano sin generar presión en el operario."
    ]
    for r in reglas:
        story.append(Paragraph(r, body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#94A3B8'), spaceBefore=5, spaceAfter=5))
    story.append(Paragraph("SGI ISO 9001:2026 — Control de Trazabilidad y Calidad Industrial", subtitulo_style))

    doc.build(story)
    print(f"✅ PDF generado correctamente: {pdf_filename}")

if __name__ == '__main__':
    construir_pdf_guia_tecnica()