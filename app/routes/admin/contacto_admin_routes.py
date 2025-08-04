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
from app.models.contacto import Contacto, ContactoUpdate, ContactoResponse, ContactoStats
from app.models import Configuracion, Categoria
from app.auth.auth_utils import require_admin

# Router para administración de contactos
router = APIRouter(prefix="/admin/contactos", tags=["admin-contactos"])

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
# RUTAS DE ADMINISTRACIÓN
# =============================================================================

@router.get("/", response_class=HTMLResponse)
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
    
    # Obtener mensajes de éxito/error
    success = request.query_params.get('success')
    error = request.query_params.get('error')
    
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
        "success": success,
        "error": error,
        "current_user": current_user,
        **global_context
    })

@router.get("/{contacto_id}", response_class=HTMLResponse)
async def ver_contacto(
    request: Request,
    contacto_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Ver detalles de un contacto específico"""
    contacto = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not contacto:
        return RedirectResponse(
            url="/admin/contactos?error=Contacto no encontrado",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    global_context = await get_global_context(db)
    
    # Obtener mensajes de éxito/error
    success = request.query_params.get('success')
    error = request.query_params.get('error')
    
    return templates.TemplateResponse("admin/contacto_detalle.html", {
        "request": request,
        "contacto": contacto,
        "success": success,
        "error": error,
        "current_user": current_user,
        **global_context
    })

@router.post("/{contacto_id}/actualizar")
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
        return RedirectResponse(
            url="/admin/contactos?error=Contacto no encontrado",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    try:
        # Actualizar estado
        if estado and estado in Contacto.get_estados_disponibles():
            contacto.estado = estado
            
            # Si se marca como resuelto, guardar quién lo resolvió
            if estado == 'resuelto' and not contacto.fecha_respuesta:
                contacto.respondido_por = f"{current_user.get('nombre', '')} {current_user.get('apellido', '')}".strip() or 'Administrador'
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

@router.post("/{contacto_id}/eliminar")
async def eliminar_contacto(
    contacto_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Eliminar un contacto específico"""
    contacto = db.query(Contacto).filter(Contacto.id == contacto_id).first()
    if not contacto:
        return RedirectResponse(
            url="/admin/contactos?error=Contacto no encontrado",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
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

@router.get("/exportar/csv")
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
            media_type='text/csv; charset=utf-8',
            headers=headers
        )
        
    except Exception as e:
        print(f"Error exportando contactos: {e}")
        return RedirectResponse(
            url="/admin/contactos?error=Error al exportar contactos",
            status_code=status.HTTP_303_SEE_OTHER
        )

@router.post("/acciones-masivas")
async def acciones_masivas_contactos(
    request: Request,
    accion: str = Form(...),
    contacto_ids: List[int] = Form(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Realizar acciones en múltiples contactos"""
    
    if not contacto_ids:
        return RedirectResponse(
            url="/admin/contactos?error=No se seleccionaron contactos",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    try:
        contactos = db.query(Contacto).filter(Contacto.id.in_(contacto_ids)).all()
        usuario_actual = f"{current_user.get('nombre', '')} {current_user.get('apellido', '')}".strip() or 'Administrador'
        
        if accion == 'marcar_pendiente':
            for contacto in contactos:
                contacto.estado = 'pendiente'
            mensaje = f'{len(contactos)} contactos marcados como pendientes'
            
        elif accion == 'marcar_proceso':
            for contacto in contactos:
                contacto.estado = 'en_proceso'
            mensaje = f'{len(contactos)} contactos marcados como en proceso'
            
        elif accion == 'marcar_resuelto':
            for contacto in contactos:
                if contacto.estado != 'resuelto':
                    contacto.estado = 'resuelto'
                    contacto.respondido_por = usuario_actual
                    contacto.fecha_respuesta = datetime.utcnow()
            mensaje = f'{len(contactos)} contactos marcados como resueltos'
            
        elif accion == 'eliminar':
            for contacto in contactos:
                db.delete(contacto)
            mensaje = f'{len(contactos)} contactos eliminados'
        
        else:
            return RedirectResponse(
                url="/admin/contactos?error=Acción no válida",
                status_code=status.HTTP_303_SEE_OTHER
            )
        
        db.commit()
        
        return RedirectResponse(
            url=f"/admin/contactos?success={mensaje}",
            status_code=status.HTTP_303_SEE_OTHER
        )
        
    except Exception as e:
        db.rollback()
        print(f"Error en acción masiva: {e}")
        return RedirectResponse(
            url="/admin/contactos?error=Error al procesar la acción masiva",
            status_code=status.HTTP_303_SEE_OTHER
        )

# =============================================================================
# API ENDPOINTS
# =============================================================================

@router.get("/api/stats", response_model=ContactoStats)
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

@router.get("/api/recientes", response_model=List[ContactoResponse])
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