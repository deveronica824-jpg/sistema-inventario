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
# CONFIGURACIÓN DE PÁGINA Y ESTILOS SUAVES Y CLAROS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Gestión - Pedregal Los Vera",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* Fondo general en azul pastel extra claro */
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
        font-family: 'Segoe UI', Roboto, sans-serif;
    }
    
    /* Personalización de la Barra Lateral (Sidebar) */
    section[data-testid="stSidebar"] {
        background-color: #F1F5F9 !important;
        border-right: 1px solid #CBD5E1;
    }
    
    /* Encabezado Principal Web */
    .web-header {
        background-color: #FFFFFF;
        padding: 18px 24px;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        border-left: 5px solid #3B82F6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .web-title {
        font-size: 24px;
        font-weight: 800;
        color: #1E3A8A;
        margin: 0;
    }
    .web-subtitle {
        font-size: 13px;
        color: #475569;
        margin-top: 2px;
    }
    
    /* Titulares de Sección */
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 15px;
        padding-bottom: 5px;
        border-bottom: 2px solid #E2E8F0;
    }
    
    /* Estilo de Campos de Entrada: Gris claro suave y Azul Pastel sin tonos oscuros */
    div[data-baseweb="input"] > div, 
    div[data-baseweb="select"] > div,
    textarea {
        background-color: #EFF6FF !important;
        border: 1px solid #BFDBFE !important;
        border-radius: 6px !important;
        color: #0F172A !important;
        font-size: 15px !important;
    }
    div[data-baseweb="input"] input {
        color: #0F172A !important;
        font-size: 15px !important;
    }
    label {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #1E293B !important;
    }
    
    /* Botones de Acción principales (Azul Corporativo Claro) */
    .stButton>button {
        background-color: #2563EB;
        color: #FFFFFF;
        border-radius: 6px;
        border: none;
        font-size: 15px;
        font-weight: 600;
        padding: 8px 16px;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #1D4ED8;
        color: #FFFFFF;
    }
    
    /* Tarjetas de Métricas en el Dashboard */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #DBEAFE;
        border-radius: 8px;
        padding: 12px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    div[data-testid="stMetricLabel"] {
        color: #475569;
        font-size: 13px;
        font-weight: 600;
    }
    div[data-testid="stMetricValue"] {
        color: #1E3A8A;
        font-size: 22px;
        font-weight: 700;
    }

    /* Impresión */
    @media print {
        body * { visibility: hidden; }
        .printable-area, .printable-area * { visibility: visible; }
        .printable-area { position: absolute; left: 0; top: 0; width: 100%; }
        .no-print { display: none !important; }
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# EXTRACCIÓN AUTOMÁTICA DE DATOS (OCR)
# ---------------------------------------------------------
def extraer_datos_pdf(archivo_pdf):
    datos = {"folio": "", "rfc": "", "fecha": None, "monto_total": 0.0, "texto_detectado": False}
    if not PDF_PARSER_AVAILABLE:
        return datos
    try:
        with pdfplumber.open(archivo_pdf) as pdf:
            texto = ""
            for pagina in pdf.pages:
                texto += pagina.extract_text() or ""
            if texto.strip():
                datos["texto_detectado"] = True
                match_rfc = re.search(r'[A-Z&Ñ]{3,4}\d{6}[A-V1-9][A-Z1-9][0-9A]', texto)
                if match_rfc: datos["rfc"] = match_rfc.group(0)
                
                match_monto = re.search(r'(?:TOTAL|Total|Monto Total)\s*\$?\s*([\d,]+\.\d{2})', texto)
                if match_monto: datos["monto_total"] = float(match_monto.group(1).replace(',', ''))
                
                match_folio = re.search(r'(?:Folio|FOLIO|Factura|Remision)\s*[:#]?\s*(\w+)', texto)
                if match_folio: datos["folio"] = match_folio.group(1)
                
                match_fecha = re.search(r'(\d{2,4}[-/\.]\d{1,2}[-/\.]\d{2,4})', texto)
                if match_fecha:
                    f_str = match_fecha.group(1)
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
                        try:
                            datos["fecha"] = datetime.strptime(f_str, fmt).date()
                            break
                        except ValueError: pass
    except Exception:
        pass
    return datos

# ---------------------------------------------------------
# BASE DE DATOS
# ---------------------------------------------------------
def get_connection():
    return sqlite3.connect("sistema_pedregal.db", check_same_thread=False)

def inicializar_bd():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, rfc TEXT, domicilio TEXT, ciudad TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS remisiones (folio INTEGER PRIMARY KEY, fecha DATE, cliente TEXT, ciudad TEXT, chofer TEXT, camion TEXT, placas TEXT, hora_inicio TEXT, hora_salida TEXT, archivo_adjunto BLOB, nombre_archivo TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS remision_detalle (id INTEGER PRIMARY KEY AUTOINCREMENT, folio_remision INTEGER, cantidad REAL, unidad TEXT, producto TEXT, variedad TEXT, tabla TEXT, precio_unitario REAL, FOREIGN KEY (folio_remision) REFERENCES remisiones (folio))')
    cursor.execute('CREATE TABLE IF NOT EXISTS evaluaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, folio_evaluacion TEXT, folio_remision INTEGER, fecha DATE, periodo TEXT, grado1_cantidad REAL, precio_unitario REAL, observaciones TEXT, archivo_adjunto BLOB)')
    cursor.execute('CREATE TABLE IF NOT EXISTS fletes (id INTEGER PRIMARY KEY AUTOINCREMENT, folio_remision INTEGER, pagado_por TEXT, factura_pdf BLOB, fecha_pago DATE, banco TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS facturas (id INTEGER PRIMARY KEY AUTOINCREMENT, folio_factura TEXT, fecha DATE, cliente TEXT, rfc TEXT, folio_fiscal TEXT, metodo_pago TEXT, forma_pago TEXT, monto_total REAL, remisiones_asociadas TEXT, fecha_pago DATE, banco TEXT, estatus_pago TEXT, factura_pdf BLOB, complemento_pdf BLOB, nota_credito_pdf BLOB)')
    cursor.execute('CREATE TABLE IF NOT EXISTS control_envases (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, tipo_movimiento TEXT, tipo_envase TEXT, cantidad INTEGER, observacion TEXT)')
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, rfc, domicilio, ciudad) VALUES ('LEONALI', 'LEO030827903', 'FABRICA EL LEON No. SN, EL LEON, C.P.74360, Puebla', 'Puebla')")
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, rfc, domicilio, ciudad) VALUES ('FRESCOS DON-GU', 'FDG101010AAA', 'San Miguel de Allende', 'San Miguel de Allende')")
    conn.commit()

