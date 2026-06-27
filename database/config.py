from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Resolver la ruta absoluta de la base de datos para que sea compartida por todos los scripts
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = f"sqlite:///{os.path.join(BASE_DIR, 'empleos_local.db')}"

engine = create_engine(DB_PATH, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()