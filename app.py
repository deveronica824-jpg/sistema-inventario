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
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
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
    
    # Usuarios
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
    
    # Proveedores
    cursor.execute('''CREATE TABLE IF NOT EXISTS proveedores_fletes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        rfc TEXT,
        telefono TEXT,
        contacto TEXT
    )''')
    
    # Insumos / Agroquímicos
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
        monto_subtotal REAL,
        descuento_insumos REAL,
        monto_total REAL, 
        remisiones_asociadas TEXT, 
        insumo_aplicado TEXT,
        metodo_pago TEXT,
        estatus_pago TEXT, 
        fecha_pago DATE, 
        banco TEXT
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

    # Datos base
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO usuarios (usuario, password, nombre, rol) VALUES ('admin', 'admin123', 'Administrador Principal', 'Administrador')")
        cursor.execute("INSERT INTO usuarios (usuario, password, nombre, rol) VALUES ('operador', '12345', 'Operador de Campo', 'Operador')")

    cursor.execute("INSERT OR IGNORE INTO clientes (nombre, rfc, domicilio, ciudad) VALUES ('LEONALI', 'LEO030827903', 'FABRICA EL LEON No. SN', 'Puebla')")
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
# SISTEMA DE LOGIN Y SESIÓN
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
logo_empresa = st.sidebar.file_uploader("Cargar Logo (PNG/JPG):", type=["png", "jpg", "jpeg"])

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

