import streamlit as st

# 1. Configuración DEBE ser lo primero
st.set_page_config(page_title="Cotizador Spectrum", page_icon="📊", layout="wide")

from database import Base, engine, get_db
from auth import login_form, require_role, hash_password
from models import User

# --- INICIALIZACIÓN DE SESIÓN PERSISTENTE ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Crear tablas
Base.metadata.create_all(bind=engine)

# Obtener sesión
db = next(get_db())

# --- BLOQUE MÁGICO: AUTOCREAR ADMIN ---
try:
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        admin_pass = hash_password("admin123") 
        new_admin = User(username="admin", password_hash=admin_pass, role="ADMIN")
        db.add(new_admin)
        db.commit()
        print("✅ Usuario Admin creado automáticamente.")
except Exception as e:
    print(f"Error verificando admin: {e}")

# ==============================================================================
# LÓGICA DE CONTROL DE ACCESO
# ==============================================================================

# Si NO está autenticado, muestra el login y DETIENE el resto de la ejecución
if not st.session_state["authenticated"]:
    login_form()
    # Importante: Dentro de login_form() debe ponerse st.session_state["authenticated"] = True 
    # cuando las credenciales sean correctas para que esto funcione.
    st.stop() 

# SI LLEGA AQUÍ, EL USUARIO YA ESTÁ LOGUEADO
# ==============================================================================
# CONTENIDO PRINCIPAL (SIDEBAR Y VISTA)
# ==============================================================================

# Sidebar
st.sidebar.title(f"👋 Hola, {st.session_state.get('username', 'Usuario')}")
st.sidebar.write(f"💼 Rol: {st.session_state.get('role', 'Sin Rol')}")

st.sidebar.divider()

if st.sidebar.button("🚪 Cerrar Sesión"):
    # Limpiamos todas las llaves para un cierre total
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Cuerpo de la página de bienvenida
st.title("🚀 Sistema de Cotizaciones Spectrum Media")
st.write("---")
st.info("👈 Selecciona una opción en el menú de la izquierda para comenzar.")

# Opcional: Mostrar resumen rápido o métricas aquí