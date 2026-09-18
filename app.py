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
    .stApp {
        background-color: #F8FAFC;
        color: #0F172A;
        font-family: 'Segoe UI', Roboto, sans-serif;
    }
    section[data-testid="stSidebar"] {
        background-color: #F1F5F9 !important;
        border-right: 1px solid #CBD5E1;
    }
    .web-header {
        background-color: #FFFFFF;
        padding: 18px 24px;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        border-left: 5px solid #3B82F6;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 20px;
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
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 15px;
        padding-bottom: 5px;
        border-bottom: 2px solid #E2E8F0;
    }
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
# BASE DE DATOS Y ESTRUCTURAS DE TABLAS
# ---------------------------------------------------------
def get_connection():
    return sqlite3.connect("sistema_pedregal.db", check_same_thread=False)

def inicializar_bd():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Usuarios y Roles
    cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE,
        password TEXT,
        nombre TEXT,
        rol TEXT
    )''')
    
    # Clientes
    cursor.execute('''CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        nombre TEXT UNIQUE, 
        rfc TEXT, 
        domicilio TEXT, 
        ciudad TEXT,
        telefono TEXT,
        contacto TEXT
    )''')
    
    # Proveedores de Flete
    cursor.execute('''CREATE TABLE IF NOT EXISTS proveedores_fletes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        rfc TEXT,
        telefono TEXT,
        contacto TEXT
    )''')
    
    # Insumos / Fertilizantes y Agroquímicos Aportados por Clientes
    cursor.execute('''CREATE TABLE IF NOT EXISTS insumos_agroquimicos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha DATE,
        cliente TEXT,
        producto TEXT,
        unidad TEXT,
        cantidad_ingresada REAL,
        costo_unitario REAL,
        monto_total REAL,
        observaciones TEXT
    )''')
    
    # Remisiones
    cursor.execute('''CREATE TABLE IF NOT EXISTS remisiones (
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
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS remision_detalle (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        folio_remision INTEGER, 
        cantidad REAL, 
        unidad TEXT, 
        producto TEXT, 
        variedad TEXT, 
        tabla TEXT, 
        precio_unitario REAL, 
        FOREIGN KEY (folio_remision) REFERENCES remisiones (folio)
    )''')
    
    # Evaluaciones
    cursor.execute('''CREATE TABLE IF NOT EXISTS evaluaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        folio_evaluacion TEXT, 
        folio_remision INTEGER, 
        fecha DATE, 
        periodo TEXT, 
        grado1_cantidad REAL, 
        precio_unitario REAL, 
        observaciones TEXT, 
        archivo_adjunto BLOB
    )''')
    
    # Fletes
    cursor.execute('''CREATE TABLE IF NOT EXISTS fletes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        folio_remision INTEGER, 
        pagado_por TEXT, 
        proveedor TEXT,
        monto REAL,
        factura_pdf BLOB, 
        fecha_pago DATE, 
        banco TEXT
    )''')
    
    # Facturas
    cursor.execute('''CREATE TABLE IF NOT EXISTS facturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        folio_factura TEXT, 
        fecha DATE, 
        cliente TEXT, 
        rfc TEXT, 
        folio_fiscal TEXT, 
        metodo_pago TEXT, 
        forma_pago TEXT, 
        monto_subtotal REAL,
        descuento_insumos REAL,
        monto_total REAL, 
        remisiones_asociadas TEXT, 
        insumo_aplicado TEXT,
        fecha_pago DATE, 
        banco TEXT, 
        estatus_pago TEXT, 
        factura_pdf BLOB
    )''')
    
    # Envases
    cursor.execute('''CREATE TABLE IF NOT EXISTS control_envases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        fecha DATE, 
        cliente TEXT, 
        tipo_movimiento TEXT, 
        tipo_envase TEXT, 
        cantidad INTEGER, 
        observacion TEXT
    )''')

    # Inserción de Usuario Administrador Inicial si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (usuario, password, nombre, rol) VALUES ('admin', 'admin123', 'Administrador Principal', 'Administrador')")
        cursor.execute("INSERT INTO usuarios (usuario, password, nombre, rol) VALUES ('operador', '12345', 'Operador de Campo', 'Operador')")

    # Inserción de Catálogos Iniciales
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, rfc, domicilio, ciudad) VALUES ('LEONALI', 'LEO030827903', 'FABRICA EL LEON No. SN, EL LEON, C.P.74360, Puebla', 'Puebla')")
    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, rfc, domicilio, ciudad) VALUES ('FRESCOS DON-GU', 'FDG101010AAA', 'San Miguel de Allende', 'San Miguel de Allende')")
    cursor.execute("INSERT OR IGNORE INTO proveedores_fletes (nombre, rfc) VALUES ('TRANSPORTES DEL BAJIO', 'TBA900101XXX')")
    
    conn.commit()

inicializar_bd()
conn = get_connection()

def exportar_excel(dataframe, nombre_hoja):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        dataframe.to_excel(writer, sheet_name=nombre_hoja, index=False)
    return output.getvalue()

# ---------------------------------------------------------
# SISTEMA DE LOGIN Y CONTROL DE SESIÓN
# ---------------------------------------------------------
if 'usuario_logueado' not in st.session_state:
    st.session_state['usuario_logueado'] = None
if 'rol_usuario' not in st.session_state:
    st.session_state['rol_usuario'] = None
if 'nombre_usuario' not in st.session_state:
    st.session_state['nombre_usuario'] = None

st.sidebar.markdown("### **INICIO DE SESIÓN**")

if st.session_state['usuario_logueado'] is None:
    user_input = st.sidebar.text_input("Usuario:")
    pass_input = st.sidebar.text_input("Contraseña:", type="password")
    if st.sidebar.button("Ingresar"):
        c = conn.cursor()
        c.execute("SELECT usuario, nombre, rol FROM usuarios WHERE usuario=? AND password=?", (user_input, pass_input))
        res = c.fetchone()
        if res:
            st.session_state['usuario_logueado'] = res[0]
            st.session_state['nombre_usuario'] = res[1]
            st.session_state['rol_usuario'] = res[2]
            st.sidebar.success(f"Bienvenido, {res[1]}")
            st.rerun()
        else:
            st.sidebar.error("Usuario o contraseña incorrectos")
    st.stop()
else:
    st.sidebar.markdown(f"**Usuario:** {st.session_state['nombre_usuario']}")
    st.sidebar.markdown(f"**Rol:** `{st.session_state['rol_usuario']}`")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state['usuario_logueado'] = None
        st.session_state['rol_usuario'] = None
        st.session_state['nombre_usuario'] = None
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### **LOGO DE EMPRESA**")
logo_empresa = st.sidebar.file_uploader("Cargar Logo (PNG/JPG):", type=["png", "jpg", "jpeg"])

# Configuración del menú según permisos
opciones_menu = [
    "Dashboard / Resumen Completo",
    "1. Generador Personalizado de Reportes",
    "2. Catálogos (Clientes / Proveedores)",
    "3. Agroquímicos y Fertilizantes (Entradas)",
    "4. Remisiones (Autocompletar)",
    "5. Evaluaciones de Calidad",
    "6. Control de Fletes",
    "7. Facturación y Descuentos",
    "8. Control de Envases",
    "9. Reporte MATRIZ Consolidado"
]

if st.session_state['rol_usuario'] == "Administrador":
    opciones_menu.append("10. Gestión de Usuarios y Accesos")

st.sidebar.markdown("---")
seccion_activa = st.sidebar.selectbox("Seleccione Módulo:", opciones_menu)

# ---------------------------------------------------------
# ENCABEZADO CON LOGO
# ---------------------------------------------------------
col_logo, col_head = st.columns([1, 5]) if logo_empresa else (None, st.container())
if logo_empresa:
    with col_logo: st.image(logo_empresa, width=110)
    with col_head:
        st.markdown("""
            <div class="web-header">
                <div>
                    <div class="web-title">PEDREGAL LOS VERA, S.A. DE C.V.</div>
                    <div class="web-subtitle">Sistema Empresarial de Administración, Facturación y Control Agrícola</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
        <div class="web-header">
            <div>
                <div class="web-title">PEDREGAL LOS VERA, S.A. DE C.V.</div>
                <div class="web-subtitle">Sistema Empresarial de Administración, Facturación y Control Agrícola</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# =========================================================
# DASHBOARD
# =========================================================
if seccion_activa == "Dashboard / Resumen Completo":
    st.markdown('<div class="section-title">Resumen Ejecutivo General</div>', unsafe_allow_html=True)
    
    df_fact = pd.read_sql("SELECT SUM(monto_total) as tot, SUM(CASE WHEN estatus_pago = 'PAGADO' THEN monto_total ELSE 0 END) as pag, SUM(CASE WHEN estatus_pago != 'PAGADO' THEN monto_total ELSE 0 END) as pend FROM facturas", conn)
    df_rem = pd.read_sql("SELECT COUNT(folio) as tot_rem FROM remisiones", conn)
    df_prod = pd.read_sql("SELECT SUM(cantidad) as tot_cant FROM remision_detalle", conn)
    df_fletes = pd.read_sql("SELECT SUM(monto) as tot_fletes FROM fletes WHERE pagado_por = 'Empresa'", conn)

    m_tot = df_fact['tot'].values[0] or 0.0
    m_pag = df_fact['pag'].values[0] or 0.0
    m_pend = df_fact['pend'].values[0] or 0.0
    tot_rem = df_rem['tot_rem'].values[0] or 0
    tot_cant = df_prod['tot_cant'].values[0] or 0.0
    tot_flete = df_fletes['tot_fletes'].values[0] or 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Facturación Total", f"${m_tot:,.2f}")
    col2.metric("Total Cobrado", f"${m_pag:,.2f}")
    col3.metric("Por Cobrar (Pendiente)", f"${m_pend:,.2f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Total de Remisiones Emitidas", f"{tot_rem} remisiones")
    col5.metric("Volumen Total Enviado", f"{tot_cant:,.1f} Kg/Pzs")
    col6.metric("Gasto Total de Fletes", f"${tot_flete:,.2f}")

# =========================================================
# REQUERIMIENTO 1: GENERADOR PERSONALIZADO DE REPORTES
# =========================================================
elif seccion_activa == "1. Generador Personalizado de Reportes":
    st.markdown('<div class="section-title">Generador de Reportes a la Medida para Dirección</div>', unsafe_allow_html=True)
    st.info("Seleccione las fechas y marque únicamente las columnas que su jefe o cliente requiere exportar en el archivo de Excel.")

    col_r1, col_r2 = st.columns(2)
    with col_r1: f_ini_rep = st.date_input("Fecha Inicio:", datetime.now() - timedelta(days=30))
    with col_r2: f_fin_rep = st.date_input("Fecha Fin:", datetime.now())

    # Carga de Matriz completa
    query_base = '''
        SELECT 
            r.folio as "Remisión", 
            r.fecha as "Fecha Remisión", 
            r.cliente as "Cliente",
            r.ciudad as "Ciudad Destino",
            r.chofer as "Chofer",
            r.camion as "Camión",
            r.placas as "Placas",
            rd.producto as "Producto", 
            rd.variedad as "Variedad",
            rd.tabla as "Tabla/Lote",
            rd.cantidad as "Cantidad Enviada", 
            rd.unidad as "Unidad",
            rd.precio_unitario as "Precio Unitario Campo $",
            e.folio_evaluacion as "Folio Evaluación",
            e.grado1_cantidad as "Cant. Grado 1",
            e.precio_unitario as "Precio Unit. Final $",
            fac.folio_factura as "Factura", 
            fac.monto_subtotal as "Subtotal Factura $",
            fac.descuento_insumos as "Descuento Agroquímicos $",
            fac.monto_total as "Monto Total Factura $",
            fac.estatus_pago as "Estatus Pago Factura",
            fac.fecha_pago as "Fecha Pago Factura",
            fac.banco as "Banco Cobro",
            f.pagado_por as "Flete Pagado Por",
            f.proveedor as "Proveedor Flete",
            f.monto as "Monto Flete $",
            f.fecha_pago as "Fecha Pago Flete",
            f.banco as "Banco Pago Flete"
        FROM remisiones r
        LEFT JOIN remision_detalle rd ON r.folio = rd.folio_remision
        LEFT JOIN evaluaciones e ON r.folio = e.folio_remision
        LEFT JOIN fletes f ON r.folio = f.folio_remision
        LEFT JOIN facturas fac ON INSTR(fac.remisiones_asociadas, CAST(r.folio AS TEXT)) > 0
        WHERE r.fecha BETWEEN ? AND ? ORDER BY r.folio DESC
    '''
    df_completo = pd.read_sql(query_base, conn, params=(f_ini_rep, f_fin_rep))

    columnas_disponibles = list(df_completo.columns)
    
    st.markdown("#### Seleccione los campos a incluir en el reporte:")
    columnas_seleccionadas = st.multiselect(
        "Campos Visibles en Excel:",
        options=columnas_disponibles,
        default=["Remisión", "Fecha Remisión", "Cliente", "Producto", "Cantidad Enviada", "Factura", "Monto Total Factura $", "Estatus Pago Factura"]
    )

    if columnas_seleccionadas:
        df_filtrado = df_completo[columnas_seleccionadas]
        st.markdown("##### Previsualización del Reporte Personalizado")
        st.dataframe(df_filtrado, use_container_width=True)
        
        st.download_button(
            "📥 Descargar Reporte Personalizado en Excel",
            data=exportar_excel(df_filtrado, "Reporte_Especial"),
            file_name=f"Reporte_Especial_{f_ini_rep}_al_{f_fin_rep}.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.warning("Seleccione al menos una columna para generar el reporte.")

# =========================================================
# SECCIÓN 2: CATÁLOGOS
# =========================================================
elif seccion_activa == "2. Catálogos (Clientes / Proveedores)":
    st.markdown('<div class="section-title">Administración de Catálogos</div>', unsafe_allow_html=True)
    tab_cli, tab_prov = st.tabs(["Catálogo de Clientes", "Catálogo de Proveedores de Flete"])
    
    with tab_cli:
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_nombre = st.text_input("Nombre / Razón Social del Cliente:")
            c_rfc = st.text_input("RFC del Cliente:")
            c_domicilio = st.text_input("Domicilio Fiscal:")
        with col_c2:
            c_ciudad = st.text_input("Ciudad / Municipio:")
            c_tel = st.text_input("Teléfono de Contacto:")
            c_contacto = st.text_input("Persona de Contacto:")

        if st.button("Guardar Cliente"):
            if c_nombre:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO clientes (nombre, rfc, domicilio, ciudad, telefono, contacto) VALUES (?, ?, ?, ?, ?, ?)",
                               (c_nombre, c_rfc, c_domicilio, c_ciudad, c_tel, c_contacto))
                conn.commit()
                st.success(f"Cliente '{c_nombre}' guardado exitosamente.")
            else: st.warning("Ingrese el nombre del cliente.")

        st.dataframe(pd.read_sql("SELECT id as ID, nombre as Nombre, rfc as RFC, ciudad as Ciudad, domicilio as Domicilio FROM clientes", conn), use_container_width=True)

    with tab_prov:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pf_nombre = st.text_input("Nombre / Línea de Transportes:")
            pf_rfc = st.text_input("RFC Proveedor:")
        with col_p2:
            pf_tel = st.text_input("Teléfono de Atención:")
            pf_contacto = st.text_input("Nombre de Ejecutivo / Contacto:")

        if st.button("Guardar Proveedor de Flete"):
            if pf_nombre:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO proveedores_fletes (nombre, rfc, telefono, contacto) VALUES (?, ?, ?, ?)",
                               (pf_nombre, pf_rfc, pf_tel, pf_contacto))
                conn.commit()
                st.success(f"Proveedor '{pf_nombre}' guardado exitosamente.")

        st.dataframe(pd.read_sql("SELECT id as ID, nombre as Nombre, rfc as RFC, telefono as Teléfono FROM proveedores_fletes", conn), use_container_width=True)

# =========================================================
# REQUERIMIENTO 3: INSUMOS, FERTILIZANTES Y AGROQUÍMICOS
# =========================================================
elif seccion_activa == "3. Agroquímicos y Fertilizantes (Entradas)":
    st.markdown('<div class="section-title">Registro de Agroquímicos y Fertilizantes Aportados por Clientes</div>', unsafe_allow_html=True)
    st.info("Registre los insumos entregados por los clientes que posteriormente se descontarán de las facturas de venta.")

    col_i1, col_i2 = st.columns(2)
    with col_i1:
        fecha_ins = st.date_input("Fecha de Recepción:", datetime.now())
        df_cli = pd.read_sql("SELECT nombre FROM clientes", conn)
        cliente_ins = st.selectbox("Cliente que Provee:", df_cli['nombre'].tolist() if not df_cli.empty else [])
        prod_ins = st.text_input("Nombre del Agroquímico / Fertilizante:")
        unid_ins = st.selectbox("Unidad de Medida:", ["Litros (L)", "Kilogramos (Kg)", "Sacos", "Bultos", "Piezas"])

    with col_i2:
        cant_ins = st.number_input("Cantidad Entregada:", min_value=0.0, step=10.0)
        costo_u_ins = st.number_input("Costo Unitario ($):", min_value=0.0, step=10.0)
        monto_tot_ins = cant_ins * costo_u_ins
        st.markdown(f"**Valor Total Insumo:** `${monto_tot_ins:,.2f}`")
        obs_ins = st.text_area("Observaciones / Folio Recepción:")

    if st.button("Registrar Insumo en Inventario"):
        if prod_ins and cant_ins > 0:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO insumos_agroquimicos (fecha, cliente, producto, unidad, cantidad_ingresada, costo_unitario, monto_total, observaciones)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (fecha_ins, cliente_ins, prod_ins, unid_ins, cant_ins, costo_u_ins, monto_tot_ins, obs_ins))
            conn.commit()
            st.success(f"Insumo '{prod_ins}' guardado con valor de ${monto_tot_ins:,.2f}.")
        else:
            st.warning("Ingrese la información completa del insumo.")

    st.markdown("---")
    st.markdown("#### Historial de Insumos / Fertilizantes Registrados")
    df_ins_ver = pd.read_sql("SELECT id as ID, fecha as Fecha, cliente as Cliente, producto as Producto, unidad as Unidad, cantidad_ingresada as Cantidad, costo_unitario as 'Costo U. $', monto_total as 'Total$' FROM insumos_agroquimicos ORDER BY id DESC", conn)
    st.dataframe(df_ins_ver, use_container_width=True)

# =========================================================
# SECCIÓN 4: REMISIONES
# =========================================================
elif seccion_activa == "4. Remisiones (Autocompletar)":
    st.markdown('<div class="section-title">Gestión de Remisiones</div>', unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Registro / Carga de Remisión", "Consecutivo e Histórico"])
    
    with tab1:
        archivo_rem_auto = st.file_uploader("Adjuntar documento de Remisión (PDF):", type=["pdf", "png", "jpg"])
        r_folio, r_fecha = 1001, datetime.now().date()
        if archivo_rem_auto:
            datos_auto = extraer_datos_pdf(archivo_rem_auto)
            if datos_auto["texto_detectado"]:
                st.success("Datos extraídos correctamente del documento.")
                if datos_auto["folio"].isdigit(): r_folio = int(datos_auto["folio"])
                if datos_auto["fecha"]: r_fecha = datos_auto["fecha"]

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            folio_input = st.number_input("Número de Folio:", value=r_folio, step=1)
            fecha_rem = st.date_input("Fecha:", value=r_fecha)
            df_cli = pd.read_sql("SELECT nombre, ciudad FROM clientes", conn)
            cli_list = df_cli['nombre'].tolist() if not df_cli.empty else []
            cliente_sel = st.selectbox("Cliente:", cli_list)
            ciudad_default = df_cli[df_cli['nombre'] == cliente_sel]['ciudad'].values[0] if (not df_cli.empty and cliente_sel in cli_list) else ""
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
            st.success(f"Remisión {folio_input} guardada.")

    with tab2:
        df_rem = pd.read_sql('''
            SELECT r.folio as Folio, r.fecha as Fecha, r.cliente as Cliente, r.ciudad as Ciudad,
                   d.cantidad as Cantidad, d.unidad as Unidad, d.producto as Producto, d.variedad as Variedad, d.tabla as Tabla
            FROM remisiones r LEFT JOIN remision_detalle d ON r.folio = d.folio_remision ORDER BY r.folio DESC
        ''', conn)
        st.dataframe(df_rem, use_container_width=True)

# =========================================================
# SECCIÓN 5: EVALUACIONES
# =========================================================
elif seccion_activa == "5. Evaluaciones de Calidad":
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
        st.success("Evaluación guardada.")

# =========================================================
# SECCIÓN 6: FLETES
# =========================================================
elif seccion_activa == "6. Control de Fletes":
    st.markdown('<div class="section-title">Control de Fletes y Transporte</div>', unsafe_allow_html=True)
    col_fl1, col_fl2 = st.columns(2)
    with col_fl1:
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        rem_opts = df_rems['folio'].tolist() if not df_rems.empty else []
        folio_rem_flete = st.selectbox("Seleccionar Remisión:", rem_opts)
        paga_empresa = st.radio("Flete pagado por:", ["Cliente", "Empresa"])
        df_pf = pd.read_sql("SELECT nombre FROM proveedores_fletes", conn)
        proveedor_flete = st.selectbox("Proveedor / Línea de Flete:", df_pf['nombre'].tolist() if not df_pf.empty else [])

    with col_fl2:
        monto_flete = st.number_input("Monto / Costo del Flete ($):", min_value=0.0, step=100.0)
        fecha_pago_flete = st.date_input("Fecha Pago:", datetime.now())
        banco_flete = st.selectbox("Banco / Forma de Pago:", ["BBVA", "Banamex", "Santander", "Banorte", "Efectivo", "Otro"])

    if st.button("Guardar Flete"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO fletes (folio_remision, pagado_por, proveedor, monto, fecha_pago, banco)
                          VALUES (?, ?, ?, ?, ?, ?)''', (folio_rem_flete, paga_empresa, proveedor_flete, monto_flete, fecha_pago_flete, banco_flete))
        conn.commit()
        st.success("Flete registrado.")