# Encabezado principal
st.markdown("""
    <div class="web-header">
        <div class="web-title">PEDREGAL LOS VERA, S.A. DE C.V.</div>
        <div class="web-subtitle">Sistema Empresarial de Administración, Facturación y Control Agrícola</div>
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

    col1, col2, col3 = st.columns(3)
    col1.metric("Facturación Total", f"${(df_fact['tot'].values[0] or 0.0):,.2f}")
    col2.metric("Total Cobrado", f"${(df_fact['pag'].values[0] or 0.0):,.2f}")
    col3.metric("Por Cobrar (Pendiente)", f"${(df_fact['pend'].values[0] or 0.0):,.2f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Remisiones Emitidas", f"{df_rem['tot_rem'].values[0] or 0}")
    col5.metric("Volumen Total Enviado", f"{(df_prod['tot_cant'].values[0] or 0.0):,.1f} Kg/Pzs")
    col6.metric("Gasto Total Fletes", f"${(df_fletes['tot_fletes'].values[0] or 0.0):,.2f}")

# =========================================================
# 1. GENERADOR PERSONALIZADO DE REPORTES (CORREGIDO)
# =========================================================
elif seccion_activa == "1. Generador Personalizado de Reportes":
    st.markdown('<div class="section-title">Generador de Reportes a la Medida para Dirección</div>', unsafe_allow_html=True)
    
    col_r1, col_r2 = st.columns(2)
    with col_r1: f_ini_rep = st.date_input("Fecha Inicio:", datetime.now() - timedelta(days=30))
    with col_r2: f_fin_rep = st.date_input("Fecha Fin:", datetime.now())

    # Formatear fechas a string de forma segura
    f_ini_str = f_ini_rep.strftime('%Y-%m-%d')
    f_fin_str = f_fin_rep.strftime('%Y-%m-%d')

    query_base = '''
        SELECT 
            r.folio as "Remisión", 
            r.fecha as "Fecha Remisión", 
            r.cliente as "Cliente",
            r.ciudad as "Ciudad Destino",
            rd.producto as "Producto", 
            rd.cantidad as "Cantidad Enviada", 
            rd.unidad as "Unidad",
            e.folio_evaluacion as "Folio Evaluación",
            e.grado1_cantidad as "Cant. Grado 1",
            fac.folio_factura as "Factura", 
            fac.monto_total as "Monto Total Factura $",
            fac.estatus_pago as "Estatus Pago Factura",
            f.proveedor as "Proveedor Flete",
            f.monto as "Monto Flete $"
        FROM remisiones r
        LEFT JOIN remision_detalle rd ON r.folio = rd.folio_remision
        LEFT JOIN evaluaciones e ON r.folio = e.folio_remision
        LEFT JOIN fletes f ON r.folio = f.folio_remision
        LEFT JOIN facturas fac ON INSTR(fac.remisiones_asociadas, CAST(r.folio AS TEXT)) > 0
        WHERE DATE(r.fecha) BETWEEN DATE(?) AND DATE(?) 
        ORDER BY r.folio DESC
    '''
    
    try:
        with conn:
            df_completo = pd.read_sql(query_base, conn, params=(f_ini_str, f_fin_str))

        columnas_disponibles = list(df_completo.columns)
        columnas_seleccionadas = st.multiselect(
            "Campos a incluir en el reporte:",
            options=columnas_disponibles,
            default=["Remisión", "Fecha Remisión", "Cliente", "Producto", "Cantidad Enviada", "Factura", "Monto Total Factura $", "Estatus Pago Factura"]
        )

        if columnas_seleccionadas:
            df_filtrado = df_completo[columnas_seleccionadas]
            st.dataframe(df_filtrado, use_container_width=True)
            
            st.download_button(
                "📥 Descargar Reporte Personalizado en Excel",
                data=exportar_excel(df_filtrado, "Reporte_Especial"),
                file_name=f"Reporte_{f_ini_str}_al_{f_fin_str}.xlsx",
                mime="application/vnd.ms-excel"
            )
    except Exception as e:
        st.error(f"Error al generar la matriz de datos: {e}")

# =========================================================
# 2. CATÁLOGOS
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
                st.success(f"Cliente '{c_nombre}' guardado.")
                st.rerun()

        st.dataframe(pd.read_sql("SELECT id as ID, nombre as Nombre, rfc as RFC, ciudad as Ciudad FROM clientes", conn), use_container_width=True)

    with tab_prov:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pf_nombre = st.text_input("Línea de Transportes:")
            pf_rfc = st.text_input("RFC Proveedor:")
        with col_p2:
            pf_tel = st.text_input("Teléfono:")
            pf_contacto = st.text_input("Contacto:")

        if st.button("Guardar Proveedor de Flete"):
            if pf_nombre:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO proveedores_fletes (nombre, rfc, telefono, contacto) VALUES (?, ?, ?, ?)",
                               (pf_nombre, pf_rfc, pf_tel, pf_contacto))
                conn.commit()
                st.success(f"Proveedor '{pf_nombre}' guardado.")
                st.rerun()

        st.dataframe(pd.read_sql("SELECT id as ID, nombre as Nombre, rfc as RFC, telefono as Teléfono FROM proveedores_fletes", conn), use_container_width=True)

# =========================================================
# 3. AGROQUÍMICOS Y FERTILIZANTES
# =========================================================
elif seccion_activa == "3. Agroquímicos y Fertilizantes (Entradas)":
    st.markdown('<div class="section-title">Registro de Agroquímicos Aportados por Clientes</div>', unsafe_allow_html=True)

    col_i1, col_i2 = st.columns(2)
    with col_i1:
        fecha_ins = st.date_input("Fecha de Recepción:", datetime.now())
        df_cli = pd.read_sql("SELECT nombre FROM clientes", conn)
        cliente_ins = st.selectbox("Cliente que Provee:", df_cli['nombre'].tolist() if not df_cli.empty else [])
        prod_ins = st.text_input("Nombre del Agroquímico / Fertilizante:")
        unid_ins = st.selectbox("Unidad:", ["Litros (L)", "Kilogramos (Kg)", "Sacos", "Piezas"])

    with col_i2:
        cant_ins = st.number_input("Cantidad Entregada:", min_value=0.0, step=10.0)
        costo_u_ins = st.number_input("Costo Unitario ($):", min_value=0.0, step=10.0)
        monto_tot_ins = cant_ins * costo_u_ins
        st.markdown(f"**Valor Total Insumo:** `${monto_tot_ins:,.2f}`")
        obs_ins = st.text_area("Observaciones:")

    if st.button("Registrar Insumo en Inventario"):
        if prod_ins and cant_ins > 0:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO insumos_agroquimicos (fecha, cliente, producto, unidad, cantidad_ingresada, costo_unitario, monto_total, observaciones)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (fecha_ins.strftime('%Y-%m-%d'), cliente_ins, prod_ins, unid_ins, cant_ins, costo_u_ins, monto_tot_ins, obs_ins))
            conn.commit()
            st.success("Insumo registrado correctamente.")
            st.rerun()

    st.markdown("---")
    st.dataframe(pd.read_sql("SELECT id as ID, fecha as Fecha, cliente as Cliente, producto as Producto, cantidad_ingresada as Cantidad, monto_total as 'Total $' FROM insumos_agroquimicos ORDER BY id DESC", conn), use_container_width=True)

# =========================================================
# 4. REMISIONES
# =========================================================
elif seccion_activa == "4. Remisiones (Autocompletar)":
    st.markdown('<div class="section-title">Gestión de Remisiones</div>', unsafe_allow_html=True)
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        folio_input = st.number_input("Número de Folio:", value=1001, step=1)
        fecha_rem = st.date_input("Fecha:", value=datetime.now())
        df_cli = pd.read_sql("SELECT nombre, ciudad FROM clientes", conn)
        cli_list = df_cli['nombre'].tolist() if not df_cli.empty else []
        cliente_sel = st.selectbox("Cliente:", cli_list)
        ciudad_input = st.text_input("Ciudad Destino:")

    with col_f2:
        chofer = st.text_input("Chofer:")
        camion = st.text_input("Camión:")
        placas = st.text_input("Placas:")

    st.markdown("#### Detalle del Producto")
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        cantidad = st.number_input("Cantidad:", min_value=0.0, step=1.0)
        unidad = st.selectbox("Unidad:", ["Cajones", "Piezas", "Kg", "Cajas"])
    with col_p2:
        producto = st.selectbox("Producto:", ["Brócoli", "Lechuga Orejona", "Lechuga Italiana", "Apio", "Otro"])
        variedad = st.text_input("Variedad:")
    with col_p3:
        tabla = st.text_input("Tabla / Lote:")
        precio_u = st.number_input("Precio Unitario ($):", min_value=0.0, step=0.5)

    if st.button("Guardar Remisión"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO remisiones (folio, fecha, cliente, ciudad, chofer, camion, placas)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                          (folio_input, fecha_rem.strftime('%Y-%m-%d'), cliente_sel, ciudad_input, chofer, camion, placas))
        cursor.execute('''INSERT INTO remision_detalle (folio_remision, cantidad, unidad, producto, variedad, tabla, precio_unitario)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''', (folio_input, cantidad, unidad, producto, variedad, tabla, precio_u))
        conn.commit()
        st.success(f"Remisión {folio_input} guardada.")

    st.markdown("---")
    st.dataframe(pd.read_sql("SELECT r.folio as Folio, r.fecha as Fecha, r.cliente as Cliente, d.producto as Producto, d.cantidad as Cantidad FROM remisiones r LEFT JOIN remision_detalle d ON r.folio = d.folio_remision ORDER BY r.folio DESC", conn), use_container_width=True)

# =========================================================
# 5. EVALUACIONES
# =========================================================
elif seccion_activa == "5. Evaluaciones de Calidad":
    st.markdown('<div class="section-title">Evaluaciones de Calidad</div>', unsafe_allow_html=True)
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        folio_rem_sel = st.selectbox("Asociar a Folio Remisión:", df_rems['folio'].tolist() if not df_rems.empty else [])
        folio_eval = st.text_input("Folio Evaluación Cliente:")
        fecha_eval = st.date_input("Fecha Evaluación:", datetime.now())
    with col_e2:
        grado1_cant = st.number_input("Cantidad Grado 1 (Kg/Pzs):", min_value=0.0, step=100.0)
        precio_eval = st.number_input("Precio Unitario Final ($):", min_value=0.0, step=0.50)

    if st.button("Guardar Evaluación"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO evaluaciones (folio_evaluacion, folio_remision, fecha, grado1_cantidad, precio_unitario)
                          VALUES (?, ?, ?, ?, ?)''', (folio_eval, folio_rem_sel, fecha_eval.strftime('%Y-%m-%d'), grado1_cant, precio_eval))
        conn.commit()
        st.success("Evaluación guardada.")

# =========================================================
# 6. CONTROL DE FLETES
# =========================================================
elif seccion_activa == "6. Control de Fletes":
    st.markdown('<div class="section-title">Control de Fletes y Transporte</div>', unsafe_allow_html=True)
    col_fl1, col_fl2 = st.columns(2)
    with col_fl1:
        df_rems = pd.read_sql("SELECT folio FROM remisiones ORDER BY folio DESC", conn)
        folio_rem_flete = st.selectbox("Seleccionar Remisión:", df_rems['folio'].tolist() if not df_rems.empty else [])
        paga_empresa = st.radio("Flete pagado por:", ["Cliente", "Empresa"])
        df_pf = pd.read_sql("SELECT nombre FROM proveedores_fletes", conn)
        proveedor_flete = st.selectbox("Proveedor de Flete:", df_pf['nombre'].tolist() if not df_pf.empty else [])

    with col_fl2:
        monto_flete = st.number_input("Monto / Costo Flete ($):", min_value=0.0, step=100.0)
        fecha_pago_flete = st.date_input("Fecha Pago:", datetime.now())
        banco_flete = st.selectbox("Banco / Forma de Pago:", ["BBVA", "Banamex", "Santander", "Banorte", "Efectivo"])

    if st.button("Guardar Flete"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO fletes (folio_remision, pagado_por, proveedor, monto, fecha_pago, banco)
                          VALUES (?, ?, ?, ?, ?, ?)''', (folio_rem_flete, paga_empresa, proveedor_flete, monto_flete, fecha_pago_flete.strftime('%Y-%m-%d'), banco_flete))
        conn.commit()
        st.success("Flete registrado.")

# =========================================================
# 7. FACTURACIÓN Y DESCUENTOS
# =========================================================
elif seccion_activa == "7. Facturación y Descuentos":
    st.markdown('<div class="section-title">Módulo de Facturación y Descuento de Insumos</div>', unsafe_allow_html=True)
    
    col_fac1, col_fac2 = st.columns(2)
    with col_fac1:
        folio_fac = st.text_input("Folio Factura:")
        fecha_fac = st.date_input("Fecha Emisión:", datetime.now())
        df_cli = pd.read_sql("SELECT nombre, rfc FROM clientes", conn)
        cliente_fac = st.selectbox("Cliente:", df_cli['nombre'].tolist() if not df_cli.empty else [])
        rfc_fac = st.text_input("RFC Receptor:")
        remision_asoc = st.text_input("Remisión(es) Asociada(s) (ej: 1001, 1002):")

    with col_fac2:
        monto_subtotal = st.number_input("Subtotal de la Venta ($):", min_value=0.0)
        
        df_ins_cli = pd.read_sql("SELECT id, producto, monto_total FROM insumos_agroquimicos WHERE cliente=?", conn, params=(cliente_fac,))
        opciones_insumo = ["Ninguno / Sin Descuento"]
        dict_insumos = {}
        for index, row in df_ins_cli.iterrows():
            lbl = f"{row['producto']} - Total Disponible: ${row['monto_total']:,.2f}"
            opciones_insumo.append(lbl)
            dict_insumos[lbl] = row['monto_total']

        insumo_sel = st.selectbox("Aplicar Descuento de Insumo:", opciones_insumo)
        
        descuento_aplicado = 0.0
        if insumo_sel != "Ninguno / Sin Descuento":
            descuento_aplicado = st.number_input("Monto a Descontar ($):", value=float(dict_insumos[insumo_sel]), min_value=0.0)

        monto_final_neto = max(0.0, monto_subtotal - descuento_aplicado)
        st.markdown(f"### **Total Neto:** `${monto_final_neto:,.2f}`")

    col_f3, col_f4 = st.columns(2)
    with col_f3:
        metodo_pago = st.selectbox("Método de Pago:", ["PPD - Diferido", "PUE - Exhibición única"])
        estatus_pago = st.selectbox("Estatus de Pago:", ["PENDIENTE DE PAGO", "PAGADO"])
    with col_f4:
        fecha_pago_fac = st.date_input("Fecha de Pago Recibido:", datetime.now())
        banco_fac = st.selectbox("Banco Recibido:", ["BBVA", "Banamex", "Santander", "Banorte"])

    if st.button("Guardar Factura"):
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO facturas (folio_factura, fecha, cliente, rfc, monto_subtotal, descuento_insumos, monto_total, remisiones_asociadas, insumo_aplicado, metodo_pago, estatus_pago, fecha_pago, banco)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                          (folio_fac, fecha_fac.strftime('%Y-%m-%d'), cliente_fac, rfc_fac, monto_subtotal, descuento_aplicado, monto_final_neto, remision_asoc, insumo_sel, metodo_pago, estatus_pago,
                           fecha_pago_fac.strftime('%Y-%m-%d') if estatus_pago == "PAGADO" else None, banco_fac if estatus_pago == "PAGADO" else None))
        conn.commit()
        st.success("Factura registrada exitosamente.")

# =========================================================
# 8. CONTROL DE ENVASES
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
                          VALUES (?, ?, ?, ?, ?)''', (datetime.now().strftime('%Y-%m-%d'), cliente_env, tipo_mov, tipo_envase, cant_envase))
        conn.commit()
        st.success("Movimiento guardado.")

# =========================================================
# 9. REPORTE MATRIZ CONSOLIDADO (CORREGIDO)
# =========================================================
elif seccion_activa == "9. Reporte MATRIZ Consolidado":
    st.markdown('<div class="section-title">Reporte Consolidado MATRIZ</div>', unsafe_allow_html=True)
    col_m1, col_m2 = st.columns(2)
    with col_m1: f_inicio = st.date_input("Desde:", datetime.now() - timedelta(days=30))
    with col_m2: f_fin = st.date_input("Hasta:", datetime.now())

    # Formatear fechas a string de forma segura
    f_ini_mat_str = f_inicio.strftime('%Y-%m-%d')
    f_fin_mat_str = f_fin.strftime('%Y-%m-%d')

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
            f.pagado_por as "Flete Pagado Por",
            f.proveedor as "Proveedor Flete",
            f.monto as "Monto Flete $"
        FROM remisiones r
        LEFT JOIN remision_detalle rd ON r.folio = rd.folio_remision
        LEFT JOIN evaluaciones e ON r.folio = e.folio_remision
        LEFT JOIN fletes f ON r.folio = f.folio_remision
        LEFT JOIN facturas fac ON INSTR(fac.remisiones_asociadas, CAST(r.folio AS TEXT)) > 0
        WHERE DATE(r.fecha) BETWEEN DATE(?) AND DATE(?) 
        ORDER BY r.folio DESC
    '''
    try:
        with conn:
            df_matriz = pd.read_sql(query_matriz, conn, params=(f_ini_mat_str, f_fin_mat_str))
        
        st.dataframe(df_matriz, use_container_width=True)
        st.download_button(
            "Exportar MATRIZ Completa a Excel", 
            data=exportar_excel(df_matriz, "MATRIZ"), 
            file_name=f"MATRIZ_{f_ini_mat_str}_al_{f_fin_mat_str}.xlsx", 
            mime="application/vnd.ms-excel"
        )
    except Exception as e:
        st.error(f"Error al cargar el Reporte MATRIZ: {e}")

# =========================================================
# 10. GESTIÓN DE USUARIOS Y ACCESOS
# =========================================================
elif seccion_activa == "10. Gestión de Usuarios y Accesos":
    st.markdown('<div class="section-title">Administración de Usuarios y Accesos al Sistema</div>', unsafe_allow_html=True)

    col_u1, col_u2 = st.columns(2)
    with col_u1:
        nuevo_user = st.text_input("Nombre de Usuario (Login):")
        nuevo_pass = st.text_input("Contraseña:", type="password")
    with col_u2:
        nombre_real = st.text_input("Nombre Completo:")
        rol_asig = st.selectbox("Rol / Permiso:", ["Operador", "Administrador"])

    if st.button("Crear / Actualizar Usuario"):
        if nuevo_user and nuevo_pass:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO usuarios (usuario, password, nombre, rol) VALUES (?, ?, ?, ?)",
                           (nuevo_user, nuevo_pass, nombre_real, rol_asig))
            conn.commit()
            st.success(f"Usuario '{nuevo_user}' registrado exitosamente.")
            st.rerun()
        else:
            st.warning("Ingrese usuario y contraseña válidos.")

    st.markdown("---")
    st.dataframe(pd.read_sql("SELECT id as ID, usuario as 'Usuario (Login)', nombre as 'Nombre Completo', rol as 'Rol' FROM usuarios", conn), use_container_width=True)
