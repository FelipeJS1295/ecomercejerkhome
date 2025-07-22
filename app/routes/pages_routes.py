from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.configuracion import Configuracion
from app.models.categoria import Categoria

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

@router.get("/nosotros")
async def nosotros(request: Request, db: Session = Depends(get_db)):
    global_context = get_global_context(db)
    
    return templates.TemplateResponse("nosotros.html", {
        "request": request,
        **global_context
    })

@router.get("/contacto")
async def contacto(request: Request, db: Session = Depends(get_db)):
    global_context = get_global_context(db)
    
    return templates.TemplateResponse("contacto.html", {
        "request": request,
        **global_context
    })

@router.post("/contacto")
async def enviar_contacto(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(""),
    asunto: str = Form(...),
    mensaje: str = Form(...),
    db: Session = Depends(get_db)
):
    # Por ahora solo redirigimos con mensaje de éxito
    # Más adelante se puede implementar envío de email
    
    global_context = get_global_context(db)
    
    return templates.TemplateResponse("contacto.html", {
        "request": request,
        "success": f"Gracias {nombre}, tu mensaje ha sido enviado correctamente. Te contactaremos pronto.",
        **global_context
    })