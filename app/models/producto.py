from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.database import Base

class Producto(Base):
    __tablename__ = "productos"
    
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, nullable=False)
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio = Column(Float, nullable=False)
    precio_oferta = Column(Float, nullable=True)
    stock = Column(Integer, default=0)
    categoria_id = Column(Integer, ForeignKey("categorias.id"))
    
    # Hasta 7 imágenes
    imagen_1 = Column(String(255), nullable=True)
    imagen_2 = Column(String(255), nullable=True)
    imagen_3 = Column(String(255), nullable=True)
    imagen_4 = Column(String(255), nullable=True)
    imagen_5 = Column(String(255), nullable=True)
    imagen_6 = Column(String(255), nullable=True)
    imagen_7 = Column(String(255), nullable=True)
    
    vistas = Column(Integer, default=0)
    activo = Column(Boolean, default=True)
    destacado = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relación con categoría (CORREGIDO)
    categoria = relationship("Categoria", back_populates="productos")
    
    def __repr__(self):
        return f"<Producto(id={self.id}, sku='{self.sku}', nombre='{self.nombre}')>"