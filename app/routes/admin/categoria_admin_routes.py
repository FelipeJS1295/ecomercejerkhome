from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.categoria import Categoria
from app.models.producto import Producto
import os
import shutil
import re
from typing import Optional

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

# Asegurar que existe el directorio de imágenes de categorías
UPLOAD_DIR = "app/static/images/categorias"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def normalizar_nombre_archivo(nombre):
    """Convierte el nombre de la categoría en un nombre de archivo válido"""
    # Convertir a minúsculas y reemplazar caracteres especiales
    nombre_limpio = re.sub(r'[^a-zA-Z0-9\s]', '', nombre.lower())
    # Reemplazar espacios con guiones bajos
    nombre_limpio = re.sub(r'\s+', '_', nombre_limpio.strip())
    return nombre_limpio

@router.get("/categorias/nueva")
async def nueva_categoria_form(request: Request):
    return templates.TemplateResponse("admin/categoria_form.html", {
        "request": request,
        "categoria": None,
        "accion": "Crear"
    })

@router.post("/categorias/nueva")
async def crear_categoria(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    activo: bool = Form(True),
    imagen: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    # Verificar que el nombre no exista
    existing_categoria = db.query(Categoria).filter(Categoria.nombre == nombre).first()
    if existing_categoria:
        return templates.TemplateResponse("admin/categoria_form.html", {
            "request": request,
            "categoria": None,
            "accion": "Crear",
            "error": "Ya existe una categoría con este nombre"
        })
    
    # Procesar imagen si se subió
    imagen_filename = None
    if imagen and imagen.filename:
        # Generar nombre descriptivo para la imagen
        file_extension = imagen.filename.split(".")[-1]
        nombre_normalizado = normalizar_nombre_archivo(nombre)
        imagen_filename = f"imagen_{nombre_normalizado}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, imagen_filename)
        
        # Guardar la imagen
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(imagen.file, buffer)
    
    # Crear la categoría
    nueva_categoria = Categoria(
        nombre=nombre,
        descripcion=descripcion,
        imagen=imagen_filename,
        activo=activo
    )
    
    db.add(nueva_categoria)
    db.commit()
    db.refresh(nueva_categoria)
    
    return RedirectResponse(url="/admin/categorias", status_code=status.HTTP_302_FOUND)

@router.get("/categorias/{categoria_id}/editar")
async def editar_categoria_form(categoria_id: int, request: Request, db: Session = Depends(get_db)):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    return templates.TemplateResponse("admin/categoria_form.html", {
        "request": request,
        "categoria": categoria,
        "accion": "Editar"
    })

@router.post("/categorias/{categoria_id}/editar")
async def actualizar_categoria(
    categoria_id: int,
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    activo: bool = Form(True),
    imagen: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    # Verificar que el nombre no exista en otra categoría
    existing_categoria = db.query(Categoria).filter(
        Categoria.nombre == nombre,
        Categoria.id != categoria_id
    ).first()
    if existing_categoria:
        return templates.TemplateResponse("admin/categoria_form.html", {
            "request": request,
            "categoria": categoria,
            "accion": "Editar",
            "error": "Ya existe otra categoría con este nombre"
        })
    
    # Procesar nueva imagen si se subió
    if imagen and imagen.filename:
        # Eliminar imagen anterior si existe
        if categoria.imagen:
            old_file_path = os.path.join(UPLOAD_DIR, categoria.imagen)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        
        # Generar nombre descriptivo para la nueva imagen
        file_extension = imagen.filename.split(".")[-1]
        nombre_normalizado = normalizar_nombre_archivo(nombre)
        imagen_filename = f"imagen_{nombre_normalizado}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, imagen_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(imagen.file, buffer)
        
        categoria.imagen = imagen_filename
    elif categoria.nombre != nombre:
        # Si cambió el nombre de la categoría pero no subió nueva imagen, renombrar la imagen existente
        if categoria.imagen:
            old_file_path = os.path.join(UPLOAD_DIR, categoria.imagen)
            if os.path.exists(old_file_path):
                file_extension = categoria.imagen.split(".")[-1]
                nombre_normalizado = normalizar_nombre_archivo(nombre)
                nuevo_nombre = f"imagen_{nombre_normalizado}.{file_extension}"
                new_file_path = os.path.join(UPLOAD_DIR, nuevo_nombre)
                
                # Renombrar archivo
                os.rename(old_file_path, new_file_path)
                categoria.imagen = nuevo_nombre
    
    # Actualizar categoría
    categoria.nombre = nombre
    categoria.descripcion = descripcion
    categoria.activo = activo
    
    db.commit()
    return RedirectResponse(url="/admin/categorias", status_code=status.HTTP_302_FOUND)

@router.get("/categorias/{categoria_id}/eliminar")
async def eliminar_categoria(categoria_id: int, request: Request, db: Session = Depends(get_db)):
    categoria = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    
    # Verificar si tiene productos asociados
    productos_asociados = db.query(Producto).filter(Producto.categoria_id == categoria_id).count()
    if productos_asociados > 0:
        categorias = db.query(Categoria).all()
        return templates.TemplateResponse("admin/categorias.html", {
            "request": request,
            "categorias": categorias,
            "error": f"No se puede eliminar la categoría '{categoria.nombre}' porque tiene {productos_asociados} productos asociados"
        })
    
    # Eliminar imagen si existe
    if categoria.imagen:
        file_path = os.path.join(UPLOAD_DIR, categoria.imagen)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Eliminar categoría
    db.delete(categoria)
    db.commit()
    
    return RedirectResponse(url="/admin/categorias", status_code=status.HTTP_302_FOUND)