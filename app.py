import streamlit as st
from database import Base, engine, get_db
from auth import login_form
from services import init_db_seeds

st.set_page_config(page_title="Cotizador SM", layout="wide")

# Inicializar Base de Datos
Base.metadata.create_all(bind=engine)
db = next(get_db())
init_db_seeds(db) # Crea usuario admin si no existe

def main():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if not st.session_state["logged_in"]:
        login_form(db)
    else:
        # Barra lateral con info de usuario
        st.sidebar.title(f"Hola, {st.session_state['username']}")
        st.sidebar.info(f"Rol: {st.session_state['role']}")
        
        st.title("Bienvenido al Cotizador & Presupuesto SM")
        st.markdown("""
        ### Guía Rápida:
        1. **Catalogos (Solo Admin):** Ve aquí PRIMERO para crear Malls, Insumos y Tipos de Actividad.
        2. **Cotizador:** Crea tus propuestas.
        3. **Aprobaciones:** El admin revisa y aprueba.
        4. **Gastos Reales:** Registra lo que realmente se gastó.
        """)
        
        if st.sidebar.button("Cerrar Sesión"):
            st.session_state["logged_in"] = False
            st.rerun()

if __name__ == "__main__":
    main()