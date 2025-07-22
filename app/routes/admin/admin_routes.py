from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.producto import Producto
from app.models.categoria import Categoria
from app.models.configuracion import Configuracion
from app.models.ventas import Venta
from app.models.usuario import Usuario
from app.middleware.auth_middleware import require_auth
from .producto_admin_routes import router as producto_admin_router
from .categoria_admin_routes import router as categoria_admin_router
from .configuracion_admin_routes import router as configuracion_admin_router
from .venta_admin_routes import router as venta_admin_router
from .usuario_admin_routes import router as usuario_admin_router

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

# Incluir los routers
router.include_router(producto_admin_router)
router.include_router(categoria_admin_router)
router.include_router(configuracion_admin_router)
router.include_router(venta_admin_router)
router.include_router(usuario_admin_router)

@router.get("/")
async def admin_dashboard(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth)  # <- AGREGAR PROTECCIÓN
):
    try:
        # Estadísticas para el dashboard
        total_productos = db.query(Producto).count()
        productos_activos = db.query(Producto).filter(Producto.activo == True).count()
        productos_destacados = db.query(Producto).filter(Producto.destacado == True).count()
        total_categorias = db.query(Categoria).count()
        total_configuraciones = db.query(Configuracion).count()
        total_ventas = db.query(Venta).count()
        total_usuarios = db.query(Usuario).count()
        
        # Productos con bajo stock
        productos_bajo_stock = db.query(Producto).filter(
            Producto.stock <= 5,
            Producto.activo == True
        ).limit(5).all()
        
        # Productos más vistos
        productos_mas_vistos = db.query(Producto).filter(
            Producto.activo == True
        ).order_by(Producto.vistas.desc()).limit(5).all()
        
        stats = {
            "total_productos": total_productos,
            "productos_activos": productos_activos,
            "productos_destacados": productos_destacados,
            "total_categorias": total_categorias,
            "total_configuraciones": total_configuraciones,
            "total_ventas": total_ventas,
            "total_usuarios": total_usuarios,
            "productos_bajo_stock": productos_bajo_stock,
            "productos_mas_vistos": productos_mas_vistos
        }
        
        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request,
            "stats": stats,
            "current_user": current_user
        })
    
    except HTTPException as e:
        if e.status_code == 302:  # Redirección al login
            return RedirectResponse(url="/login", status_code=302)
        raise e

@router.get("/productos")
async def admin_productos(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth)  # <- AGREGAR PROTECCIÓN
):
    try:
        productos = db.query(Producto).all()
        return templates.TemplateResponse("admin/productos.html", {
            "request": request,
            "productos": productos,
            "current_user": current_user
        })
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(url="/login", status_code=302)
        raise e

@router.get("/categorias")
async def admin_categorias(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_auth)  # <- AGREGAR PROTECCIÓN
):
    try:
        categorias = db.query(Categoria).all()
        return templates.TemplateResponse("admin/categorias.html", {
            "request": request,
            "categorias": categorias,
            "current_user": current_user
        })
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(url="/login", status_code=302)
        raise e