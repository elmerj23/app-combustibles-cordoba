import mysql.connector
import pandas as pd

# ==========================================
# 1. FUNCIONES BASE DE CONEXIÓN Y CONSULTAS
# ==========================================

def obtener_conexion():
    """Establece y devuelve la conexión a MySQL usando Aiven Cloud."""
    return mysql.connector.connect(
        host=st.secrets["DB_HOST"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        database=st.secrets["DB_NAME"],
        port=int(st.secrets["DB_PORT"])
    )
def guardar_reporte_manual(id_estacion, tipo_combustible, precio):
    """Guarda el precio ingresado manualmente en la base de datos."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        
        query = """
            INSERT INTO reportes_precios (estacion_id, Tipo_combustible, precio) 
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (id_estacion, tipo_combustible, precio))
        conn.commit()
        
        cursor.close()
        conn.close()
        return True, "¡Precio cargado con éxito!"
    except mysql.connector.Error as err:
        return False, f"Error en la base de datos: {err}"

def obtener_precios_mas_baratos():
    """Trae los precios más bajos reportados por choferes y los oficiales."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        
        # Más barato reportado por choferes
        q_usr = """
            SELECT r.Tipo_combustible, r.precio, e.nombre_estacion, e.direccion_estacion
            FROM reportes_precios r
            JOIN estaciones e ON r.estacion_id = e.estacion_id
            WHERE r.precio = (
                SELECT MIN(r2.precio) 
                FROM reportes_precios r2 
                WHERE r2.Tipo_combustible = r.Tipo_combustible
            )
            GROUP BY r.Tipo_combustible, r.precio, e.nombre_estacion, e.direccion_estacion;
        """
        cursor.execute(q_usr)
        reportes_usr = cursor.fetchall()
        
        # Más barato oficial (si existe la tabla)
        q_ofic = """
            SELECT p.tipo_combustible, p.precio_oficial, p.marca
            FROM precios_oficiales p
            WHERE p.precio_oficial = (
                SELECT MIN(p2.precio_oficial) 
                FROM precios_oficiales p2 
                WHERE p2.tipo_combustible = p.tipo_combustible
            )
            GROUP BY p.tipo_combustible, p.precio_oficial, p.marca;
        """
        cursor.execute(q_ofic)
        oficiales = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return reportes_usr, oficiales
    except mysql.connector.Error:
        return [], []


# ==========================================
# 2. MENÚ INTERACTIVO POR CONSOLA
# ==========================================

def ejecutar_menu_consola():
    """Ejecuta el menú por consola si corrés directamente 'python mi_script.py'"""
    try:
        conexion = obtener_conexion()
        print("¡Conexión exitosa a la base de datos 'app_uber'!\n")
    except mysql.connector.Error as err:
        print(f"Error al conectar: {err}")
        return

    Micursor = conexion.cursor()

    while True:
        print('======= MENU ========')
        print('1. VER ESTACION / PRECIO PROMEDIO')
        print('2. CARGAR PRECIO NUEVO')
        print('3. SALIR')
        print()
        opcion = input('Buenos días, por favor ingrese una opción: ')
        
        # 1. VER ESTACIONES
        if opcion == '1':
            print('\n===== ESTACIONES Y PRECIOS PROMEDIO =====')
            Micursor.execute("SELECT estacion_id, nombre_estacion, direccion_estacion FROM estaciones")
            estaciones = Micursor.fetchall()
            
            if estaciones:
                for est in estaciones:
                    e_id, e_nombre, e_direccion = est
                    consulta_precios = '''
                        SELECT Tipo_combustible, AVG(precio) 
                        FROM reportes_precios 
                        WHERE estacion_id = %s 
                        GROUP BY Tipo_combustible
                    '''
                    Micursor.execute(consulta_precios, (e_id,))
                    precios = Micursor.fetchall()
                    
                    print(f"\n📍 {e_nombre} ({e_direccion})")
                    if precios:
                        for p in precios:
                            tipo, promedio = p
                            print(f"   -> {tipo}: ${promedio:.2f}")
                    else:
                        print("   -> ⚠️ Sin precios cargados aún")
            else:
                print("No hay estaciones registradas en la base de datos.")
            print()

        # 2. CARGAR DATOS
        elif opcion == '2':
            print('\n===== CARGAR NUEVO PRECIO =====')
            Micursor.execute("SELECT estacion_id, nombre_estacion, direccion_estacion FROM estaciones")
            estaciones = Micursor.fetchall()
            
            if not estaciones:
                print("❌ No hay estaciones registradas. Primero debés dar de alta una estación.")
            else:
                print("Seleccioná la estación:")
                for est in estaciones:
                    print(f"  {est[0]}. {est[1]} ({est[2]})")
                
                try:
                    id_estacion = int(input("\nNúmero de estación: "))
                    
                    print("\nSeleccioná el tipo de combustible:")
                    print("  1. GNC")
                    print("  2. Nafta Súper")
                    print("  3. Nafta Premium")
                    
                    opcion_combustible = input("Opción (1-3): ")
                    
                    if opcion_combustible == '1':
                        tipo_combustible = 'GNC'
                    elif opcion_combustible == '2':
                        tipo_combustible = 'Nafta Super'
                    elif opcion_combustible == '3':
                        tipo_combustible = 'Nafta Premium'
                    else:
                        print("⚠️ Opción de combustible no válida. Operación cancelada.")
                        continue
                    
                    precio = float(input(f"Ingresá el precio para {tipo_combustible}: $"))
                    
                    # Llamada a la función
                    exito, msg = guardar_reporte_manual(id_estacion, tipo_combustible, precio)
                    if exito:
                        print(f"\n✅ ¡Éxito! Se cargó ${precio:.2f} para {tipo_combustible} correctamente.")
                    else:
                        print(f"\n❌ {msg}")
                    
                except ValueError:
                    print("❌ Error: Debés ingresar un número válido.")
            print()

        # 3. SALIR
        elif opcion == '3':
            print('\n=======================================================')
            print('¡QUE TENGA BUENOS DÍAS! GRACIAS POR SU APORTE')
            print('=======================================================\n')
            break

    Micursor.close()
    conexion.close()
    print("Conexión cerrada.")

if __name__ == "__main__":
    ejecutar_menu_consola()
def guardar_reporte_control(tipo_control, descripcion, latitud, longitud):
    """Guarda un nuevo reporte de control en la base de datos."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        query = """
            INSERT INTO reportes_controles (tipo_control, ubicacion_descripcion, latitud, longitud)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (tipo_control, descripcion, latitud, longitud))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "¡Aviso de control registrado con éxito!"
    except Exception as e:
        return False, f"Error al guardar el aviso: {e}"

def obtener_controles_activos(horas=4):
    """Obtiene los controles reportados en las últimas 'X' horas."""
    try:
        conn = obtener_conexion()
        query = f"""
            SELECT control_id, tipo_control, ubicacion_descripcion, latitud, longitud, fecha_hora
            FROM reportes_controles
            WHERE fecha_hora >= NOW() - INTERVAL {horas} HOUR
            ORDER BY fecha_hora DESC
        """
        df = pd.read_sql(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error al obtener controles: {e}")
        return pd.DataFrame()
def eliminar_reporte_control(control_id):
    """Elimina o da por finalizada una alerta de tránsito por su ID."""
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        query = "DELETE FROM reportes_controles WHERE control_id = %s"
        cursor.execute(query, (control_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True, "¡Alerta eliminada correctamente!"
    except Exception as e:
        return False, f"Error al eliminar la alerta: {e}"    
