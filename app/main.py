from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from app.database.database import engine, get_db
from app.models import Categoria, Producto, Configuracion, Venta, TransaccionWebpay, LogWebpay, ConfiguracionWebpay, Usuario
from app.routes.categoria_routes import router as categoria_router
from app.routes.producto_routes import router as producto_router
from app.routes.pages_routes import router as pages_router
from app.routes.auth_routes import router as auth_router
from app.routes.admin.admin_routes import router as admin_router
from app.routes.admin.producto_admin_routes import router as producto_admin_router
from app.routes.admin.categoria_admin_routes import router as categoria_admin_router
from app.routes.admin.configuracion_admin_routes import router as configuracion_admin_router
from app.routes.admin.venta_admin_routes import router as venta_admin_router
from app.routes.admin.usuario_admin_routes import router as usuario_admin_router
from app.routes.checkout_routes import router as checkout_router
from app.routes.webpay_routes import router as webpay_router

# Crear las tablas en la base de datos
Categoria.metadata.create_all(bind=engine)
Producto.metadata.create_all(bind=engine)
Configuracion.metadata.create_all(bind=engine)
Venta.metadata.create_all(bind=engine)
TransaccionWebpay.metadata.create_all(bind=engine)
LogWebpay.metadata.create_all(bind=engine)
ConfiguracionWebpay.metadata.create_all(bind=engine)
Usuario.metadata.create_all(bind=engine)

# Crear la aplicación FastAPI
app = FastAPI(title="JerkHome - Fábrica de Muebles Tapizados")

# Configurar archivos estáticos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Configurar templates Jinja2
templates = Jinja2Templates(directory="app/templates")

# Función helper para obtener categorías activas para el navbar
def get_categorias_navbar(db: Session):
    """Obtiene las categorías activas para mostrar en el navbar"""
    return db.query(Categoria).filter(Categoria.activo == True).order_by(Categoria.nombre).all()

# Función helper para obtener configuraciones
def get_configuraciones(db: Session):
    configs = db.query(Configuracion).filter(Configuracion.activo == True).all()
    return {config.clave: config.valor for config in configs}

# Context processor para datos globales
async def get_global_context(db: Session = Depends(get_db)):
    """Context común para todas las páginas"""
    return {
        "categorias_nav": get_categorias_navbar(db),
        "config": get_configuraciones(db)
    }

# Incluir rutas ANTES de definir las rutas principales
app.include_router(auth_router)
app.include_router(categoria_router)
app.include_router(producto_router)
app.include_router(pages_router)
app.include_router(admin_router)
app.include_router(producto_admin_router)
app.include_router(categoria_admin_router)
app.include_router(configuracion_admin_router)
app.include_router(venta_admin_router)
app.include_router(usuario_admin_router)
app.include_router(checkout_router)
app.include_router(webpay_router)

# Ruta principal actualizada
@app.get("/")
async def home(request: Request, db: Session = Depends(get_db)):
    # Obtener context global
    global_context = await get_global_context(db)
    
    # Obtener solo las primeras 3 categorías para mostrar en el index
    categorias_principales = global_context["categorias_nav"][:3]
    
    # Obtener productos destacados
    productos_destacados = db.query(Producto).filter(
        Producto.activo == True,
        Producto.destacado == True
    ).limit(3).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "categorias": categorias_principales,  # Para la sección de categorías del index
        "productos_destacados": productos_destacados,
        **global_context  # Incluye categorias_nav y config
    })

# Ruta de categorías (si no está en category_routes)
@app.get("/categorias")
async def categorias_page(request: Request, db: Session = Depends(get_db)):
    global_context = await get_global_context(db)
    
    # Todas las categorías activas
    todas_categorias = global_context["categorias_nav"]
    
    return templates.TemplateResponse("categorias.html", {
        "request": request,
        "categorias": todas_categorias,
        **global_context
    })

# Ruta de categoría individual (si no está en category_routes)
@app.get("/categoria/{categoria_nombre}")
async def categoria_detalle(categoria_nombre: str, request: Request, db: Session = Depends(get_db)):
    global_context = await get_global_context(db)
    
    # Buscar la categoría específica
    categoria = db.query(Categoria).filter(
        Categoria.nombre.ilike(categoria_nombre),
        Categoria.activo == True
    ).first()
    
    if not categoria:
        # Manejar error 404
        return templates.TemplateResponse("404.html", {
            "request": request,
            **global_context
        }, status_code=404)
    
    # Obtener productos de esta categoría (si tienes relación)
    # productos = db.query(Producto).filter(Producto.categoria_id == categoria.id).all()
    
    return templates.TemplateResponse("categoria_detalle.html", {
        "request": request,
        "categoria": categoria,
        # "productos": productos,
        **global_context
    })

# Ruta de productos (si no está en product_routes)
@app.get("/productos")
async def productos_page(request: Request, db: Session = Depends(get_db)):
    global_context = await get_global_context(db)
    
    # Obtener todos los productos activos
    productos = db.query(Producto).filter(Producto.activo == True).all()
    
    return templates.TemplateResponse("productos.html", {
        "request": request,
        "productos": productos,
        **global_context
    })

# Ruta nosotros (si no está en pages_routes)
@app.get("/nosotros")
async def nosotros_page(request: Request, db: Session = Depends(get_db)):
    global_context = await get_global_context(db)
    
    return templates.TemplateResponse("nosotros.html", {
        "request": request,
        **global_context
    })

# Ruta contacto (si no está en pages_routes)
@app.get("/contacto")
async def contacto_page(request: Request, db: Session = Depends(get_db)):
    global_context = await get_global_context(db)
    
    return templates.TemplateResponse("contacto.html", {
        "request": request,
        **global_context
    })

# Middleware para añadir contexto global (alternativa más elegante)
@app.middleware("http")
async def add_global_context_middleware(request: Request, call_next):
    response = await call_next(request)
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)