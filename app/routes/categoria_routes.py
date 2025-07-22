from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.categoria import Categoria
from app.models.configuracion import Configuracion

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Función helper para obtener configuraciones
def get_configuraciones(db: Session):
    configs = db.query(Configuracion).filter(Configuracion.activo == True).all()
    return {config.clave: config.valor for config in configs}

# Función helper para obtener categorías del navbar
def get_categorias_navbar(db: Session):
    """Obtiene las categorías activas para mostrar en el navbar"""
    return db.query(Categoria).filter(Categoria.activo == True).order_by(Categoria.nombre).all()

# Context global para todas las páginas
def get_global_context(db: Session):
    """Context común para todas las páginas"""
    return {
        "categorias_nav": get_categorias_navbar(db),
        "config": get_configuraciones(db)
    }

@router.get("/categorias")
async def listar_categorias(request: Request, db: Session = Depends(get_db)):
    global_context = get_global_context(db)
    
    # Todas las categorías activas para mostrar en la página
    categorias = global_context["categorias_nav"]
    
    return templates.TemplateResponse("categorias.html", {
        "request": request, 
        "categorias": categorias,
        **global_context
    })

@router.get("/categoria/{categoria_nombre}")
async def productos_por_categoria(categoria_nombre: str, request: Request, db: Session = Depends(get_db)):
    global_context = get_global_context(db)
    
    # Buscar la categoría específica
    categoria = db.query(Categoria).filter(
        Categoria.nombre.ilike(f"%{categoria_nombre}%"),
        Categoria.activo == True
    ).first()
    
    if not categoria:
        return templates.TemplateResponse("404.html", {
            "request": request,
            **global_context
        }, status_code=404)
    
    return templates.TemplateResponse("categoria_detalle.html", {
        "request": request,
        "categoria": categoria,
        "productos": categoria.productos,
        **global_context
    })