from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.producto import Producto
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

@router.get("/productos")
async def listar_productos(request: Request, db: Session = Depends(get_db)):
    global_context = get_global_context(db)
    
    # Obtener todos los productos activos
    productos = db.query(Producto).filter(Producto.activo == True).all()
    
    return templates.TemplateResponse("productos.html", {
        "request": request,
        "productos": productos,
        **global_context
    })

@router.get("/producto/{producto_id}")
async def detalle_producto(producto_id: int, request: Request, db: Session = Depends(get_db)):
    global_context = get_global_context(db)
    
    # Buscar el producto específico
    producto = db.query(Producto).filter(
        Producto.id == producto_id,
        Producto.activo == True
    ).first()
    
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Incrementar vistas
    producto.vistas += 1
    db.commit()
    
    # Obtener productos relacionados de la misma categoría
    productos_relacionados = db.query(Producto).filter(
        Producto.categoria_id == producto.categoria_id,
        Producto.activo == True,
        Producto.id != producto.id
    ).limit(4).all()
    
    return templates.TemplateResponse("producto_detalle.html", {
        "request": request,
        "producto": producto,
        "productos_relacionados": productos_relacionados,
        **global_context
    })

@router.get("/productos/destacados")
async def productos_destacados(request: Request, db: Session = Depends(get_db)):
    global_context = get_global_context(db)
    
    # Obtener productos destacados
    productos = db.query(Producto).filter(
        Producto.activo == True,
        Producto.destacado == True
    ).all()
    
    return templates.TemplateResponse("productos_destacados.html", {
        "request": request,
        "productos": productos,
        **global_context
    })