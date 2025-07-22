from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.configuracion import Configuracion
import os
import shutil
import uuid
from typing import Optional

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

# Asegurar que existe el directorio de imágenes
UPLOAD_DIR = "app/static/images/config"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/configuracion")
async def admin_configuracion(request: Request, db: Session = Depends(get_db)):
    # Obtener configuraciones agrupadas por categoría
    configuraciones = db.query(Configuracion).filter(Configuracion.activo == True).all()
    
    # Agrupar por categoría
    config_por_categoria = {}
    for config in configuraciones:
        if config.categoria not in config_por_categoria:
            config_por_categoria[config.categoria] = []
        config_por_categoria[config.categoria].append(config)
    
    return templates.TemplateResponse("admin/configuracion.html", {
        "request": request,
        "config_por_categoria": config_por_categoria
    })

@router.post("/configuracion/actualizar")
async def actualizar_configuracion(
    request: Request,
    db: Session = Depends(get_db)
):
    # Obtener todas las configuraciones
    configuraciones = db.query(Configuracion).all()
    form_data = await request.form()
    
    success_count = 0
    error_messages = []
    
    for config in configuraciones:
        clave = config.clave
        
        if config.tipo == "imagen":
            # Manejar archivos de imagen
            archivo = form_data.get(f"{clave}_file")
            if archivo and hasattr(archivo, 'filename') and archivo.filename:
                try:
                    # Eliminar imagen anterior si existe
                    if config.valor:
                        old_file_path = os.path.join(UPLOAD_DIR, config.valor)
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    
                    # Guardar nueva imagen
                    file_extension = archivo.filename.split(".")[-1]
                    unique_filename = f"{uuid.uuid4()}.{file_extension}"
                    file_path = os.path.join(UPLOAD_DIR, unique_filename)
                    
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(archivo.file, buffer)
                    
                    config.valor = unique_filename
                    success_count += 1
                except Exception as e:
                    error_messages.append(f"Error al subir imagen {config.descripcion}: {str(e)}")
            else:
                # Si no hay archivo nuevo, mantener el valor actual
                continue
        else:
            # Manejar otros tipos de campos
            nuevo_valor = form_data.get(clave)
            if nuevo_valor is not None:
                if config.tipo == "boolean":
                    config.valor = "true" if nuevo_valor else "false"
                else:
                    config.valor = nuevo_valor
                success_count += 1
    
    try:
        db.commit()
        # Redirigir con mensaje de éxito
        return RedirectResponse(
            url="/admin/configuracion?success=true", 
            status_code=status.HTTP_302_FOUND
        )
    except Exception as e:
        db.rollback()
        error_messages.append(f"Error al guardar en base de datos: {str(e)}")
        return RedirectResponse(
            url="/admin/configuracion?error=true", 
            status_code=status.HTTP_302_FOUND
        )

@router.get("/configuracion/nueva")
async def nueva_configuracion_form(request: Request):
    return templates.TemplateResponse("admin/configuracion_form.html", {
        "request": request,
        "configuracion": None,
        "accion": "Crear"
    })

@router.post("/configuracion/nueva")
async def crear_configuracion(
    request: Request,
    clave: str = Form(...),
    valor: str = Form(""),
    tipo: str = Form(...),
    categoria: str = Form(...),
    descripcion: str = Form(""),
    activo: bool = Form(True),
    db: Session = Depends(get_db)
):
    # Verificar que la clave no exista
    existing_config = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if existing_config:
        return templates.TemplateResponse("admin/configuracion_form.html", {
            "request": request,
            "configuracion": None,
            "accion": "Crear",
            "error": "Ya existe una configuración con esta clave"
        })
    
    # Crear nueva configuración
    nueva_config = Configuracion(
        clave=clave,
        valor=valor,
        tipo=tipo,
        categoria=categoria,
        descripcion=descripcion,
        activo=activo
    )
    
    db.add(nueva_config)
    db.commit()
    
    return RedirectResponse(url="/admin/configuracion", status_code=status.HTTP_302_FOUND)

@router.get("/configuracion/{config_id}/eliminar")
async def eliminar_configuracion(config_id: int, request: Request, db: Session = Depends(get_db)):
    config = db.query(Configuracion).filter(Configuracion.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuración no encontrada")
    
    # Eliminar imagen si existe
    if config.tipo == "imagen" and config.valor:
        file_path = os.path.join(UPLOAD_DIR, config.valor)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Eliminar configuración
    db.delete(config)
    db.commit()
    
    return RedirectResponse(url="/admin/configuracion", status_code=status.HTTP_302_FOUND)