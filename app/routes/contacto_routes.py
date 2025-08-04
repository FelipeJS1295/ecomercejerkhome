from fastapi import APIRouter, Depends, HTTPException, Query, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import datetime, timedelta
import csv
from io import StringIO

from app.database.database import get_db
from app.models.contacto import Contacto, ContactoCreate, ContactoUpdate, ContactoResponse, ContactoStats
from app.models import Configuracion, Categoria
from app.auth.auth_utils import get_current_user, require_admin  # Ajustar según tu sistema de auth

# Router para contactos
router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

# Funciones helper (compatibles con tu estructura existente)
def get_categorias_navbar(db: Session):
    """Obtiene las categorías activas para mostrar en el navbar"""
    return db.query(Categoria).filter(Categoria.activo == True).order_by(Categoria.nombre).all()

def get_configuraciones(db: Session):
    """Obtiene configuraciones del sitio"""
    configs = db.query(Configuracion).filter(Configuracion.activo == True).all()
    return {config.clave: config.valor for config in configs}

async def get_global_context(db: Session):
    """Context común para todas las páginas"""
    return {
        "categorias_nav": get_categorias_navbar(db),
        "config": get_configuraciones(db)
    }

# =============================================================================
# RUTAS PÚBLICAS
# =============================================================================

@router.post("/contacto")
async def procesar_contacto(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    telefono: Optional[str] = Form(None),
    asunto: str = Form(...),
    mensaje: str = Form(...),
    db: Session = Depends(get_db)
):
    """Procesar formulario de contacto"""
    try:
        # Validar datos usando Pydantic
        contacto_data = ContactoCreate(
            nombre=nombre,
            email=email,
            telefono=telefono,
            asunto=asunto,
            mensaje=mensaje
        )
        
        # Crear nuevo contacto
        nuevo_contacto = Contacto(
            nombre=contacto_data.nombre,
            telefono=contacto_data.telefono,
            email=contacto_data.email,
            asunto=contacto_data.asunto,
            mensaje=contacto_data.mensaje
        )
        
        # Guardar en la base de datos
        db.add(nuevo_contacto)
        db.commit()
        db.refresh(nuevo_contacto)
        
        # Enviar notificación (opcional)
        try:
            await enviar_notificacion_contacto(nuevo_contacto, db)
        except Exception as e:
            print(f"Error enviando notificación: {e}")
        
        # Obtener contexto global para la respuesta
        global_context = await get_global_context(db)
        
        # Mostrar página de éxito
        return templates.TemplateResponse("contacto.html", {
            "request": request,
            "success": "¡Gracias por contactarnos! Tu mensaje ha sido enviado correctamente. Nos pondremos en contacto contigo pronto.",
            **global_context
        })
        
    except ValueError as e:
        # Errores de validación
        global_context = await get_global_context(db)
        return templates.TemplateResponse("contacto.html", {
            "request": request,
            "error": str(e),
            "form_data": {
                "nombre": nombre,
                "email": email,
                "telefono": telefono,
                "asunto": asunto,
                "mensaje": mensaje
            },
            **global_context
        })
    
    except Exception as e:
        db.rollback()
        print(f"Error procesando contacto: {e}")
        global_context = await get_global_context(db)
        return templates.TemplateResponse("contacto.html", {
            "request": request,
            "error": "Ocurrió un error al procesar tu mensaje. Por favor, intenta nuevamente.",
            "form_data": {
                "nombre": nombre,
                "email": email,
                "telefono": telefono,
                "asunto": asunto,
                "mensaje": mensaje
            },
            **global_context
        })

# =============================================================================
# RUTAS DE ADMINISTRACIÓN
# =============================================================================

