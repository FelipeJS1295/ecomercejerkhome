from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from app.database.database import Base
import enum

class RolUsuario(str, enum.Enum):
    ADMIN = "ADMIN"
    VENDEDOR = "VENDEDOR"
    OPERADOR = "OPERADOR"

class EstadoUsuario(str, enum.Enum):
    ACTIVO = "ACTIVO"
    INACTIVO = "INACTIVO"
    SUSPENDIDO = "SUSPENDIDO"

class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Información personal
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    telefono = Column(String(20), nullable=True)
    
    # Credenciales
    username = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Roles y permisos
    rol = Column(Enum(RolUsuario), nullable=False, default=RolUsuario.OPERADOR)
    estado = Column(Enum(EstadoUsuario), nullable=False, default=EstadoUsuario.ACTIVO)
    
    # Control de acceso
    ultimo_acceso = Column(DateTime, nullable=True)
    intentos_fallidos = Column(Integer, default=0)
    bloqueado_hasta = Column(DateTime, nullable=True)
    
    # Configuración
    cambiar_password = Column(Boolean, default=True)  # Forzar cambio en primer login
    
    # Timestamps automáticos
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, username='{self.username}', rol='{self.rol}')>"
    
    @property
    def nombre_completo(self):
        """Retorna el nombre completo del usuario"""
        return f"{self.nombre} {self.apellido}"
    
    @property
    def is_admin(self):
        """Verifica si el usuario es administrador"""
        return self.rol == RolUsuario.ADMIN
    
    @property
    def is_active(self):
        """Verifica si el usuario está activo"""
        return self.estado == EstadoUsuario.ACTIVO
    
    @property
    def is_blocked(self):
        """Verifica si el usuario está bloqueado"""
        if self.bloqueado_hasta:
            from datetime import datetime
            return datetime.now() < self.bloqueado_hasta
        return False