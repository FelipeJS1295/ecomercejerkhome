from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Enum, Text
from sqlalchemy.sql import func
from app.database.database import Base
from datetime import datetime, timedelta
import enum

# Enums para los estados
class EstadoPago(str, enum.Enum):
    PAGADA = "PAGADA"
    PENDIENTE = "PENDIENTE"
    ANULADA = "ANULADA"

class EstadoVenta(str, enum.Enum):
    NUEVA = "NUEVA"
    EN_DESPACHO = "EN_DESPACHO"
    ENTREGADA = "ENTREGADA"
    ANULADA = "ANULADA"
    DEVOLUCION = "DEVOLUCION"

class Venta(Base):
    __tablename__ = "ventas"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    orden_compra = Column(String(12), nullable=False, unique=True, index=True)
    
    # Información del cliente
    
    rut_cliente = Column(String(12), nullable=False, index=True)
    nombre_cliente = Column(String(255), nullable=False)
    direccion_cliente = Column(String(255), nullable=False)
    comuna_cliente = Column(String(100), nullable=False, index=True)
    region_cliente = Column(String(100), nullable=False)
    numero_telefono = Column(String(20), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    
    # Información del producto
    sku = Column(String(50), nullable=False, index=True)
    nombre = Column(String(255), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio = Column(Float, nullable=False)  # Cambiado de Decimal a Float
    
    # Fechas
    fecha_compra = Column(DateTime, nullable=False, default=func.now(), index=True)
    fecha_entrega = Column(Date, nullable=True, index=True)
    
    # Estados
    estado_pago = Column(
        Enum(EstadoPago), 
        nullable=False, 
        default=EstadoPago.PENDIENTE, 
        index=True
    )
    estado_venta = Column(
        Enum(EstadoVenta), 
        nullable=False, 
        default=EstadoVenta.NUEVA, 
        index=True
    )
    
    # Timestamps automáticos
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Venta(id={self.id}, cliente='{self.nombre_cliente}', producto='{self.nombre}', total={self.total})>"
    
    @property
    def total(self):
        """Calcula el total de la venta (cantidad * precio)"""
        return float(self.cantidad * self.precio)
    
    @property
    def numero_venta(self):
        """Genera un número de venta legible"""
        return f"JH{self.id:06d}"