import streamlit as st
import pandas as pd
import mysql.connector
import folium
from streamlit_folium import st_folium
import re

# Importamos la conexión y funciones desde mi_script.py
from mi_script import (
    obtener_conexion, 
    guardar_reporte_manual, 
    obtener_precios_mas_baratos,
    guardar_reporte_control,
    obtener_controles_activos,
    eliminar_reporte_control  
)

# Configuración de la página
st.set_page_config(
    page_title="Red Vial y Combustibles - Córdoba",
    page_icon="🚘",
    layout="wide"
)

st.title("🚘 Red Vial y Estado del Tránsito - Córdoba")
st.markdown("Consulta precios de combustible, ubicaciones y reportá **alertas de tránsito u operativos viales** tocando directamente en el mapa.")

# ==========================================
# GESTIÓN DE ESTADO (SESSION STATE PARA CLICS)
# ==========================================
if "estacion_seleccionada_nombre" not in st.session_state:
    st.session_state["estacion_seleccionada_nombre"] = None

if "click_lat" not in st.session_state:
    st.session_state["click_lat"] = None

if "click_lng" not in st.session_state:
    st.session_state["click_lng"] = None

def limpiar_texto(texto):
    if not texto:
        return ""
    texto = texto.lower()
    texto = re.sub(r'[áàäâ]', 'a', texto)
    texto = re.sub(r'[éèëê]', 'e', texto)
    texto = re.sub(r'[íìïî]', 'i', texto)
    texto = re.sub(r'[óòöô]', 'o', texto)
    texto = re.sub(r'[úùüû]', 'u', texto)
    texto = re.sub(r'[^a-z0-9 ]', '', texto)
    return texto.strip()

# ==========================================
# 1. TARJETAS DE PRECIOS MÁS BAJOS
# ==========================================
reportes_usr, oficiales = obtener_precios_mas_baratos()

if reportes_usr:
    st.subheader("🔥 Precios más bajos (Reportados por la comunidad)")
    cols = st.columns(len(reportes_usr))
    for i, r in enumerate(reportes_usr):
        tipo = r[0]
        precio = r[1]
        estacion = r[2]
        
        with cols[i]:
            st.metric(
                label=f"{tipo}", 
                value=f"${precio:.2f}", 
                delta=f"📍 {estacion}"
            )
            if st.button(f"🎯 Ver {estacion[:15]}...", key=f"btn_usr_{i}"):
                st.session_state["estacion_seleccionada_nombre"] = estacion
                st.rerun()

st.markdown("---")

