from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- EL TRUCO ESTÁ AQUÍ ---
# Cambiamos "local.db" por "spectrum_v1.db" (o v2, v3...)
# Esto obliga a la nube a crear un archivo nuevo y limpio.
SQLALCHEMY_DATABASE_URL = "sqlite:///./spectrum_v1.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()