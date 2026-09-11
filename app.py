import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Órdenes e Inventario",
    page_icon="📦",
    layout="wide"
)

# Conexión a Base de Datos persistente
def get_connection():
    conn = sqlite3.connect("sistema.db", check_same_thread=False)
    return conn

# Inicializar Tablas
def inicializar_bd():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            contacto TEXT,
            telefono TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordenes_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_id INTEGER NOT NULL,
            producto TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL NOT NULL,
            iva REAL NOT NULL,
            total REAL NOT NULL,
            saldo_pendiente REAL NOT NULL,
            centro_costos TEXT NOT NULL,
            fecha_pago TEXT NOT NULL,
            observaciones TEXT,
            fecha_creacion TEXT NOT NULL,
            FOREIGN KEY (proveedor_id) REFERENCES proveedores (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            orden_id INTEGER NOT NULL,
            producto TEXT NOT NULL,
            entradas INTEGER NOT NULL,
            salidas INTEGER DEFAULT 0,
            stock_actual INTEGER NOT NULL,
            costo_unitario REAL NOT NULL,
            FOREIGN KEY (orden_id) REFERENCES ordenes_compra (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bajas_inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventario_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            motivo TEXT NOT NULL,
            usuario_responsable TEXT NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY (inventario_id) REFERENCES inventario (id)
        )
    ''')
    conn.commit()

inicializar_bd()

st.title("📦 Sistema Integral de Órdenes e Inventario")

# Menú lateral
menu = st.sidebar.selectbox("Selecciona una opción", [
    "1. Registrar Proveedor",
    "2. Crear Órden de Compra",
    "3. Ver / Imprimir Órden de Compra",
    "4. Dar de Baja Producto (Consumo)",
    "5. Reporte de Inventario (Kardex)",
    "6. Concentrado de Órdenes",
    "7. Saldos por Proveedor",
    "8. Reporte Centros de Costos"
])

conn = get_connection()

# -------------------------------------------------------------
# 1. REGISTRAR PROVEEDOR
# -------------------------------------------------------------
if menu == "1. Registrar Proveedor":
    st.header("👤 Registrar Nuevo Proveedor")
    with st.form("form_prov"):
        nombre = st.text_input("Nombre de la Empresa / Proveedor")
        contacto = st.text_input("Nombre de Contacto")
        telefono = st.text_input("Teléfono")
        submitted = st.form_submit_button("Guardar Proveedor")
        
        if submitted:
            if nombre.strip() == "":
                st.error("El nombre del proveedor es obligatorio.")
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO proveedores (nombre, contacto, telefono) VALUES (?, ?, ?)", (nombre, contacto, telefono))
                    conn.commit()
                    st.success(f"✅ Proveedor '{nombre}' registrado correctamente.")
                except sqlite3.IntegrityError:
                    st.error("❌ El proveedor ya existe.")

# -------------------------------------------------------------
# 2. CREAR ÓRDEN DE COMPRA
# -------------------------------------------------------------
elif menu == "2. Crear Órden de Compra":
    st.header("📝 Nueva Órden de Compra")
    
    df_provs = pd.read_sql("SELECT id, nombre FROM proveedores", conn)
    
    if df_provs.empty:
        st.warning("⚠️ Primero debe registrar al menos un proveedor.")
    else:
        opciones_prov = {row['nombre']: row['id'] for _, row in df_provs.iterrows()}
        
        with st.form("form_oc"):
            prov_nombre = st.selectbox("Seleccionar Proveedor", list(opciones_prov.keys()))
            producto = st.text_input("Producto / Servicio")
            col1, col2 = st.columns(2)
            with col1:
                cantidad = st.number_input("Cantidad", min_value=1, step=1)
            with col2:
                precio_u = st.number_input("Precio Unitario ($)", min_value=0.01, step=0.5)
                
            aplica_iva = st.radio("¿Aplica IVA?", ["Sí (16%)", "No"])
            centro_costos = st.text_input("Centro de Costos")
            fecha_pago = st.date_input("Fecha de Pago Programada")
            obs = st.text_area("Observaciones")
            
            submitted = st.form_submit_button("Generar Órden de Compra")
            
            if submitted:
                prov_id = opciones_prov[prov_nombre]
                subtotal = cantidad * precio_u
                iva = subtotal * 0.16 if aplica_iva == "Sí (16%)" else 0.0
                total = subtotal + iva
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO ordenes_compra (proveedor_id, producto, cantidad, precio_unitario, subtotal, iva, total, saldo_pendiente, centro_costos, fecha_pago, observaciones, fecha_creacion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (prov_id, producto, cantidad, precio_u, subtotal, iva, total, total, centro_costos, str(fecha_pago), obs, fecha_actual))
                folio = cursor.lastrowid
                
                cursor.execute('''
                    INSERT INTO inventario (orden_id, producto, entradas, salidas, stock_actual, costo_unitario)
                    VALUES (?, ?, ?, 0, ?, ?)
                ''', (folio, producto, cantidad, cantidad, precio_u))
                conn.commit()
                
                st.success(f"🎉 Órden #OC-{folio:05d} creada exitosamente e ingresada al inventario.")

# -------------------------------------------------------------
# 3. VER / IMPRIMIR ÓRDEN DE COMPRA
# -------------------------------------------------------------
elif menu == "3. Ver / Imprimir Órden de Compra":
    st.header("📄 Formato Imprimible de Órden de Compra")
    folio_input = st.number_input("Ingrese el número de Folio (ej. 1, 2...)", min_value=1, step=1)
    
    if st.button("Buscar Órden"):
        cursor = conn.cursor()
        cursor.execute('''
            SELECT oc.id, oc.fecha_creacion, p.nombre, p.contacto, p.telefono, 
                   oc.producto, oc.cantidad, oc.precio_unitario, oc.subtotal, 
                   oc.iva, oc.total, oc.saldo_pendiente, oc.centro_costos, 
                   oc.fecha_pago, oc.observaciones
            FROM ordenes_compra oc
            JOIN proveedores p ON oc.proveedor_id = p.id
            WHERE oc.id = ?
        ''', (folio_input,))
        oc = cursor.fetchone()
        
        if oc:
            st.code(f"""
======================================================================
                         ORDEN DE COMPRA: #OC-{oc[0]:05d}
======================================================================
Fecha de Emisión : {oc[1]}
Centro de Costos : {oc[12]}
----------------------------------------------------------------------
DATOS DEL PROVEEDOR:
  Nombre         : {oc[2]}
  Contacto       : {oc[3] or 'N/A'}
  Teléfono       : {oc[4] or 'N/A'}
  Fecha Pago Prog: {oc[13]}
----------------------------------------------------------------------
DETALLE DEL PEDIDO:
  Producto / Serv: {oc[5]}
  Cantidad       : {oc[6]}
  Precio Unit.   : ${oc[7]:,.2f}
----------------------------------------------------------------------
RESUMEN FINANCIERO:
  Subtotal       : ${oc[8]:,.2f}
  IVA (16%)      : ${oc[9]:,.2f}
  TOTAL          : ${oc[10]:,.2f}
  Saldo Pendiente: ${oc[11]:,.2f}
----------------------------------------------------------------------
OBSERVACIONES:
  {oc[14] or 'Sin observaciones.'}
======================================================================

  ____________________________          ____________________________
     Firma de Autorización                  Recibido Conforme
======================================================================
""", language="text")
        else:
            st.error("❌ Folio no encontrado.")

# -------------------------------------------------------------
# 4. DAR DE BAJA PRODUCTO
# -------------------------------------------------------------
elif menu == "4. Dar de Baja Producto (Consumo)":
    st.header("📉 Registrar Salida / Baja de Inventario")
    df_inv = pd.read_sql("SELECT id, producto, stock_actual, costo_unitario FROM inventario WHERE stock_actual > 0", conn)
    
    if df_inv.empty:
        st.info("No hay existencias disponibles en inventario.")
    else:
        st.dataframe(df_inv)
        
        with st.form("form_baja"):
            inv_id = st.selectbox("ID de Inventario", df_inv["id"].tolist())
            cant_baja = st.number_input("Cantidad a dar de baja", min_value=1, step=1)
            motivo = st.text_input("Motivo (Consumo, Merma, etc.)")
            responsable = st.text_input("Persona Solicitante / Responsable")
            
            submitted = st.form_submit_button("Registrar Baja")
            if submitted:
                stock_actual = df_inv.loc[df_inv['id'] == inv_id, 'stock_actual'].values[0]
                prod_nombre = df_inv.loc[df_inv['id'] == inv_id, 'producto'].values[0]
                
                if cant_baja > stock_actual:
                    st.error("❌ La cantidad supera el stock disponible.")
                else:
                    cursor = conn.cursor()
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                    cursor.execute("INSERT INTO bajas_inventario (inventario_id, cantidad, motivo, usuario_responsable, fecha) VALUES (?, ?, ?, ?, ?)",
                                   (inv_id, cant_baja, motivo, responsable, fecha_actual))
                    nuevo_stock = stock_actual - cant_baja
                    cursor.execute("UPDATE inventario SET salidas = salidas + ?, stock_actual = ? WHERE id = ?", (cant_baja, nuevo_stock, inv_id))
                    conn.commit()
                    st.success(f"✅ Se dieron de baja {cant_baja} unidades de '{prod_nombre}'. Stock restante: {nuevo_stock}")

# -------------------------------------------------------------
# 5. REPORTE INVENTARIO
# -------------------------------------------------------------
elif menu == "5. Reporte de Inventario (Kardex)":
    st.header("📊 Inventario de Productos y Existencias")
    df = pd.read_sql('''
        SELECT id as ID_INV, orden_id as FOLIO_OC, producto as PRODUCTO, entradas as ENTRADAS, 
               salidas as SALIDAS, stock_actual as STOCK, costo_unitario as COSTO_UNIT,
               (stock_actual * costo_unitario) as VALOR_TOTAL
        FROM inventario
    ''', conn)
    
    if df.empty:
        st.info("Sin registros en inventario.")
    else:
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------------------
# 6. CONCENTRADO DE ÓRDENES
# -------------------------------------------------------------
elif menu == "6. Concentrado de Órdenes":
    st.header("📋 Concentrado General de Órdenes de Compra")
    df = pd.read_sql('''
        SELECT oc.id as FOLIO, oc.fecha_creacion as FECHA, p.nombre as PROVEEDOR, 
               oc.producto as PRODUCTO, oc.total as TOTAL, oc.saldo_pendiente as SALDO_PENDIENTE, 
               oc.centro_costos as CENTRO_COSTOS
        FROM ordenes_compra oc
        JOIN proveedores p ON oc.proveedor_id = p.id
        ORDER BY oc.id ASC
    ''', conn)
    
    if df.empty:
        st.info("Sin órdenes registradas.")
    else:
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------------------
# 7. SALDOS POR PROVEEDOR
# -------------------------------------------------------------
elif menu == "7. Saldos por Proveedor":
    st.header("💰 Saldos Pendientes por Proveedor")
    df = pd.read_sql('''
        SELECT p.nombre as PROVEEDOR, SUM(oc.total) as TOTAL_FACTURADO, SUM(oc.saldo_pendiente) as SALDO_PENDIENTE
        FROM ordenes_compra oc
        JOIN proveedores p ON oc.proveedor_id = p.id
        GROUP BY p.id
        ORDER BY SALDO_PENDIENTE DESC
    ''', conn)
    
    if df.empty:
        st.info("Sin registros.")
    else:
        st.dataframe(df, use_container_width=True)

# -------------------------------------------------------------
# 8. CENTROS DE COSTOS
# -------------------------------------------------------------
elif menu == "8. Reporte Centros de Costos":
    st.header("🏢 Resumen de Gastos por Centro de Costos")
    df = pd.read_sql('''
        SELECT centro_costos as CENTRO_COSTOS, COUNT(id) as CANT_ORDENES, 
               SUM(total) as TOTAL_GASTADO, SUM(saldo_pendiente) as SALDO_POR_PAGAR
        FROM ordenes_compra
        GROUP BY centro_costos
        ORDER BY TOTAL_GASTADO DESC
    ''', conn)
    
    if df.empty:
        st.info("Sin registros.")
    else:
        st.dataframe(df, use_container_width=True)