# =========================================================
# SECCIÓN 7: FACTURACIÓN Y DESCUENTO DE AGROQUÍMICOS
# =========================================================
elif seccion_activa == "7. Facturación y Descuentos":
    st.markdown('<div class="section-title">Módulo de Facturación y Descuento de Insumos</div>', unsafe_allow_html=True)
    
    archivo_fac = st.file_uploader("Subir PDF de Factura para autocompletar:", type=["pdf"])
    f_folio, f_rfc, f_monto, f_fecha = "", "", 0.0, datetime.now().date()
    
    if archivo_fac:
        datos = extraer_datos_pdf(archivo_fac)
        if datos["texto_detectado"]:
            st.success("Datos extraídos correctamente.")
            f_folio, f_rfc, f_monto = datos["folio"], datos["rfc"], datos["monto_total"]
            if datos["fecha"]: f_fecha = datos["fecha"]

    col_fac1, col_fac2 = st.columns(2)
    with col_fac1:
        folio_fac = st.text_input("Folio Factura:", value=f_folio)
        fecha_fac = st.date_input("Fecha Emisión:", value=f_fecha)
        df_cli = pd.read_sql("SELECT nombre, rfc FROM clientes", conn)
        cliente_fac = st.selectbox("Cliente:", df_cli['nombre'].tolist() if not df_cli.empty else [])
        rfc_fac = st.text_input("RFC Receptor:", value=f_rfc)
        remision_asoc = st.text_input("Remisión(es) Asociada(s) (ej: 1001, 1002):")

    with col_fac2:
        monto_subtotal = st.number_input("Subtotal de la Venta ($):", value=f_monto, min_value=0.0)
        
        # Selección e integración del descuento de agroquímicos del cliente
        st.markdown("---")
        st.markdown("##### **Descuento de Fertilizantes / Agroquímicos**")
        df_ins_cli = pd.read_sql("SELECT id, producto, monto_total FROM insumos_agroquimicos WHERE cliente=?", conn, params=(cliente_fac,))
        
        opciones_insumo = ["Ninguno / Sin Descuento"]
        dict_insumos = {}
        for index, row in df_ins_cli.iterrows():
            lbl = f"{row['producto']} - Total Disponible: ${row['monto_total']:,.2f}"
            opciones_insumo.append(lbl)
            dict_insumos[lbl] = row['monto_total']

        insumo_sel = st.selectbox("Aplicar Descuento de Insumo Aportado:", opciones_insumo)
        
        descuento_aplicado = 0.0
        if insumo_sel != "Ninguno / Sin Descuento":
            descuento_aplicado = st.number_input("Monto a Descontar ($):", value=float(dict_insumos[insumo_sel]), min_value=0.0)

        monto_final_neto = max(0.0, monto_subtotal - descuento_aplicado)
        st.markdown(f"### **Total Neto a Facturar:** `${monto_final_neto:,.2f}`")

    st.markdown("---")
    col_f3, col_f4 = st.columns(2)
    with col_f3:
        metodo_pago = st.selectbox("Método de Pago:", ["PPD - Diferido", "PUE - Exhibición única"])
        estatus_pago = st.selectbox("Estatus de Pago:", ["PENDIENTE DE PAGO", "PAGADO"])
    with col_f4:
        fecha_pago_fac = st.date_input("Fecha de Pago Recibido:", datetime.now())
        banco_fac = st.selectbox("Banco Recibido:", ["BBVA", "Banamex", "Santander", "Banorte", "Otro"])

    if st.button("Guardar Factura"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO facturas (folio_factura, fecha, cliente, rfc, monto_subtotal, descuento_insumos, monto_total, remisiones_asociadas, insumo_aplicado, metodo_pago, estatus_pago, fecha_pago, banco)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                          (folio_fac, fecha_fac, cliente_fac, rfc_fac, monto_subtotal, descuento_aplicado, monto_final_neto, remision_asoc, insumo_sel, metodo_pago, estatus_pago,
                           fecha_pago_fac if estatus_pago == "PAGADO" else None, banco_fac if estatus_pago == "PAGADO" else None))
        conn.commit()
        st.success("Factura y descuento registrados correctamente.")

