import streamlit as st
import bcrypt
from database import get_db
from models import User

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def login_form():
    st.title("🔐 Iniciar Sesión")
    
    with st.form("login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")
        
        if submitted:
            db = next(get_db())
            user = db.query(User).filter(User.username == username).first()
            
            if user and check_password(password, user.password_hash):
                st.session_state["user_id"] = user.id
                st.session_state["username"] = user.username
                st.session_state["role"] = user.role
                st.success(f"Bienvenido {user.username}")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

def require_role(roles):
    if "user_id" not in st.session_state:
        st.warning("Debes iniciar sesión.")
        st.stop()
    
    if st.session_state["role"] not in roles:
        st.error("⛔ No tienes permisos para ver esta página.")
        st.stop()