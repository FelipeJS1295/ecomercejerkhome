from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.producto import Producto
from app.models.categoria import Categoria
import os
import shutil
from typing import List, Optional
import uuid

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

# Asegurar que existe el directorio de imágenes
UPLOAD_DIR = "app/static/images/productos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/productos/nuevo")
async def nuevo_producto_form(request: Request, db: Session = Depends(get_db)):
    categorias = db.query(Categoria).filter(Categoria.activo == True).all()
    return templates.TemplateResponse("admin/producto_form.html", {
        "request": request,
        "categorias": categorias,
        "producto": None,
        "accion": "Crear"
    })

@router.post("/productos/nuevo")
async def crear_producto(
    request: Request,
    sku: str = Form(...),
    nombre: str = Form(...),
    descripcion: str = Form(""),
    precio: float = Form(...),
    precio_oferta: Optional[float] = Form(None),
    stock: int = Form(0),
    categoria_id: int = Form(...),
    destacado: bool = Form(False),
    activo: bool = Form(True),
    imagen_1: Optional[UploadFile] = File(None),
    imagen_2: Optional[UploadFile] = File(None),
    imagen_3: Optional[UploadFile] = File(None),
    imagen_4: Optional[UploadFile] = File(None),
    imagen_5: Optional[UploadFile] = File(None),
    imagen_6: Optional[UploadFile] = File(None),
    imagen_7: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    # Verificar que el SKU no exista
    existing_producto = db.query(Producto).filter(Producto.sku == sku).first()
    if existing_producto:
        categorias = db.query(Categoria).filter(Categoria.activo == True).all()
        return templates.TemplateResponse("admin/producto_form.html", {
            "request": request,
            "categorias": categorias,
            "producto": None,
            "accion": "Crear",
            "error": "El SKU ya existe"
        })
    
    # Crear el producto
    producto_data = {
        "sku": sku,
        "nombre": nombre,
        "descripcion": descripcion,
        "precio": precio,
        "precio_oferta": precio_oferta if precio_oferta and precio_oferta > 0 else None,
        "stock": stock,
        "categoria_id": categoria_id,
        "destacado": destacado,
        "activo": activo
    }
    
    # Procesar imágenes
    imagenes = [imagen_1, imagen_2, imagen_3, imagen_4, imagen_5, imagen_6, imagen_7]
    for i, imagen in enumerate(imagenes, 1):
        if imagen and imagen.filename:
            # Generar nombre único para la imagen
            file_extension = imagen.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            # Guardar la imagen
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(imagen.file, buffer)
            
            producto_data[f"imagen_{i}"] = unique_filename
    
    # Crear producto en la base de datos
    nuevo_producto = Producto(**producto_data)
    db.add(nuevo_producto)
    db.commit()
    db.refresh(nuevo_producto)
    
    return RedirectResponse(url="/admin/productos", status_code=status.HTTP_302_FOUND)

@router.get("/productos/{producto_id}/editar")
async def editar_producto_form(producto_id: int, request: Request, db: Session = Depends(get_db)):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    categorias = db.query(Categoria).filter(Categoria.activo == True).all()
    return templates.TemplateResponse("admin/producto_form.html", {
        "request": request,
        "categorias": categorias,
        "producto": producto,
        "accion": "Editar"
    })

@router.post("/productos/{producto_id}/editar")
async def actualizar_producto(
    producto_id: int,
    request: Request,
    sku: str = Form(...),
    nombre: str = Form(...),
    descripcion: str = Form(""),
    precio: float = Form(...),
    precio_oferta: Optional[float] = Form(None),
    stock: int = Form(0),
    categoria_id: int = Form(...),
    destacado: bool = Form(False),
    activo: bool = Form(True),
    imagen_1: Optional[UploadFile] = File(None),
    imagen_2: Optional[UploadFile] = File(None),
    imagen_3: Optional[UploadFile] = File(None),
    imagen_4: Optional[UploadFile] = File(None),
    imagen_5: Optional[UploadFile] = File(None),
    imagen_6: Optional[UploadFile] = File(None),
    imagen_7: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Verificar que el SKU no exista en otro producto
    existing_producto = db.query(Producto).filter(
        Producto.sku == sku,
        Producto.id != producto_id
    ).first()
    if existing_producto:
        categorias = db.query(Categoria).filter(Categoria.activo == True).all()
        return templates.TemplateResponse("admin/producto_form.html", {
            "request": request,
            "categorias": categorias,
            "producto": producto,
            "accion": "Editar",
            "error": "El SKU ya existe en otro producto"
        })
    
    # Actualizar datos básicos
    producto.sku = sku
    producto.nombre = nombre
    producto.descripcion = descripcion
    producto.precio = precio
    producto.precio_oferta = precio_oferta if precio_oferta and precio_oferta > 0 else None
    producto.stock = stock
    producto.categoria_id = categoria_id
    producto.destacado = destacado
    producto.activo = activo
    
    # Procesar imágenes nuevas
    imagenes = [imagen_1, imagen_2, imagen_3, imagen_4, imagen_5, imagen_6, imagen_7]
    for i, imagen in enumerate(imagenes, 1):
        if imagen and imagen.filename:
            # Eliminar imagen anterior si existe
            imagen_anterior = getattr(producto, f"imagen_{i}")
            if imagen_anterior:
                old_file_path = os.path.join(UPLOAD_DIR, imagen_anterior)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
            
            # Guardar nueva imagen
            file_extension = imagen.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(imagen.file, buffer)
            
            setattr(producto, f"imagen_{i}", unique_filename)
    
    db.commit()
    return RedirectResponse(url="/admin/productos", status_code=status.HTTP_302_FOUND)

@router.get("/productos/{producto_id}/eliminar")
async def eliminar_producto(producto_id: int, request: Request, db: Session = Depends(get_db)):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Eliminar imágenes del servidor
    for i in range(1, 8):
        imagen = getattr(producto, f"imagen_{i}")
        if imagen:
            file_path = os.path.join(UPLOAD_DIR, imagen)
            if os.path.exists(file_path):
                os.remove(file_path)
    
    # Eliminar producto de la base de datos
    db.delete(producto)
    db.commit()
    
    return RedirectResponse(url="/admin/productos", status_code=status.HTTP_302_FOUND)