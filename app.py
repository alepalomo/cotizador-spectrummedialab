import streamlit as st
# Configuración DEBE ser lo primero
st.set_page_config(page_title="Cotizador Spectrum", page_icon="📊")

from database import Base, engine, get_db
from auth import login_form, require_role, hash_password
from models import User

# Crear tablas
Base.metadata.create_all(bind=engine)

# Obtener sesión
db = next(get_db())

# --- BLOQUE MÁGICO: AUTOCREAR ADMIN ---
try:
    admin_user = db.query(User).filter(User.username == "admin").first()
    if not admin_user:
        # Crea el usuario admin si no existe
        admin_pass = hash_password("admin123") 
        new_admin = User(username="admin", password_hash=admin_pass, role="ADMIN")
        db.add(new_admin)
        db.commit()
        print("✅ Usuario Admin creado automáticamente.")
except Exception as e:
    print(f"Error verificando admin: {e}")
# -----------------------------------------------------

# Lógica de Login
if "user_id" not in st.session_state:
    login_form()
else:
    # Sidebar
    st.sidebar.title(f"Hola, {st.session_state['username']}")
    st.sidebar.write(f"Rol: {st.session_state['role']}")
    
    if st.sidebar.button("Cerrar Sesión"):
        for key in ["user_id", "role", "username"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    
    st.write("---")
    st.info("👈 Selecciona una opción en el menú de la izquierda.")