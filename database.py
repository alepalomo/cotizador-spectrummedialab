import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# LÓGICA HÍBRIDA: NUBE vs LOCAL
try:
    # Intenta leer la URL de los secretos de Streamlit (Nube)
    database_url = st.secrets["connections"]["postgresql"]["url"]
    
    # Corrige el formato si viene como postgres://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
        
    print("☁️ Conectando a Base de Datos en la Nube (PostgreSQL)...")

except Exception:
    # Si falla (porque estás en tu compu sin secretos), usa SQLite local
    print("💻 Conectando a Base de Datos Local (SQLite)...")
    database_url = "sqlite:///./local_backup.db"

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()