@router.get("/admin/contactos", response_class=HTMLResponse)
async def admin_contactos(
    request: Request,
    page: int = Query(1, ge=1),
    estado: Optional[str] = Query(None),
    asunto: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    nombre: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Panel de administración de contactos"""
    
    # Query base
    query = db.query(Contacto)
    
    # Aplicar filtros
    if estado:
        query = query.filter(Contacto.estado == estado)
    if asunto:
        query = query.filter(Contacto.asunto == asunto)
    if email:
        query = query.filter(Contacto.email.contains(email))
    if nombre:
        query = query.filter(Contacto.nombre.contains(nombre))
    
    # Contar total
    total = query.count()
    
    # Aplicar paginación
    per_page = 20
    offset = (page - 1) * per_page
    contactos = query.order_by(desc(Contacto.fecha_creacion)).offset(offset).limit(per_page).all()
    
    # Calcular número de páginas
    pages = (total + per_page - 1) // per_page
    
    # Estadísticas
    stats = {
        'total': db.query(Contacto).count(),
        'pendientes': db.query(Contacto).filter_by(estado='pendiente').count(),
        'en_proceso': db.query(Contacto).filter_by(estado='en_proceso').count(),
        'resueltos': db.query(Contacto).filter_by(estado='resuelto').count()
    }
    
    # Obtener contexto global
    global_context = await get_global_context(db)
    
    return templates.TemplateResponse("admin/contactos.html", {
        "request": request,
        "contactos": contactos,
        "stats": stats,
        "estados": Contacto.get_estados_disponibles(),
        "asuntos": Contacto.get_asuntos_disponibles(),
        "current_page": page,
        "total_pages": pages,
        "total": total,
        "estado_filter": estado,
        "asunto_filter": asunto,
        "email_filter": email,
        "nombre_filter": nombre,
        **global_context
    })

@router.get("/admin/contactos/{contacto_id}", response_class=HTMLResponse)
async def ver_contacto(
    request: Request,
    contacto_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Ver detalles de un contacto específico"""
    contacto = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not contacto:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    
    global_context = await get_global_context(db)
    
    return templates.TemplateResponse("admin/ver_contacto.html", {
        "request": request,
        "contacto": contacto,
        **global_context
    })

@router.post("/admin/contactos/{contacto_id}/actualizar")
async def actualizar_contacto(
    contacto_id: int,
    estado: Optional[str] = Form(None),
    notas_internas: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Actualizar estado y notas de un contacto"""
    contacto = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not contacto:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    
    try:
        # Actualizar estado
        if estado and estado in Contacto.get_estados_disponibles():
            contacto.estado = estado
            
            # Si se marca como resuelto, guardar quién lo resolvió
            if estado == 'resuelto' and not contacto.fecha_respuesta:
                contacto.respondido_por = current_user.get('nombre', 'Administrador')
                contacto.fecha_respuesta = datetime.utcnow()
        
        # Actualizar notas
        if notas_internas:
            contacto.notas_internas = notas_internas
        
        db.commit()
        
        # Redireccionar con mensaje de éxito
        return RedirectResponse(
            url=f"/admin/contactos/{contacto_id}?success=Contacto actualizado correctamente",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except Exception as e:
        db.rollback()
        print(f"Error actualizando contacto: {e}")
        return RedirectResponse(
            url=f"/admin/contactos/{contacto_id}?error=Error al actualizar el contacto",
            status_code=status.HTTP_303_SEE_OTHER
        )

@router.post("/admin/contactos/{contacto_id}/eliminar")
async def eliminar_contacto(
    contacto_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Eliminar un contacto específico"""
    contacto = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not contacto:
        raise HTTPException(status_code=404, detail="Contacto no encontrado")
    
    try:
        nombre_contacto = contacto.nombre
        db.delete(contacto)
        db.commit()
        
        return RedirectResponse(
            url=f"/admin/contactos?success=Contacto de {nombre_contacto} eliminado correctamente",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except Exception as e:
        db.rollback()
        print(f"Error eliminando contacto: {e}")
        return RedirectResponse(
            url="/admin/contactos?error=Error al eliminar el contacto",
            status_code=status.HTTP_303_SEE_OTHER
        )

@router.get("/admin/contactos/exportar/csv")
async def exportar_contactos_csv(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Exportar contactos a CSV"""
    try:
        # Crear CSV en memoria
        output = StringIO()
        writer = csv.writer(output)
        
        # Headers
        writer.writerow([
            'ID', 'Nombre', 'Email', 'Teléfono', 'Asunto', 'Mensaje',
            'Estado', 'Fecha Creación', 'Respondido Por', 'Fecha Respuesta'
        ])
        
        # Datos
        contactos = db.query(Contacto).order_by(desc(Contacto.fecha_creacion)).all()
        for contacto in contactos:
            writer.writerow([
                contacto.id,
                contacto.nombre,
                contacto.email,
                contacto.telefono or '',
                contacto.asunto,
                contacto.mensaje,
                contacto.estado,
                contacto.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                contacto.respondido_por or '',
                contacto.fecha_respuesta.strftime('%d/%m/%Y %H:%M') if contacto.fecha_respuesta else ''
            ])
        
        # Preparar respuesta
        output.seek(0)
        content = output.getvalue()
        
        headers = {
            'Content-Disposition': f'attachment; filename=contactos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        }
        
        return Response(
            content=content,
            media_type='text/csv',
            headers=headers
        )
        
    except Exception as e:
        print(f"Error exportando contactos: {e}")
        raise HTTPException(status_code=500, detail="Error al exportar contactos")

# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/api/contactos/stats", response_model=ContactoStats)
async def api_contactos_stats(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """API para estadísticas de contactos"""
    try:
        stats = {
            'total': db.query(Contacto).count(),
            'pendientes': db.query(Contacto).filter_by(estado='pendiente').count(),
            'en_proceso': db.query(Contacto).filter_by(estado='en_proceso').count(),
            'resueltos': db.query(Contacto).filter_by(estado='resuelto').count(),
            'por_asunto': {}
        }
        
        # Estadísticas por asunto
        asuntos_stats = db.query(
            Contacto.asunto, 
            func.count(Contacto.id)
        ).group_by(Contacto.asunto).all()
        
        for asunto, count in asuntos_stats:
            stats['por_asunto'][asunto] = count
        
        return stats
        
    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@router.get("/api/contactos/recientes", response_model=List[ContactoResponse])
async def api_contactos_recientes(
    dias: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """API para contactos recientes"""
    try:
        fecha_limite = datetime.utcnow() - timedelta(days=dias)
        contactos = db.query(Contacto).filter(
            Contacto.fecha_creacion >= fecha_limite
        ).order_by(desc(Contacto.fecha_creacion)).all()
        
        return contactos
        
    except Exception as e:
        print(f"Error obteniendo contactos recientes: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo contactos recientes")

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

async def enviar_notificacion_contacto(contacto: Contacto, db: Session):
    """Envía notificación por email cuando se recibe un nuevo contacto"""
    try:
        # Por ahora solo logueamos la información
        print(f"📧 Nuevo contacto recibido:")
        print(f"   - Nombre: {contacto.nombre}")
        print(f"   - Email: {contacto.email}")
        print(f"   - Asunto: {contacto.asunto}")
        print(f"   - Fecha: {contacto.fecha_creacion}")
        
        # TODO: Implementar envío real de email
        config = get_configuraciones(db)
        admin_email = config.get('admin_email')
        
        if admin_email:
            # Aquí iría la lógica de envío de email
            pass
        
    except Exception as e:
        print(f"Error enviando notificación de contacto: {e}")