# =========================================================
# SECCIÓN 8: ENVASES
# =========================================================
elif seccion_activa == "8. Control de Envases":
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
# SECCIÓN 9: REPORTE MATRIZ CONSOLIDADO
# =========================================================
elif seccion_activa == "9. Reporte MATRIZ Consolidado":
    st.markdown('<div class="section-title">Reporte Consolidado MATRIZ</div>', unsafe_allow_html=True)
    col_m1, col_m2 = st.columns(2)
    with col_m1: f_inicio = st.date_input("Desde:", datetime.now() - timedelta(days=30))
    with col_m2: f_fin = st.date_input("Hasta:", datetime.now())

    query_matriz = '''
        SELECT 
            r.folio as "Remisión", 
            r.fecha as "Fecha Remisión", 
            r.cliente as "Cliente",
            rd.producto as "Producto", 
            rd.cantidad as "Cantidad Enviada", 
            e.grado1_cantidad as "Cant. Grado 1",
            e.precio_unitario as "Precio Unit. $",
            fac.folio_factura as "Factura", 
            fac.monto_subtotal as "Subtotal $",
            fac.descuento_insumos as "Desc. Agroquímicos $",
            fac.monto_total as "Total Factura $",
            fac.estatus_pago as "Estatus Pago",
            fac.fecha_pago as "Fecha Pago Factura",
            f.pagado_por as "Flete Pagado Por",
            f.proveedor as "Proveedor Flete",
            f.monto as "Monto Flete $"
        FROM remisiones r
        LEFT JOIN remision_detalle rd ON r.folio = rd.folio_remision
        LEFT JOIN evaluaciones e ON r.folio = e.folio_remision
        LEFT JOIN fletes f ON r.folio = f.folio_remision
        LEFT JOIN facturas fac ON INSTR(fac.remisiones_asociadas, CAST(r.folio AS TEXT)) > 0
        WHERE r.fecha BETWEEN ? AND ? ORDER BY r.folio DESC
    '''
    df_matriz = pd.read_sql(query_matriz, conn, params=(f_inicio, f_fin))
    st.dataframe(df_matriz, use_container_width=True)
    st.download_button("Exportar MATRIZ Completa a Excel", data=exportar_excel(df_matriz, "MATRIZ"), file_name=f"Reporte_MATRIZ_{f_inicio}_al_{f_fin}.xlsx", mime="application/vnd.ms-excel")

