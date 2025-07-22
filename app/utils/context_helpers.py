from sqlalchemy.orm import Session
from app.models import Categoria, Configuracion

def get_categorias_navbar(db: Session):
    """Obtiene las categorías activas para mostrar en el navbar"""
    return db.query(Categoria).filter(Categoria.activo == True).order_by(Categoria.nombre).all()

def get_configuraciones(db: Session):
    """Obtiene las configuraciones activas"""
    configs = db.query(Configuracion).filter(Configuracion.activo == True).all()
    return {config.clave: config.valor for config in configs}

def get_global_context(db: Session):
    """Context común para todas las páginas"""
    return {
        "categorias_nav": get_categorias_navbar(db),
        "config": get_configuraciones(db)
    }