from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, Boolean, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.database import Base
from datetime import datetime
import enum

# Enums para los estados y tipos
class EstadoTransaccion(str, enum.Enum):
    INICIADA = "iniciada"
    COMPLETADA = "completada"
    FALLIDA = "fallida"
    ANULADA = "anulada"

class TipoLog(str, enum.Enum):
    ERROR_INICIO = "error_inicio"
    ERROR_CONFIRMACION = "error_confirmacion"
    TRANSACCION_INICIADA = "transaccion_iniciada"
    TRANSACCION_CONFIRMADA = "transaccion_confirmada"
    DEBUG = "debug"
    WARNING = "warning"

class AmbienteWebpay(str, enum.Enum):
    TESTING = "testing"
    PRODUCTION = "production"

class TransaccionWebpay(Base):
    __tablename__ = "transacciones_webpay"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    numero_orden = Column(String(20), nullable=False, index=True)
    token = Column(String(255), nullable=False, index=True)
    session_id = Column(String(255), nullable=False)
    monto = Column(Integer, nullable=False)  # Monto en pesos chilenos sin decimales
    estado = Column(Enum(EstadoTransaccion), nullable=False, default=EstadoTransaccion.INICIADA, index=True)
    authorization_code = Column(String(50), nullable=True)
    payment_type_code = Column(String(10), nullable=True)
    response_code = Column(Integer, nullable=True)
    resultado_completo = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    
    def __repr__(self):
        return f"<TransaccionWebpay(orden={self.numero_orden}, estado={self.estado}, monto={self.monto})>"
    
    @property
    def es_exitosa(self):
        """Verifica si la transacción fue exitosa"""
        return self.estado == EstadoTransaccion.COMPLETADA and self.response_code == 0
    
    @property
    def tipo_pago_descripcion(self):
        """Retorna la descripción del tipo de pago"""
        tipos = {
            'VD': 'Tarjeta de Débito',
            'VN': 'Tarjeta de Crédito',
            'VC': 'Tarjeta de Crédito',
            'SI': 'Sin Interés',
            'S2': '2 cuotas sin interés',
            'S3': '3 cuotas sin interés',
            'N2': '2 cuotas con interés',
            'N3': '3 cuotas con interés',
            'N4': '4 cuotas con interés'
        }
        return tipos.get(self.payment_type_code, f'Tipo {self.payment_type_code}')
    
    def marcar_como_completada(self, authorization_code, payment_type_code, response_code, resultado_completo):
        """Marca la transacción como completada"""
        self.estado = EstadoTransaccion.COMPLETADA
        self.authorization_code = authorization_code
        self.payment_type_code = payment_type_code
        self.response_code = response_code
        self.resultado_completo = resultado_completo
        self.updated_at = datetime.now()
    
    def marcar_como_fallida(self, response_code, resultado_completo):
        """Marca la transacción como fallida"""
        self.estado = EstadoTransaccion.FALLIDA
        self.response_code = response_code
        self.resultado_completo = resultado_completo
        self.updated_at = datetime.now()

class LogWebpay(Base):
    __tablename__ = "logs_webpay"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    numero_orden = Column(String(20), nullable=True, index=True)
    token = Column(String(255), nullable=True, index=True)
    tipo = Column(Enum(TipoLog), nullable=False, index=True)
    mensaje = Column(Text, nullable=False)
    datos_adicionales = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now(), index=True)
    
    def __repr__(self):
        return f"<LogWebpay(tipo={self.tipo}, orden={self.numero_orden})>"
    
    @classmethod
    def crear_log(cls, tipo, mensaje, numero_orden=None, token=None, datos_adicionales=None, ip_address=None, user_agent=None):
        """Método de clase para crear un log"""
        return cls(
            tipo=tipo,
            mensaje=mensaje,
            numero_orden=numero_orden,
            token=token,
            datos_adicionales=datos_adicionales,
            ip_address=ip_address,
            user_agent=user_agent
        )

class ConfiguracionWebpay(Base):
    __tablename__ = "configuracion_webpay"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ambiente = Column(Enum(AmbienteWebpay), nullable=False, default=AmbienteWebpay.TESTING)
    commerce_code = Column(String(50), nullable=False)
    api_key = Column(String(255), nullable=False)  # Debería estar encriptada en producción
    activo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ConfiguracionWebpay(ambiente={self.ambiente}, activo={self.activo})>"
    
    @classmethod
    def obtener_configuracion_activa(cls, db_session, ambiente=AmbienteWebpay.TESTING):
        """Obtiene la configuración activa para un ambiente específico"""
        return db_session.query(cls).filter(
            cls.ambiente == ambiente,
            cls.activo == True
        ).first()

class EstadisticaWebpay(Base):
    __tablename__ = "estadisticas_webpay"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column(DateTime, nullable=False, unique=True, index=True)
    total_transacciones = Column(Integer, nullable=False, default=0)
    transacciones_exitosas = Column(Integer, nullable=False, default=0)
    transacciones_fallidas = Column(Integer, nullable=False, default=0)
    monto_total = Column(Integer, nullable=False, default=0)  # En pesos chilenos
    monto_exitoso = Column(Integer, nullable=False, default=0)  # En pesos chilenos
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<EstadisticaWebpay(fecha={self.fecha}, total={self.total_transacciones})>"
    
    @property
    def tasa_exito(self):
        """Calcula la tasa de éxito de transacciones"""
        if self.total_transacciones == 0:
            return 0
        return (self.transacciones_exitosas / self.total_transacciones) * 100
    
    @property
    def monto_promedio(self):
        """Calcula el monto promedio de transacciones exitosas"""
        if self.transacciones_exitosas == 0:
            return 0
        return self.monto_exitoso / self.transacciones_exitosas
    
    @classmethod
    def actualizar_estadisticas_hoy(cls, db_session):
        """Actualiza las estadísticas del día actual"""
        from datetime import date
        from sqlalchemy import func
        
        hoy = date.today()
        
        # Obtener estadísticas de transacciones de hoy
        stats = db_session.query(
            func.count(TransaccionWebpay.id).label('total'),
            func.sum(func.case([(TransaccionWebpay.estado == EstadoTransaccion.COMPLETADA, 1)], else_=0)).label('exitosas'),
            func.sum(func.case([(TransaccionWebpay.estado == EstadoTransaccion.FALLIDA, 1)], else_=0)).label('fallidas'),
            func.sum(TransaccionWebpay.monto).label('monto_total'),
            func.sum(func.case([(TransaccionWebpay.estado == EstadoTransaccion.COMPLETADA, TransaccionWebpay.monto)], else_=0)).label('monto_exitoso')
        ).filter(
            func.date(TransaccionWebpay.created_at) == hoy
        ).first()
        
        # Buscar o crear registro de estadísticas
        estadistica = db_session.query(cls).filter(func.date(cls.fecha) == hoy).first()
        
        if not estadistica:
            estadistica = cls(fecha=hoy)
            db_session.add(estadistica)
        
        # Actualizar valores
        estadistica.total_transacciones = stats.total or 0
        estadistica.transacciones_exitosas = stats.exitosas or 0
        estadistica.transacciones_fallidas = stats.fallidas or 0
        estadistica.monto_total = stats.monto_total or 0
        estadistica.monto_exitoso = stats.monto_exitoso or 0
        
        db_session.commit()
        return estadistica