inicializar_bd()
conn = get_connection()

def exportar_excel(dataframe, nombre_hoja):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        dataframe.to_excel(writer, sheet_name=nombre_hoja, index=False)
    return output.getvalue()

# ---------------------------------------------------------
# ENCABEZADO
# ---------------------------------------------------------
st.markdown("""
    <div class="web-header">
        <div class="web-title">PEDREGAL LOS VERA, S.A. DE C.V.</div>
        <div class="web-subtitle">Sistema Empresarial de Administración, Facturación y Control Agrícola</div>
    </div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# MENÚ DESPLEGABLE EN LA BARRA LATERAL IZQUIERDA
# ---------------------------------------------------------
st.sidebar.markdown("### **MENÚ DEL SISTEMA**")
seccion_activa = st.sidebar.selectbox(
    "Seleccione Módulo:",
    [
        "Dashboard / Resumen",
        "1. Remisiones (Autocompletar)",
        "2. Evaluaciones",
        "3. Fletes",
        "4. Facturación (Autocompletar)",
        "5. Control de Envases",
        "6. Reporte MATRIZ"
    ]
)

# =========================================================
# SECCIÓN: DASHBOARD
# =========================================================
if seccion_activa == "Dashboard / Resumen":
    st.markdown('<div class="section-title">Resumen Ejecutivo</div>', unsafe_allow_html=True)
    
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
    col_m4.metric("Promedio Grado 1", f"{g1_avg:,.1f} Kg")

    st.markdown("---")
    st.subheader("Cuentas por Cobrar Pendientes")
    df_pend = pd.read_sql("SELECT folio_factura as 'Folio Factura', fecha as Fecha, cliente as Cliente, monto_total as Total, estatus_pago as Estatus FROM facturas WHERE estatus_pago != 'PAGADO'", conn)
    st.dataframe(df_pend, use_container_width=True)

# =========================================================
# SECCIÓN 1: REMISIONES (CON AUTOCOMPLETADO)
# =========================================================
elif seccion_activa == "1. Remisiones (Autocompletar)":
    st.markdown('<div class="section-title">Gestión de Remisiones</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Registro / Carga de Remisión", "Consecutivo y Exportación"])
    
    with tab1:
        st.info("Cargue un archivo PDF/Imagen de la remisión para extraer los datos en automático o complete el formulario de forma manual.")
        archivo_rem_auto = st.file_uploader("Adjuntar documento de Remisión (PDF):", type=["pdf", "png", "jpg"])
        
        # Extracción automática
        r_folio, r_fecha = 1001, datetime.now().date()
        if archivo_rem_auto:
            datos_auto = extraer_datos_pdf(archivo_rem_auto)
            if datos_auto["texto_detectado"]:
                st.success("Información del documento leída correctamente.")
                if datos_auto["folio"].isdigit():
                    r_folio = int(datos_auto["folio"])
                if datos_auto["fecha"]:
                    r_fecha = datos_auto["fecha"]

        st.markdown("---")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            folio_input = st.number_input("Número de Folio:", value=r_folio, step=1)
            fecha_rem = st.date_input("Fecha:", value=r_fecha)
            df_cli = pd.read_sql("SELECT nombre, ciudad FROM clientes", conn)
            cli_list = df_cli['nombre'].tolist() if not df_cli.empty else []
            cliente_sel = st.selectbox("Cliente:", cli_list + ["+ Nuevo Cliente"])
            
            if cliente_sel == "+ Nuevo Cliente":
                cliente_sel = st.text_input("Nombre del Cliente:")
                ciudad_input = st.text_input("Ciudad:")
            else:
                ciudad_default = df_cli[df_cli['nombre'] == cliente_sel]['ciudad'].values[0] if not df_cli.empty else ""
                ciudad_input = st.text_input("Ciudad:", value=ciudad_default)

        with col_f2:
            chofer = st.text_input("Chofer:")
            camion = st.text_input("Camión:")
            placas = st.text_input("Placas:")
            col_t1, col_t2 = st.columns(2)
            with col_t1: h_inicio = st.time_input("Hora Inicio:")
            with col_t2: h_salida = st.time_input("Hora Salida:")

        st.markdown("#### Detalle del Producto")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            cantidad = st.number_input("Cantidad:", min_value=0.0, step=1.0)
            unidad = st.selectbox("Unidad:", ["Cajones", "Piezas", "Kg", "Cajas"])
        with col_p2:
            producto = st.selectbox("Producto:", ["Brócoli", "Lechuga Orejona", "Lechuga Italiana", "Apio", "Otro"])
            if producto == "Otro": producto = st.text_input("Especifique Producto:")
            variedad = st.text_input("Variedad:")
        with col_p3:
            tabla = st.text_input("Tabla:")
            precio_u = st.number_input("Precio Unitario ($):", min_value=0.0, step=0.5)

        if st.button("Guardar Remisión"):
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO remisiones (folio, fecha, cliente, ciudad, chofer, camion, placas, hora_inicio, hora_salida, archivo_adjunto, nombre_archivo)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (folio_input, fecha_rem, cliente_sel, ciudad_input, chofer, camion, placas, str(h_inicio), str(h_salida),
                               archivo_rem_auto.read() if archivo_rem_auto else None, archivo_rem_auto.name if archivo_rem_auto else ""))
            cursor.execute('''INSERT INTO remision_detalle (folio_remision, cantidad, unidad, producto, variedad, tabla, precio_unitario)
                              VALUES (?, ?, ?, ?, ?, ?, ?)''', (folio_input, cantidad, unidad, producto, variedad, tabla, precio_u))
            conn.commit()
            st.success(f"Remisión {folio_input} guardada correctamente.")

    with tab2:
        df_rem = pd.read_sql('''
            SELECT r.folio as Folio, r.fecha as Fecha, r.cliente as Cliente, r.ciudad as Ciudad,
                   d.cantidad as Cantidad, d.unidad as Unidad, d.producto as Producto, d.variedad as Variedad, d.tabla as Tabla,
                   r.chofer as Chofer, r.camion as Camion
            FROM remisiones r LEFT JOIN remision_detalle d ON r.folio = d.folio_remision ORDER BY r.folio DESC
        ''', conn)
        
        st.dataframe(df_rem, use_container_width=True)
        
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            st.download_button("Exportar Remisiones a Excel", data=exportar_excel(df_rem, "Remisiones"), file_name="Remisiones.xlsx", mime="application/vnd.ms-excel")
        with col_exp2:
            if st.button("Vista de Impresión"):
                st.components.v1.html("<script>window.print();</script>", height=0)

# =========================================================
# SECCIÓN 2: EVALUACIONES
# =========================================================
elif seccion_activa == "2. Evaluaciones":
    st.markdown('<div class="section-title">Evaluaciones de Calidad</div>', unsafe_allow_html=True)
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        rem_opts = df_rems['folio'].tolist() if not df_rems.empty else []
        folio_rem_sel = st.selectbox("Asociar a Folio Remisión:", rem_opts)
        folio_eval = st.text_input("Folio Evaluación Cliente:")
        fecha_eval = st.date_input("Fecha Evaluación:", datetime.now())
    with col_e2:
        grado1_cant = st.number_input("Cantidad Grado 1 (Kg/Pzs):", min_value=0.0, step=100.0)
        precio_eval = st.number_input("Precio ($):", min_value=0.0, step=0.50)
        obs_eval = st.text_area("Observaciones:")

    if st.button("Guardar Evaluación"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO evaluaciones (folio_evaluacion, folio_remision, fecha, grado1_cantidad, precio_unitario, observaciones)
                          VALUES (?, ?, ?, ?, ?, ?)''', (folio_eval, folio_rem_sel, fecha_eval, grado1_cant, precio_eval, obs_eval))
        conn.commit()
        st.success("Evaluación vinculada con éxito.")

# =========================================================
# SECCIÓN 3: FLETES
# =========================================================
elif seccion_activa == "3. Fletes":
    st.markdown('<div class="section-title">Control de Fletes</div>', unsafe_allow_html=True)
    col_fl1, col_fl2 = st.columns(2)
    with col_fl1:
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        rem_opts = df_rems['folio'].tolist() if not df_rems.empty else []
        folio_rem_flete = st.selectbox("Seleccionar Remisión:", rem_opts)
        paga_empresa = st.radio("Flete pagado por:", ["Cliente", "Empresa"])
    with col_fl2:
        fecha_pago_flete = st.date_input("Fecha Pago:", datetime.now())
        banco_flete = st.selectbox("Banco:", ["BBVA", "Banamex", "Santander", "Banorte", "Otro"])

    if st.button("Guardar Flete"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO fletes (folio_remision, pagado_por, fecha_pago, banco)
                          VALUES (?, ?, ?, ?)''', (folio_rem_flete, paga_empresa, fecha_pago_flete, banco_flete))
        conn.commit()
        st.success("Flete registrado correctamente.")

# =========================================================
# SECCIÓN 4: FACTURACIÓN
# =========================================================
elif seccion_activa == "4. Facturación (Autocompletar)":
    st.markdown('<div class="section-title">Módulo de Facturación</div>', unsafe_allow_html=True)
    
    archivo_fac = st.file_uploader("Subir PDF de Factura para autocompletar:", type=["pdf"])
    f_folio, f_rfc, f_monto, f_fecha = "", "", 0.0, datetime.now().date()
    
    if archivo_fac:
        datos = extraer_datos_pdf(archivo_fac)
        if datos["texto_detectado"]:
            st.success("Datos extraídos automáticamente del documento.")
            f_folio, f_rfc, f_monto = datos["folio"], datos["rfc"], datos["monto_total"]
            if datos["fecha"]: f_fecha = datos["fecha"]

    col_fac1, col_fac2 = st.columns(2)
    with col_fac1:
        folio_fac = st.text_input("Folio Factura:", value=f_folio)
        fecha_fac = st.date_input("Fecha Emisión:", value=f_fecha)
        df_cli = pd.read_sql("SELECT nombre, rfc FROM clientes", conn)
        cliente_fac = st.selectbox("Cliente:", df_cli['nombre'].tolist() if not df_cli.empty else [])
        rfc_fac = st.text_input("RFC Receptor:", value=f_rfc)
    with col_fac2:
        uuid_fac = st.text_input("Folio Fiscal (UUID):")
        monto_total = st.number_input("Monto Total ($):", value=f_monto, min_value=0.0)
        metodo_pago = st.selectbox("Método de Pago:", ["PPD - Diferido", "PUE - Exhibición única"])

    if st.button("Guardar Factura"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO facturas (folio_factura, fecha, cliente, rfc, folio_fiscal, metodo_pago, monto_total, estatus_pago)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (folio_fac, fecha_fac, cliente_fac, rfc_fac, uuid_fac, metodo_pago, monto_total, "PAGADO" if "PUE" in metodo_pago else "PENDIENTE"))
        conn.commit()
        st.success("Factura guardada exitosamente.")

# =========================================================
# SECCIÓN 5: CONTROL DE ENVASES
# =========================================================
elif seccion_activa == "5. Control de Envases":
    st.markdown('<div class="section-title">Control de Envases y Cajas</div>', unsafe_allow_html=True)
    col_en1, col_en2 = st.columns(2)
    with col_en1:
        df_cli = pd.read_sql("SELECT nombre FROM clientes", conn)
        cliente_env = st.selectbox("Cliente:", df_cli['nombre'].tolist() if not df_cli.empty else [])
        tipo_mov = st.radio("Movimiento:", ["Salida (Entregado)", "Entrada (Devolución)"])
    with col_en2:
        tipo_envase = st.selectbox("Tipo Envase:", ["Cajón Blanco (50 Kg)", "Caja MR Lucky", "Caja Plástica", "Tarima Madera"])
        cant_envase = st.number_input("Cantidad:", min_value=1, step=10)

    if st.button("Registrar Envase"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO control_envases (fecha, cliente, tipo_movimiento, tipo_envase, cantidad)
                          VALUES (?, ?, ?, ?, ?)''', (datetime.now().date(), cliente_env, tipo_mov, tipo_envase, cant_envase))
        conn.commit()
        st.success("Movimiento registrado.")

# =========================================================
# SECCIÓN 6: REPORTES
# =========================================================
elif seccion_activa == "6. Reporte MATRIZ":
    st.markdown('<div class="section-title">Reporte General MATRIZ</div>', unsafe_allow_html=True)
    
    col_m1, col_m2 = st.columns(2)
    with col_m1: f_inicio = st.date_input("Desde:", datetime.now() - timedelta(days=30))
    with col_m2: f_fin = st.date_input("Hasta:", datetime.now())

    query_matriz = '''
        SELECT r.folio as "Remisión", r.fecha as "Fecha", r.cliente as "Cliente",
               rd.producto as "Producto", rd.cantidad as "Cantidad", e.grado1_cantidad as "Grado 1",
               e.precio_unitario as "Precio", fac.folio_factura as "Factura", fac.monto_total as "Monto $"
        FROM remisiones r
        LEFT JOIN remision_detalle rd ON r.folio = rd.folio_remision
        LEFT JOIN evaluaciones e ON r.folio = e.folio_remision
        LEFT JOIN facturas fac ON INSTR(fac.remisiones_asociadas, CAST(r.folio AS TEXT)) > 0
        WHERE r.fecha BETWEEN ? AND ? ORDER BY r.folio DESC
    '''
    df_matriz = pd.read_sql(query_matriz, conn, params=(f_inicio, f_fin))
    
    st.dataframe(df_matriz, use_container_width=True)
    
    col_rep1, col_rep2 = st.columns(2)
    with col_rep1:
        st.download_button("Exportar Reporte MATRIZ a Excel", data=exportar_excel(df_matriz, "MATRIZ"), file_name=f"Reporte_MATRIZ_{f_inicio}_al_{f_fin}.xlsx", mime="application/vnd.ms-excel")
    with col_rep2:
        if st.button("Imprimir Reporte Matriz"):
            st.components.v1.html("<script>window.print();</script>", height=0)