# ==========================================
# 2. CARGA DE DATOS DESDE MYSQL
# ==========================================
@st.cache_data(ttl=30)
def cargar_datos_mapa():
    try:
        conn = obtener_conexion()
        
        query_estaciones = """
            SELECT e.estacion_id, e.nombre_estacion, e.direccion_estacion, e.latitud, e.longitud,
                   AVG(r.precio) as precio_promedio
            FROM estaciones e
            LEFT JOIN reportes_precios r ON e.estacion_id = r.estacion_id
            GROUP BY e.estacion_id, e.nombre_estacion, e.direccion_estacion, e.latitud, e.longitud
        """
        df_est = pd.read_sql(query_estaciones, conn)
        
        query_usr = """
            SELECT estacion_id, Tipo_combustible, AVG(precio) as precio_prom
            FROM reportes_precios
            GROUP BY estacion_id, Tipo_combustible
        """
        df_usr = pd.read_sql(query_usr, conn)
        
        query_ofic = """
            SELECT tipo_combustible, precio_oficial, marca
            FROM precios_oficiales
        """
        df_ofic = pd.read_sql(query_ofic, conn)
        
        conn.close()
        return df_est, df_usr, df_ofic
    except Exception as e:
        st.error(f"Error al conectar a la base de datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_estaciones, df_precios_usr, df_precios_ofic = cargar_datos_mapa()
df_controles = obtener_controles_activos(horas=4)

# ==========================================
# 3. BARRA LATERAL (REPORTES Y ALERTAS)
# ==========================================
st.sidebar.header("📝 Carga de Datos")

pestana = st.sidebar.radio("¿Qué querés reportar?", ["⛽ Precio de Combustible", "⚠️ Alerta de Tránsito"])

if pestana == "⛽ Precio de Combustible":
    st.sidebar.subheader("Cargar Nuevo Precio")
    if not df_estaciones.empty:
        opciones_estaciones = {f"{row['nombre_estacion']} ({row['direccion_estacion']})": row['estacion_id'] 
                               for _, row in df_estaciones.iterrows()}
        estacion_sel = st.sidebar.selectbox("Seleccioná la Estación", list(opciones_estaciones.keys()))
        id_estacion = opciones_estaciones[estacion_sel]

        tipo_combustible = st.sidebar.selectbox("Tipo de Combustible", ["GNC", "Nafta Super", "Nafta Premium"])
        precio_ingresado = st.sidebar.number_input("Precio ($)", min_value=0.0, step=0.5, format="%.2f")

        if st.sidebar.button("💾 Guardar Precio"):
            if precio_ingresado > 0:
                exito, mensaje = guardar_reporte_manual(id_estacion, tipo_combustible, precio_ingresado)
                if exito:
                    st.sidebar.success(mensaje)
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.sidebar.error(mensaje)
            else:
                st.sidebar.warning("Ingresá un precio mayor a 0.")
    else:
        st.sidebar.warning("No hay estaciones cargadas en la BD.")

elif pestana == "⚠️ Alerta de Tránsito":
    st.sidebar.subheader("Reportar Novedad Vial")
    
    tipo_ctrl = st.sidebar.selectbox("Tipo de Evento / Alerta", [
        "🚧 Operativo Vial / Inspección",
        "🛑 Corte de Calle / Obras",
        "🚨 Control Vehicular",
        "🚦 Semáforo fuera de servicio / Demoras"
    ])
    
    descripcion_ctrl = st.sidebar.text_input("Ubicación / Esquina de referencia", placeholder="Ej: Av. Colón y Zípoli")
    
    # Notificación si hay un punto marcado por clic en el mapa
    if st.session_state["click_lat"] and st.session_state["click_lng"]:
        st.sidebar.info(f"📍 **Ubicación seleccionada en el mapa:**\n\nLat: `{st.session_state['click_lat']:.5f}` | Lng: `{st.session_state['click_lng']:.5f}`")
        if st.sidebar.button("❌ Limpiar selección del mapa"):
            st.session_state["click_lat"] = None
            st.session_state["click_lng"] = None
            st.rerun()

    # Opciones de ubicación (Clic en Mapa vs Estación de referencia)
    modo_ubicacion = st.sidebar.radio("Origen de las coordenadas:", ["Usar clic en el mapa 🎯", "Usar ubicación de estación ⛽"])
    
    lat_ctrl, lng_ctrl = -31.4135, -64.1810
    
    if modo_ubicacion == "Usar clic en el mapa 🎯":
        if st.session_state["click_lat"] and st.session_state["click_lng"]:
            lat_ctrl = st.session_state["click_lat"]
            lng_ctrl = st.session_state["click_lng"]
        else:
            st.sidebar.warning("👉 Hacé clic en cualquier punto del mapa para marcar el lugar exacto de la alerta.")
    else:
        if not df_estaciones.empty:
            estaciones_validas = df_estaciones.dropna(subset=['latitud', 'longitud'])
            opc_est_ctrl = {f"{row['nombre_estacion']} ({row['direccion_estacion']})": (row['latitud'], row['longitud']) 
                            for _, row in estaciones_validas.iterrows()}
            est_ref = st.sidebar.selectbox("Estación de Referencia", list(opc_est_ctrl.keys()))
            lat_ctrl, lng_ctrl = opc_est_ctrl[est_ref]

    if st.sidebar.button("📢 Publicar Alerta"):
        if descripcion_ctrl.strip() != "":
            exito, mensaje = guardar_reporte_control(tipo_ctrl, descripcion_ctrl, lat_ctrl, lng_ctrl)
            if exito:
                st.sidebar.success("¡Alerta registrada correctamente!")
                st.session_state["click_lat"] = None
                st.session_state["click_lng"] = None
                st.cache_data.clear()
                st.rerun()
            else:
                st.sidebar.error(mensaje)
        else:
            st.sidebar.warning("Ingresá una descripción o esquina de referencia.")

# ==========================================
# 4. MAPA INTERACTIVO (ESTACIONES + ALERTAS + CLICS)
# ==========================================
st.subheader("🗺️ Estado de Calzada y Estaciones de Servicio (Últimas 4h)")
st.caption("👉 **Tip:** Hacé clic en cualquier punto del mapa para seleccionar la ubicación de una nueva alerta de tránsito.")

if not df_controles.empty:
    st.info(f"⚠️ **Hay {len(df_controles)} alerta(s) de tránsito o evento(s) activo(s)** reportados por los usuarios en las últimas 4 horas.")

if not df_estaciones.empty:
    centro_lat, centro_lng, zoom_nivel = -31.4135, -64.1810, 12
    
    estacion_enfocada_nombre = st.session_state.get("estacion_seleccionada_nombre", None)
    
    if estacion_enfocada_nombre:
        nombre_busqueda = limpiar_texto(estacion_enfocada_nombre)
        df_estaciones['nombre_limpio'] = df_estaciones['nombre_estacion'].apply(limpiar_texto)
        est_match = df_estaciones[df_estaciones['nombre_limpio'].str.contains(nombre_busqueda, na=False)]
        
        if not est_match.empty:
            cand_lat = est_match.iloc[0]['latitud']
            cand_lng = est_match.iloc[0]['longitud']
            if pd.notnull(cand_lat) and pd.notnull(cand_lng):
                centro_lat, centro_lng = float(cand_lat), float(cand_lng)
                zoom_nivel = 15
                st.info(f"🎯 Enfocando en la estación: **{est_match.iloc[0]['nombre_estacion']}**")

        if st.button("❌ Quitar enfoque"):
            st.session_state["estacion_seleccionada_nombre"] = None
            st.rerun()

    mapa = folium.Map(location=[centro_lat, centro_lng], zoom_start=zoom_nivel)
    promedio_general = df_estaciones['precio_promedio'].dropna().mean() if not df_estaciones['precio_promedio'].dropna().empty else 0

    # A) PIN DE SELECCIÓN TEMPORAL POR CLIC DEL USUARIO
    if st.session_state["click_lat"] and st.session_state["click_lng"]:
        folium.Marker(
            location=[st.session_state["click_lat"], st.session_state["click_lng"]],
            popup="📍 Ubicación Seleccionada para Alerta",
            tooltip="Punto seleccionado (Ver menú lateral)",
            icon=folium.Icon(color="purple", icon="crosshairs", prefix="fa")
        ).add_to(mapa)

    # B) MARCADORES DE ESTACIONES
    for _, row in df_estaciones.iterrows():
        lat, lng, e_id = row['latitud'], row['longitud'], row['estacion_id']
        nombre_est, direccion_est, prom_est = row['nombre_estacion'], row['direccion_estacion'], row['precio_promedio']
        
        if pd.notnull(lat) and pd.notnull(lng):
            usr_est = df_precios_usr[df_precios_usr['estacion_id'] == e_id]
            url_gmaps = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"
            
            p_head = f"<b>📍 {nombre_est}</b><br><small>{direccion_est}</small><br>"
            p_gps = f"<a href='{url_gmaps}' target='_blank' style='display:inline-block; margin-top:5px; padding:4px 8px; background-color:#4CAF50; color:white; text-decoration:none; border-radius:4px; font-weight:bold;'>🚗 Ir con GPS</a><hr style='margin:5px 0;'>"
            html_popup = p_head + p_gps
            
            html_popup += "<b>🙋‍♂️ Precios Comunidad:</b><br>"
            if not usr_est.empty:
                for _, p_row in usr_est.iterrows():
                    html_popup += f"• {p_row['Tipo_combustible']}: <b>${p_row['precio_prom']:.2f}</b><br>"
            else:
                html_popup += "<i>Sin reportes recientes</i><br>"

            color_pin = "green" if (pd.notnull(prom_est) and prom_est <= promedio_general) else "orange"
            if estacion_enfocada_nombre and (limpiar_texto(nombre_est) in limpiar_texto(estacion_enfocada_nombre)):
                color_pin = "blue"

            folium.Marker(
                location=[float(lat), float(lng)],
                popup=folium.Popup(html_popup, max_width=280),
                tooltip=f"⛽ {nombre_est}",
                icon=folium.Icon(color=color_pin, icon="gas-pump", prefix="fa")
            ).add_to(mapa)

    # C) MARCADORES DE ALERTAS DE TRÁNSITO
    if not df_controles.empty:
        for _, c_row in df_controles.iterrows():
            c_lat, c_lng = c_row['latitud'], c_row['longitud']
            c_tipo, c_desc, c_fecha = c_row['tipo_control'], c_row['ubicacion_descripcion'], c_row['fecha_hora']
            hora_fmt = pd.to_datetime(c_fecha).strftime("%H:%M hs")
            
            popup_ctrl = f"<b>{c_tipo}</b><br>📍 {c_desc}<br>⏰ Reportado a las: <b>{hora_fmt}</b>"
            
            folium.Marker(
                location=[float(c_lat), float(c_lng)],
                popup=folium.Popup(popup_ctrl, max_width=250),
                tooltip=f"{c_tipo} - {c_desc} ({hora_fmt})",
                icon=folium.Icon(color="red", icon="triangle-exclamation", prefix="fa")
            ).add_to(mapa)

    # RENDERIZADO DEL MAPA Y CAPTURA DE EVENTO CLIC
    mapa_salida = st_folium(mapa, width="100%", height=500)

    # Captura de coordenadas al hacer clic
    if mapa_salida and mapa_salida.get("last_clicked"):
        click_data = mapa_salida["last_clicked"]
        nueva_lat = click_data["lat"]
        nueva_lng = click_data["lng"]

        if nueva_lat != st.session_state["click_lat"] or nueva_lng != st.session_state["click_lng"]:
            st.session_state["click_lat"] = nueva_lat
            st.session_state["click_lng"] = nueva_lng
            st.rerun()

# ==========================================
# 5. LISTADO Y GESTIÓN DE ALERTAS ACTIVAS
# ==========================================
if not df_controles.empty:
    st.subheader("📢 Alertas Viales Activas (Últimas 4 Horas)")
    st.caption("Si pasás por el lugar y ves que la alerta ya no está activa, podés presionar **🗑️ Ya se liberó** para quitarla del mapa.")

    for _, c_row in df_controles.iterrows():
        c_id = c_row['control_id']
        c_tipo = c_row['tipo_control']
        c_desc = c_row['ubicacion_descripcion']
        hora_fmt = pd.to_datetime(c_row['fecha_hora']).strftime("%H:%M hs")

        # Mostramos cada alerta en una tarjeta de dos columnas
        col_info, col_btn = st.columns([4, 1])

        with col_info:
            st.markdown(f"**{c_tipo}** | 📍 {c_desc} *(Reportado {hora_fmt})*")

        with col_btn:
            if st.button("🗑️ Ya se liberó", key=f"btn_del_{c_id}"):
                exito, msj = eliminar_reporte_control(c_id)
                if exito:
                    st.toast("✅ Alerta quitada correctamente")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(msj)
# ==========================================
# 6. PIE DE PÁGINA (DESLINDE LEGAL / DISCLAIMER)
# ==========================================
st.markdown("---")
st.caption(
    "ℹ️ **Aviso Legal y Términos de Uso:** Esta plataforma es una herramienta informativa y de colaboración comunitaria entre "
    "conductores sobre el estado del tránsito y valores orientativos de combustibles en la vía pública. Se promueve el estricto cumplimiento "
    "de las normas de tránsito vigentes, la conducción responsable y el respeto a la autoridad de aplicación. La información "
    "es proveída y actualizada de manera voluntaria por los usuarios."
)