# =========================================================
# REQUERIMIENTO 2: GESTIÓN DE USUARIOS Y ACCESOS
# =========================================================
elif seccion_activa == "10. Gestión de Usuarios y Accesos":
    st.markdown('<div class="section-title">Administración de Usuarios y Accesos al Sistema</div>', unsafe_allow_html=True)
    st.info("Agregue o modifique las cuentas de usuario con inicio de sesión para restringir o permitir la operación en la plataforma.")

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        nuevo_user = st.text_input("Nombre de Usuario (Login):")
        nuevo_pass = st.text_input("Contraseña de Acceso:", type="password")
    with col_u2:
        nombre_real = st.text_input("Nombre Completo:")
        rol_asig = st.selectbox("Rol / Permiso:", ["Operador", "Administrador"])

    if st.button("Crear / Actualizar Usuario"):
        if nuevo_user and nuevo_pass:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO usuarios (usuario, password, nombre, rol) VALUES (?, ?, ?, ?)",
                           (nuevo_user, nuevo_pass, nombre_real, rol_asig))
            conn.commit()
            st.success(f"Usuario '{nuevo_user}' registrado exitosamente con rol de {rol_asig}.")
        else:
            st.warning("Ingrese usuario y contraseña válidos.")

    st.markdown("---")
    st.markdown("#### Usuarios Activos en el Sistema")
    df_users = pd.read_sql("SELECT id as ID, usuario as 'Usuario (Login)', nombre as 'Nombre Completo', rol as 'Rol' FROM usuarios", conn)
    st.dataframe(df_users, use_container_width=True)
