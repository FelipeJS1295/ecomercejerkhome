from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from app.database.database import Base
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, EmailStr, validator

class Contacto(Base):
    __tablename__ = 'contactos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    telefono = Column(String(20), nullable=True)
    email = Column(String(100), nullable=False)
    asunto = Column(String(100), nullable=False)
    mensaje = Column(Text, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, server_default=func.current_timestamp())
    estado = Column(String(20), default='pendiente', server_default='pendiente')
    notas_internas = Column(Text, nullable=True)
    respondido_por = Column(String(100), nullable=True)
    fecha_respuesta = Column(DateTime, nullable=True)
    
    def to_dict(self):
        """Convierte el objeto a diccionario"""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'telefono': self.telefono,
            'email': self.email,
            'asunto': self.asunto,
            'mensaje': self.mensaje,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'estado': self.estado,
            'notas_internas': self.notas_internas,
            'respondido_por': self.respondido_por,
            'fecha_respuesta': self.fecha_respuesta.isoformat() if self.fecha_respuesta else None
        }
    
    @staticmethod
    def get_estados_disponibles():
        """Retorna los estados disponibles para un contacto"""
        return ['pendiente', 'en_proceso', 'resuelto']
    
    @staticmethod
    def get_asuntos_disponibles():
        """Retorna los asuntos disponibles"""
        return [
            'Consulta de Productos',
            'Cotización',
            'Servicio Post-Venta',
            'Reclamo',
            'Sugerencia',
            'Otro'
        ]
    
    def tiempo_respuesta(self):
        """Calcula el tiempo de respuesta si está resuelto"""
        if self.fecha_respuesta and self.fecha_creacion:
            diff = self.fecha_respuesta - self.fecha_creacion
            if diff.days > 0:
                return f"{diff.days} día(s)"
            else:
                hours = diff.seconds // 3600
                return f"{hours} hora(s)"
        return None

# Esquemas Pydantic para validación
class ContactoCreate(BaseModel):
    nombre: str
    telefono: Optional[str] = None
    email: EmailStr
    asunto: str
    mensaje: str
    
    @validator('nombre')
    def validar_nombre(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('El nombre debe tener al menos 2 caracteres')
        if len(v.strip()) > 100:
            raise ValueError('El nombre no puede exceder 100 caracteres')
        return v.strip()
    
    @validator('telefono')
    def validar_telefono(cls, v):
        if v is not None and v.strip():
            import re
            if not re.match(r'^[\d\s\-\+\(\)]{8,20}$', v.strip()):
                raise ValueError('El formato del teléfono no es válido')
            return v.strip()
        return None
    
    @validator('asunto')
    def validar_asunto(cls, v):
        asuntos_validos = [
            'Consulta de Productos',
            'Cotización',
            'Servicio Post-Venta',
            'Reclamo',
            'Sugerencia',
            'Otro'
        ]
        if v not in asuntos_validos:
            raise ValueError('El asunto seleccionado no es válido')
        return v
    
    @validator('mensaje')
    def validar_mensaje(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('El mensaje debe tener al menos 10 caracteres')
        if len(v.strip()) > 2000:
            raise ValueError('El mensaje no puede exceder 2000 caracteres')
        return v.strip()

class ContactoUpdate(BaseModel):
    estado: Optional[str] = None
    notas_internas: Optional[str] = None
    respondido_por: Optional[str] = None
    
    @validator('estado')
    def validar_estado(cls, v):
        if v is not None:
            estados_validos = ['pendiente', 'en_proceso', 'resuelto']
            if v not in estados_validos:
                raise ValueError('El estado seleccionado no es válido')
        return v

class ContactoResponse(BaseModel):
    id: int
    nombre: str
    telefono: Optional[str]
    email: str
    asunto: str
    mensaje: str
    fecha_creacion: datetime
    estado: str
    notas_internas: Optional[str]
    respondido_por: Optional[str]
    fecha_respuesta: Optional[datetime]
    
    class Config:
        from_attributes = True

class ContactoStats(BaseModel):
    total: int
    pendientes: int
    en_proceso: int
    resueltos: int
    por_asunto: Dict[str, int]