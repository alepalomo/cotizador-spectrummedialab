import bcrypt
import streamlit as st
from sqlalchemy.orm import Session
from models import User

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def authenticate_user(db: Session, username, password):
    user = db.query(User).filter(User.username == username).first()
    if user and check_password(password, user.password_hash):
        return user
    return None

def login_form(db: Session):
    st.markdown("### Iniciar Sesión")
    username = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        user = authenticate_user(db, username, password)
        if user:
            if not user.is_active:
                st.error("Usuario inactivo.")
                return
            st.session_state["logged_in"] = True
            st.session_state["user_id"] = user.id
            st.session_state["username"] = user.username
            st.session_state["role"] = user.role
            st.rerun()
        else:
            st.error("Credenciales incorrectas")

def require_role(roles: list):
    if not st.session_state.get("logged_in"):
        st.warning("Por favor inicia sesión.")
        st.stop()
    if st.session_state.get("role") not in roles:
        st.error("No tienes permiso para ver esta página.")
        st.stop()