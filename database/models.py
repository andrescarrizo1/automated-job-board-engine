from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime
from database.config import engine

Base = declarative_base()

class RawMessage(Base):
    __tablename__ = 'raw_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String, index=True) 
    message_text = Column(Text, nullable=False)
    message_hash = Column(String, unique=True, index=True) 
    date_received = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default='pending') 

# --- NUEVA TABLA PARA LOS DATOS LIMPIOS ---
class StructuredJob(Base):
    __tablename__ = 'structured_jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_message_id = Column(Integer, ForeignKey('raw_messages.id')) # Conecta con el mensaje original
    puesto = Column(String)
    empresa = Column(String)
    ubicacion = Column(String)
    requisitos = Column(Text)
    contacto = Column(String)
    status = Column(String, default='pending')

# Crea las tablas automáticamente si no existen
Base.metadata.create_all(bind=engine)