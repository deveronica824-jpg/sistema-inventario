import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import re

# Intento de importación para lectura automática de PDF
try:
    import pdfplumber
    PDF_PARSER_AVAILABLE = True
except ImportError:
    PDF_PARSER_AVAILABLE = False

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS VISUALES (TEMA CLARO CORPORATIVO)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Gestión Integral - Pedregal Los Vera",
    layout="wide"
)

st.markdown("""
    <style>
    /* Estilos generales del tema claro */
    .stApp {
        background-color: #FFFFFF;
        color: #0F172A;
    }
    
    /* Encabezado principal */
    .main-header {
        font-size: 20px;
        font-weight: 700;
        color: #0F172A;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 8px;
        margin-bottom: 20px;
    }
    
    /* Tarjeta de datos de la empresa */
    .company-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #1E3A8A;
        padding: 12px 16px;
        border-radius: 6px;
        margin-bottom: 20px;
        font-size: 13px;
        color: #334155;
    }
    
    /* Métricas ejecutivas */
    div[data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 12px;
        border-radius: 6px;
    }
    div[data-testid="stMetricLabel"] {
        color: #64748B;
        font-size: 12px;
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        color: #0F172A;
        font-size: 20px;
        font-weight: 700;
    }
    
    /* Botones de acción */
    .stButton>button {
        background-color: #1E3A8A;
        color: #FFFFFF;
        border-radius: 4px;
        border: none;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #2563EB;
        color: #FFFFFF;
    }
    
    /* Formato de impresión para Remisiones */
    @media print {
        .no-print { display: none !important; }
        .print-remision {
            border: 2px solid #000000;
            padding: 15px;
            width: 100%;
            font-family: Arial, sans-serif;
            color: #000000;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# MOTOR DE EXTRACCIÓN AUTOMÁTICA DE DATOS (OCR / PARSING)
# ---------------------------------------------------------
def extraer_datos_pdf(archivo_pdf):
    """
    Lee el contenido de un archivo PDF y extrae información
    clave como Folio, RFC, Fecha e Importes mediante expresiones regulares.
    """
    datos = {
        "folio": "",
        "rfc": "",
        "fecha": None,
        "monto_total": 0.0,
        "texto_detectado": False
    }
    
    if not PDF_PARSER_AVAILABLE:
        return datos
        
    try:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto = ""
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ""
            
            if texto.strip():
                datos["texto_detectado"] = True
                
                # 1. Búsqueda de RFC
                match_rfc = re.search(r'[A-Z&Ñ]{3,4}\d{6}[A-V1-9][A-Z1-9][0-9A]', texto)
                if match_rfc:
                    datos["rfc"] = match_rfc.group(0)
                    
                # 2. Búsqueda de Monto / Total
                match_monto = re.search(r'(?:TOTAL|Total|Monto Total)\s*\$?\s*([\d,]+\.\d{2})', texto)
                if match_monto:
                    datos["monto_total"] = float(match_monto.group(1).replace(',', ''))
                    
                # 3. Búsqueda de Folio
                match_folio = re.search(r'(?:Folio|FOLIO|Factura|Remision)\s*[:#]?\s*(\w+)', texto)
                if match_folio:
                    datos["folio"] = match_folio.group(1)
                    
                # 4. Búsqueda de Fecha (YYYY-MM-DD o DD/MM/YYYY)
                match_fecha = re.search(r'(\d{2,4}[-/\.]\d{1,2}[-/\.]\d{2,4})', texto)
                if match_fecha:
                    f_str = match_fecha.group(1)
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
                        try:
                            datos["fecha"] = datetime.strptime(f_str, fmt).date()
                            break
                        except ValueError:
                            pass
    except Exception as e:
        st.error(f"Error durante el procesamiento automático del documento: {e}")
        
    return datos

# ---------------------------------------------------------
# BASE DE DATOS (SQLite)
# ---------------------------------------------------------
def get_connection():
    return sqlite3.connect("sistema_pedregal.db", check_same_thread=False)

def inicializar_bd():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            rfc TEXT,
            domicilio TEXT,
            ciudad TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS remisiones (
            folio INTEGER PRIMARY KEY,
            fecha DATE,
            cliente TEXT,
            ciudad TEXT,
            chofer TEXT,
            camion TEXT,
            placas TEXT,
            hora_inicio TEXT,
            hora_salida TEXT,
            archivo_adjunto BLOB,
            nombre_archivo TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS remision_detalle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_remision INTEGER,
            cantidad REAL,
            unidad TEXT,
            producto TEXT,
            variedad TEXT,
            tabla TEXT,
            precio_unitario REAL,
            FOREIGN KEY (folio_remision) REFERENCES remisiones (folio)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_evaluacion TEXT,
            folio_remision INTEGER,
            fecha DATE,
            periodo TEXT,
            grado1_cantidad REAL,
            precio_unitario REAL,
            observaciones TEXT,
            archivo_adjunto BLOB,
            FOREIGN KEY (folio_remision) REFERENCES remisiones (folio)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_remision INTEGER,
            pagado_por TEXT,
            factura_pdf BLOB,
            fecha_pago DATE,
            banco TEXT,
            FOREIGN KEY (folio_remision) REFERENCES remisiones (folio)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_factura TEXT,
            fecha DATE,
            cliente TEXT,
            rfc TEXT,
            folio_fiscal TEXT,
            metodo_pago TEXT,
            forma_pago TEXT,
            monto_total REAL,
            remisiones_asociadas TEXT,
            fecha_pago DATE,
            banco TEXT,
            estatus_pago TEXT,
            factura_pdf BLOB,
            complemento_pdf BLOB,
            nota_credito_pdf BLOB
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS control_envases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE,
            cliente TEXT,
            tipo_movimiento TEXT,
            tipo_envase TEXT,
            cantidad INTEGER,
            observacion TEXT
        )
    ''')
    
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, rfc, domicilio, ciudad) VALUES ('LEONALI', 'LEO030827903', 'FABRICA EL LEON No. SN, EL LEON, C.P.74360, Puebla', 'Puebla')")
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, rfc, domicilio, ciudad) VALUES ('FRESCOS DON-GU', 'FDG101010AAA', 'San Miguel de Allende', 'San Miguel de Allende')")
    
    conn.commit()

inicializar_bd()

def calcular_periodo_semanal(fecha_obj):
    inicio_semana = fecha_obj - timedelta(days=fecha_obj.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    return f"del {inicio_semana.day} de {meses[inicio_semana.month - 1]} al {fin_semana.day} de {meses[fin_semana.month - 1]}"

def obtener_siguiente_folio():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(folio) FROM remisiones")
    max_folio = cursor.fetchone()[0]
    return (max_folio + 1) if max_folio else 1777

# ---------------------------------------------------------
# ENCABEZADO Y MENU PRINCIPAL
# ---------------------------------------------------------
st.markdown("""
    <div class="company-card">
        <strong style="font-size: 15px; color: #0F172A;">PEDREGAL LOS VERA, S.A. DE C.V.</strong><br>
        <b>RFC:</b> PVE150220JE0 | <b>Dirección:</b> Fray Juan de San Miguel No. 24, Col Cimatario CP 76030, Querétaro, Qro.<br>
        <i>Régimen Fiscal: 622 - Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras</i>
    </div>
""", unsafe_allow_html=True)

menu = st.sidebar.radio(
    "MÓDULOS DE SISTEMA",
    [
        "Dashboard / Métricas",
        "1. Remisiones",
        "2. Evaluaciones",
        "3. Fletes",
        "4. Facturación (OCR)",
        "5. Control de Envases",
        "6. Reporte MATRIZ",
        "Configuración"
    ]
)

conn = get_connection()

# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard / Métricas":
    st.markdown('<div class="main-header">Resumen Ejecutivo y Estado Financiero</div>', unsafe_allow_html=True)
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    df_fact = pd.read_sql("SELECT SUM(monto_total) as tot, SUM(CASE WHEN estatus_pago = 'PAGADO' THEN monto_total ELSE 0 END) as pag, SUM(CASE WHEN estatus_pago != 'PAGADO' THEN monto_total ELSE 0 END) as pend FROM facturas", conn)
    df_g1 = pd.read_sql("SELECT AVG(grado1_cantidad) as avg_g1 FROM evaluaciones", conn)

    m_tot = df_fact['tot'].values[0] or 0.0
    m_pag = df_fact['pag'].values[0] or 0.0
    m_pend = df_fact['pend'].values[0] or 0.0
    g1_avg = df_g1['avg_g1'].values[0] or 0.0

    col_m1.metric("Facturado Total", f"${m_tot:,.2f}")
    col_m2.metric("Cobrado", f"${m_pag:,.2f}")
    col_m3.metric("Por Cobrar", f"${m_pend:,.2f}")
    col_m4.metric("Promedio Grado 1", f"{g1_avg:,.1f} Kg/Pzs")

    st.markdown("---")
    st.subheader("Cuentas por Cobrar Pendientes")
    df_pend = pd.read_sql("SELECT folio_factura as 'Folio Factura', fecha as Fecha, cliente as Cliente, monto_total as Total, metodo_pago as Método, estatus_pago as Estatus FROM facturas WHERE estatus_pago != 'PAGADO'", conn)
    st.dataframe(df_pend, use_container_width=True)

# =========================================================
# MÓDULO 1: REMISIONES
# =========================================================
elif menu == "1. Remisiones":
    st.markdown('<div class="main-header">Gestión de Remisiones</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Registro de Remisión", "Consecutivo de Remisiones"])
    
    with tab1:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            folio_input = st.number_input("Número de Folio:", value=obtener_siguiente_folio(), step=1)
            fecha_remision = st.date_input("Fecha:", datetime.now())
            df_cli = pd.read_sql("SELECT nombre, ciudad FROM clientes", conn)
            cli_list = df_cli['nombre'].tolist() if not df_cli.empty else []
            cliente_sel = st.selectbox("Cliente:", cli_list + ["+ Agregar Nuevo"])
            
            if cliente_sel == "+ Agregar Nuevo":
                cliente_sel = st.text_input("Nombre Cliente:")
                ciudad_input = st.text_input("Ciudad:")
            else:
                ciudad_default = df_cli[df_cli['nombre'] == cliente_sel]['ciudad'].values[0] if not df_cli.empty else ""
                ciudad_input = st.text_input("Ciudad:", value=ciudad_default)

        with col_f2:
            st.subheader("Datos de Transporte")
            chofer = st.text_input("Nombre del Chofer:")
            camion = st.text_input("Tipo de Camión:")
            placas = st.text_input("Placas:")
            col_t1, col_t2 = st.columns(2)
            with col_t1: h_inicio = st.time_input("Hora Inicio:")
            with col_t2: h_salida = st.time_input("Hora Salida:")
        
        st.subheader("Detalle del Producto")
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        with col_p1:
            cantidad = st.number_input("Cantidad:", min_value=0.0, step=1.0)
            unidad = st.selectbox("Unidad:", ["Cajones", "Piezas", "Kg", "Cajas"])
        with col_p2:
            producto = st.selectbox("Producto:", ["Brócoli", "Lechuga Orejona", "Lechuga Italiana", "Apio", "Otro"])
            if producto == "Otro": producto = st.text_input("Especifique Producto:")
            variedad = st.text_input("Variedad:")
        with col_p3:
            tabla = st.text_input("Tabla:")
            precio_u = st.number_input("Precio Unitario (Opcional):", min_value=0.0, step=0.5)
        with col_p4:
            archivo_rem = st.file_uploader("Adjuntar Remisión (PDF/JPG):", type=["pdf", "jpg", "png"])

        if st.button("Guardar Remisión"):
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO remisiones (folio, fecha, cliente, ciudad, chofer, camion, placas, hora_inicio, hora_salida, archivo_adjunto, nombre_archivo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (folio_input, fecha_remision, cliente_sel, ciudad_input, chofer, camion, placas, str(h_inicio), str(h_salida), archivo_rem.read() if archivo_rem else None, archivo_rem.name if archivo_rem else ""))
            
            cursor.execute('''
                INSERT INTO remision_detalle (folio_remision, cantidad, unidad, producto, variedad, tabla, precio_unitario)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (folio_input, cantidad, unidad, producto, variedad, tabla, precio_u))
            
            conn.commit()
            st.success(f"Remisión con Folio {folio_input} registrada correctamente.")

    with tab2:
        df_rem = pd.read_sql('''
            SELECT r.folio as Folio, r.fecha as Fecha, r.cliente as Cliente, r.ciudad as Ciudad,
                   d.cantidad as Cantidad, d.unidad as Unidad, d.producto as Producto, d.variedad as Variedad, d.tabla as Tabla,
                   r.chofer as Chofer, r.camion as Camion, r.placas as Placas, r.hora_inicio as "H. Inicio", r.hora_salida as "H. Salida"
            FROM remisiones r
            LEFT JOIN remision_detalle d ON r.folio = d.folio_remision
            ORDER BY r.folio DESC
        ''', conn)
        st.dataframe(df_rem, use_container_width=True)

# =========================================================
# MÓDULO 2: EVALUACIONES
# =========================================================
elif menu == "2. Evaluaciones":
    st.markdown('<div class="main-header">Evaluaciones de Calidad</div>', unsafe_allow_html=True)
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        rem_opts = df_rems['folio'].tolist() if not df_rems.empty else []
        
        folio_rem_sel = st.selectbox("Asociar a Folio de Remisión:", rem_opts)
        folio_eval = st.text_input("Folio de Evaluación de Cliente:")
        fecha_eval = st.date_input("Fecha de Evaluación:", datetime.now())
        periodo_calc = calcular_periodo_semanal(fecha_eval)
        st.info(f"Período Calculado: {periodo_calc}")

    with col_e2:
        grado1_cant = st.number_input("Cantidad Grado 1 (Kg/Piezas):", min_value=0.0, step=100.0)
        precio_eval = st.number_input("Precio ($):", min_value=0.0, step=0.50)
        obs_eval = st.text_area("Observaciones y Defectos:")
        archivo_eval = st.file_uploader("Cargar Evaluación (PDF/JPG):", type=["pdf", "jpg", "png"])

    if st.button("Guardar Evaluación"):
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO evaluaciones (folio_evaluacion, folio_remision, fecha, periodo, grado1_cantidad, precio_unitario, observaciones, archivo_adjunto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (folio_eval, folio_rem_sel, fecha_eval, periodo_calc, grado1_cant, precio_eval, obs_eval, archivo_eval.read() if archivo_eval else None))
        conn.commit()
        st.success("Evaluación guardada y vinculada correctamente.")

# =========================================================
# MÓDULO 3: FLETES
# =========================================================
elif menu == "3. Fletes":
    st.markdown('<div class="main-header">Control de Fletes y Transporte</div>', unsafe_allow_html=True)
    col_fl1, col_fl2 = st.columns(2)
    with col_fl1:
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        rem_opts = df_rems['folio'].tolist() if not df_rems.empty else []
        folio_rem_flete = st.selectbox("Seleccione Remisión:", rem_opts)
        paga_empresa = st.radio("Pago de Flete:", ["Cliente", "Empresa"])
    with col_fl2:
        if paga_empresa == "Empresa":
            factura_flete_pdf = st.file_uploader("Factura de Flete (PDF):", type=["pdf", "jpg", "png"])
            fecha_pago_flete = st.date_input("Fecha de Pago:", datetime.now())
            banco_flete = st.selectbox("Banco:", ["BBVA", "Banamex", "Santander", "Banorte", "Otro"])
        else:
            factura_flete_pdf = None
            fecha_pago_flete = None
            banco_flete = None

    if st.button("Guardar Registro de Flete"):
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO fletes (folio_remision, pagado_por, factura_pdf, fecha_pago, banco)
            VALUES (?, ?, ?, ?, ?)
        ''', (folio_rem_flete, paga_empresa, factura_flete_pdf.read() if factura_flete_pdf else None, fecha_pago_flete, banco_flete))
        conn.commit()
        st.success("Información de flete actualizada.")

# =========================================================
# MÓDULO 4: FACTURACIÓN CON EXTRACCIÓN AUTOMÁTICA (OCR)
# =========================================================
elif menu == "4. Facturación (OCR)":
    st.markdown('<div class="main-header">Módulo de Facturación y Carga Automática</div>', unsafe_allow_html=True)
    
    st.subheader("Carga Automática de Factura (PDF)")
    archivo_fac_auto = st.file_uploader("Suba la Factura en PDF para autocompletar el formulario:", type=["pdf"])
    
    # Valores extraídos por defecto
    f_folio, f_rfc, f_monto, f_fecha = "", "", 0.0, datetime.now().date()
    
    if archivo_fac_auto:
        datos_ocr = extraer_datos_pdf(archivo_fac_auto)
        if datos_ocr["texto_detectado"]:
            st.success("Lectura automática completada. Los campos se han llenado con los datos extraídos.")
            f_folio = datos_ocr["folio"]
            f_rfc = datos_ocr["rfc"]
            f_monto = datos_ocr["monto_total"]
            if datos_ocr["fecha"]:
                f_fecha = datos_ocr["fecha"]
        else:
            st.info("No se pudo extraer texto automático. Por favor, introduzca los datos manualmente.")

    st.markdown("---")
    col_fac1, col_fac2 = st.columns(2)
    with col_fac1:
        folio_fac = st.text_input("Folio de Factura:", value=f_folio)
        fecha_fac = st.date_input("Fecha de Emisión:", value=f_fecha)
        
        df_cli = pd.read_sql("SELECT nombre, rfc FROM clientes", conn)
        cli_list = df_cli['nombre'].tolist() if not df_cli.empty else []
        cliente_fac = st.selectbox("Cliente:", cli_list)
        
        rfc_fac = st.text_input("RFC Receptor:", value=f_rfc if f_rfc else (df_cli[df_cli['nombre'] == cliente_fac]['rfc'].values[0] if not df_cli.empty else ""))
        uuid_fac = st.text_input("Folio Fiscal (UUID):")
        monto_total = st.number_input("Monto Total ($):", value=f_monto, min_value=0.0, step=1000.0)

    with col_fac2:
        metodo_pago = st.selectbox("Método de Pago:", ["PPD - Pago en parcialidades o diferido", "PUE - Pago en una sola exhibición"])
        forma_pago = st.text_input("Forma de Pago:", value="99 Por definir")
        
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        rems_disponibles = df_rems['folio'].tolist() if not df_rems.empty else []
        rems_seleccionadas = st.multiselect("Asociar Remisión(es):", rems_disponibles)
        
        cp_pdf = st.file_uploader("Cargar Complemento de Pago (PDF) en caso de PPD:", type=["pdf"])
        nc_pdf = st.file_uploader("Cargar Nota de Crédito (PDF):", type=["pdf"])

    if st.button("Guardar Factura"):
        cursor = conn.cursor()
        str_rems = ",".join(map(str, rems_seleccionadas))
        estatus = "PAGADO" if "PUE" in metodo_pago or cp_pdf else "PENDIENTE DE PAGO"
        
        cursor.execute('''
            INSERT INTO facturas (folio_factura, fecha, cliente, rfc, folio_fiscal, metodo_pago, forma_pago, monto_total, remisiones_asociadas, estatus_pago, factura_pdf, complemento_pdf, nota_credito_pdf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (folio_fac, fecha_fac, cliente_fac, rfc_fac, uuid_fac, metodo_pago, forma_pago, monto_total, str_rems, estatus,
              archivo_fac_auto.read() if archivo_fac_auto else None,
              cp_pdf.read() if cp_pdf else None,
              nc_pdf.read() if nc_pdf else None))
        
        conn.commit()
        st.success("Factura guardada en la base de datos.")

# =========================================================
# MÓDULO 5: CONTROL DE ENVASES
# =========================================================
elif menu == "5. Control de Envases":
    st.markdown('<div class="main-header">Control de Envases, Cajas y Tarimas</div>', unsafe_allow_html=True)
    
    col_en1, col_en2 = st.columns(2)
    with col_en1:
        df_cli = pd.read_sql("SELECT nombre FROM clientes", conn)
        cli_list = df_cli['nombre'].tolist() if not df_cli.empty else []
        cliente_env = st.selectbox("Cliente:", cli_list)
        tipo_mov = st.radio("Tipo de Movimiento:", ["Salida (Entregado)", "Entrada (Devolución)"])
        
    with col_en2:
        tipo_envase = st.selectbox("Tipo de Envase:", ["Cajón Blanco (50 Kg)", "Caja MR Lucky", "Caja Plástica", "Tarima Madera"])
        cant_envase = st.number_input("Cantidad (Piezas):", min_value=1, step=10)
        obs_env = st.text_input("Observaciones / Folio de Referencia:")

    if st.button("Registrar Envase"):
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO control_envases (fecha, cliente, tipo_movimiento, tipo_envase, cantidad, observacion)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now().date(), cliente_env, tipo_mov, tipo_envase, cant_envase, obs_env))
        conn.commit()
        st.success("Movimiento de envase registrado.")

    st.markdown("---")
    st.subheader("Historial de Envases")
    df_env = pd.read_sql("SELECT id as ID, fecha as Fecha, cliente as Cliente, tipo_movimiento as Movimiento, tipo_envase as Envase, cantidad as Cantidad, observacion as Observación FROM control_envases ORDER BY id DESC", conn)
    st.dataframe(df_env, use_container_width=True)

# =========================================================
# MÓDULO 6: REPORTE MATRIZ
# =========================================================
elif menu == "6. Reporte MATRIZ":
    st.markdown('<div class="main-header">Reporte Consolidado MATRIZ</div>', unsafe_allow_html=True)
    
    col_m1, col_m2 = st.columns(2)
    with col_m1: f_inicio = st.date_input("Fecha Inicio:", datetime.now() - timedelta(days=30))
    with col_m2: f_fin = st.date_input("Fecha Fin:", datetime.now())
        
    query_matriz = '''
        SELECT 
            r.folio as "Remisión",
            r.fecha as "Fecha Remisión",
            r.cliente as "Cliente",
            rd.producto as "Producto",
            rd.cantidad as "Cant. Enviada",
            e.folio_evaluacion as "Folio Eval.",
            e.periodo as "PERÍODO",
            e.grado1_cantidad as "Cant. Grado 1",
            e.precio_unitario as "Precio Unit.",
            (e.grado1_cantidad * e.precio_unitario) as "Importe Eval. $",
            f.pagado_por as "Flete Pagado Por",
            fac.folio_factura as "Folio Factura",
            fac.monto_total as "Monto Factura $",
            fac.estatus_pago as "Estatus Pago"
        FROM remisiones r
        LEFT JOIN remision_detalle rd ON r.folio = rd.folio_remision
        LEFT JOIN evaluaciones e ON r.folio = e.folio_remision
        LEFT JOIN fletes f ON r.folio = f.folio_remision
        LEFT JOIN facturas fac ON INSTR(fac.remisiones_asociadas, CAST(r.folio AS TEXT)) > 0
        WHERE r.fecha BETWEEN ? AND ?
        ORDER BY r.folio DESC
    '''
    
    df_matriz = pd.read_sql(query_matriz, conn, params=(f_inicio, f_fin))
    st.dataframe(df_matriz, use_container_width=True)
    
    buf_matriz = io.BytesIO()
    with pd.ExcelWriter(buf_matriz, engine='xlsxwriter') as writer:
        df_matriz.to_excel(writer, sheet_name='MATRIZ', index=False)
        
    st.download_button(
        label="Descargar Reporte MATRIZ (Excel)",
        data=buf_matriz.getvalue(),
        file_name=f"Reporte_MATRIZ_{f_inicio}_al_{f_fin}.xlsx",
        mime="application/vnd.ms-excel"
    )

# =========================================================
# CONFIGURACIÓN
# =========================================================
elif menu == "Configuración":
    st.markdown('<div class="main-header">Catálogo de Clientes</div>', unsafe_allow_html=True)
    df_c = pd.read_sql("SELECT id as ID, nombre as Nombre, rfc as RFC, domicilio as Domicilio, ciudad as Ciudad FROM clientes", conn)
    st.dataframe(df_c, use_container_width=True)
