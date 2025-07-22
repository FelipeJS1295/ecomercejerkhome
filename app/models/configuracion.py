from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from app.database.database import Base

class Configuracion(Base):
    __tablename__ = "configuraciones"
    
    id = Column(Integer, primary_key=True, index=True)
    clave = Column(String(100), unique=True, nullable=False, index=True)
    valor = Column(Text, nullable=True)
    tipo = Column(String(50), nullable=False, default="texto")  # texto, imagen, boolean, email, telefono, url
    categoria = Column(String(50), nullable=False)  # general, contacto, redes_sociales, banner, seo
    descripcion = Column(String(255), nullable=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Configuracion(clave='{self.clave}', valor='{self.valor}')>"