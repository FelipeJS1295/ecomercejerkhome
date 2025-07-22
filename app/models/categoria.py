from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.database import Base

class Categoria(Base):
    __tablename__ = "categorias"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(String(255), nullable=True)
    imagen = Column(String(255), nullable=True)  # Nueva columna para imagen
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relación con productos
    productos = relationship("Producto", back_populates="categoria")
    
    def __repr__(self):
        return f"<Categoria(id={self.id}, nombre='{self.nombre}')>"