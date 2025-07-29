# app/routes/catalogo_routes.py
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import json

# Importar según tu estructura
from app.database.database import get_db
from app.models import Categoria, Producto

# Configurar templates
templates = Jinja2Templates(directory="app/templates")

# Crear el router
router = APIRouter()

# Función helper para obtener categorías activas (igual que en main.py)
def get_categorias_navbar(db: Session):
    """Obtiene las categorías activas para mostrar en el navbar"""
    return db.query(Categoria).filter(Categoria.activo == True).order_by(Categoria.nombre).all()

# Context processor para datos globales del catálogo
async def get_catalogo_context(db: Session):
    """Context común para páginas del catálogo"""
    return {
        "categorias_nav": get_categorias_navbar(db),
        "config": {}  # Aquí puedes agregar configuraciones si las necesitas
    }

@router.get("/catalogo", response_class=HTMLResponse)
async def mostrar_catalogo(
    request: Request, 
    db: Session = Depends(get_db)
):
    """
    Página principal del catálogo editorial
    """
    try:
        # Obtener context global
        global_context = await get_catalogo_context(db)
        
        # Obtener todas las categorías activas
        categorias = db.query(Categoria).filter(
            Categoria.activo == True
        ).order_by(Categoria.nombre).all()
        
        # Obtener productos agrupados por categoría
        productos_por_categoria = {}
        total_productos = 0
        
        for categoria in categorias:
            productos = db.query(Producto).filter(
                Producto.categoria_id == categoria.id,
                Producto.activo == True
            ).order_by(
                Producto.destacado.desc(),  # Destacados primero
                Producto.nombre
            ).all()
            
            productos_por_categoria[categoria.id] = productos
            total_productos += len(productos)
        
        # Obtener productos destacados para mostrar primero
        productos_destacados = db.query(Producto).filter(
            Producto.activo == True,
            Producto.destacado == True
        ).limit(6).all()
        
        return templates.TemplateResponse("catalogo.html", {
            "request": request,
            "categorias": categorias,
            "productos_por_categoria": productos_por_categoria,
            "productos_destacados": productos_destacados,
            "total_productos": total_productos,
            "page_title": "Catálogo Editorial",
            "meta_description": f"Catálogo completo de JerkHome con {total_productos} productos en {len(categorias)} categorías",
            **global_context  # Incluye categorias_nav y config
        })
        
    except Exception as e:
        print(f"Error en catálogo: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar el catálogo")


@router.get("/catalogo/categoria/{categoria_id}", response_class=HTMLResponse)
async def catalogo_por_categoria(
    categoria_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Catálogo filtrado por categoría específica
    """
    try:
        # Obtener context global
        global_context = await get_catalogo_context(db)
        
        # Verificar que la categoría existe y está activa
        categoria = db.query(Categoria).filter(
            Categoria.id == categoria_id,
            Categoria.activo == True
        ).first()
        
        if not categoria:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
        
        # Obtener todos los productos de esta categoría
        productos = db.query(Producto).filter(
            Producto.categoria_id == categoria_id,
            Producto.activo == True
        ).order_by(
            Producto.destacado.desc(),
            Producto.nombre
        ).all()
        
        # Obtener todas las categorías para el nav
        todas_categorias = db.query(Categoria).filter(
            Categoria.activo == True
        ).order_by(Categoria.nombre).all()
        
        # Crear estructura para el template
        productos_por_categoria = {categoria_id: productos}
        
        return templates.TemplateResponse("catalogo.html", {
            "request": request,
            "categorias": [categoria],  # Solo la categoría seleccionada
            "categoria_actual": categoria,
            "productos_por_categoria": productos_por_categoria,
            "todas_categorias": todas_categorias,
            "filtro_categoria": True,
            "page_title": f"Catálogo - {categoria.nombre}",
            "meta_description": f"Catálogo de {categoria.nombre} - {len(productos)} productos disponibles",
            **global_context
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error en catálogo por categoría: {e}")
        raise HTTPException(status_code=500, detail="Error al cargar la categoría")


@router.get("/catalogo/api/productos")
async def api_productos_catalogo(
    request: Request,
    categoria_id: Optional[int] = None,
    destacados: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = 0,
    db: Session = Depends(get_db)
):
    """
    API para obtener productos del catálogo (para AJAX/JavaScript)
    """
    try:
        query = db.query(Producto).filter(Producto.activo == True)
        
        # Filtros opcionales
        if categoria_id:
            query = query.filter(Producto.categoria_id == categoria_id)
        
        if destacados is not None:
            query = query.filter(Producto.destacado == destacados)
        
        # Ordenamiento
        query = query.order_by(
            Producto.destacado.desc(),
            Producto.vistas.desc() if hasattr(Producto, 'vistas') else Producto.nombre,
            Producto.nombre
        )
        
        # Paginación
        if limit:
            query = query.offset(offset).limit(limit)
        
        productos = query.all()
        
        # Formatear respuesta JSON
        productos_data = []
        for producto in productos:
            categoria = db.query(Categoria).filter(
                Categoria.id == producto.categoria_id
            ).first()
            
            productos_data.append({
                "id": producto.id,
                "nombre": producto.nombre,
                "descripcion": producto.descripcion,
                "precio": float(producto.precio) if producto.precio else 0,
                "precio_oferta": float(producto.precio_oferta) if producto.precio_oferta else None,
                "sku": producto.sku,
                "stock": producto.stock,
                "imagen_1": producto.imagen_1,
                "categoria": {
                    "id": categoria.id,
                    "nombre": categoria.nombre
                } if categoria else None,
                "destacado": producto.destacado,
                "vistas": getattr(producto, 'vistas', 0)
            })
        
        return {"productos": productos_data, "total": len(productos_data)}
        
    except Exception as e:
        print(f"Error en API productos: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener productos")


@router.get("/catalogo/buscar", response_class=HTMLResponse)
async def buscar_en_catalogo(
    request: Request,
    q: str,
    categoria_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Búsqueda en el catálogo
    """
    try:
        # Obtener context global
        global_context = await get_catalogo_context(db)
        
        # Construir query de búsqueda
        query = db.query(Producto).filter(
            Producto.activo == True
        )
        
        # Filtro de búsqueda en nombre, descripción y SKU
        search_filter = (
            Producto.nombre.ilike(f"%{q}%") | 
            Producto.descripcion.ilike(f"%{q}%") |
            Producto.sku.ilike(f"%{q}%")
        )
        query = query.filter(search_filter)
        
        if categoria_id:
            query = query.filter(Producto.categoria_id == categoria_id)
        
        productos_encontrados = query.order_by(
            Producto.destacado.desc(),
            Producto.nombre
        ).all()
        
        # Obtener categorías para el filtro
        categorias = db.query(Categoria).filter(
            Categoria.activo == True
        ).order_by(Categoria.nombre).all()
        
        # Agrupar productos por categoría
        productos_por_categoria = {}
        for producto in productos_encontrados:
            cat_id = producto.categoria_id
            if cat_id not in productos_por_categoria:
                productos_por_categoria[cat_id] = []
            productos_por_categoria[cat_id].append(producto)
        
        return templates.TemplateResponse("catalogo.html", {
            "request": request,
            "categorias": categorias,
            "productos_por_categoria": productos_por_categoria,
            "busqueda": q,
            "resultados_busqueda": len(productos_encontrados),
            "page_title": f"Búsqueda: {q}",
            "meta_description": f"Resultados de búsqueda para '{q}' - {len(productos_encontrados)} productos encontrados",
            **global_context
        })
        
    except Exception as e:
        print(f"Error en búsqueda: {e}")
        raise HTTPException(status_code=500, detail="Error en la búsqueda")


@router.get("/catalogo/pdf")
async def generar_pdf_catalogo(
    request: Request,
    categoria_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Generar PDF del catálogo (datos preparados para PDF)
    """
    try:
        # Obtener datos
        if categoria_id:
            categoria = db.query(Categoria).filter(
                Categoria.id == categoria_id,
                Categoria.activo == True
            ).first()
            if not categoria:
                raise HTTPException(status_code=404, detail="Categoría no encontrada")
            
            productos = db.query(Producto).filter(
                Producto.categoria_id == categoria_id,
                Producto.activo == True
            ).all()
            titulo = f"Catálogo {categoria.nombre}"
        else:
            categorias = db.query(Categoria).filter(
                Categoria.activo == True
            ).all()
            productos = db.query(Producto).filter(
                Producto.activo == True
            ).all()
            titulo = "Catálogo Completo JerkHome"
        
        # Preparar datos para PDF
        productos_data = []
        for producto in productos:
            categoria = db.query(Categoria).filter(
                Categoria.id == producto.categoria_id
            ).first()
            
            productos_data.append({
                "nombre": producto.nombre,
                "descripcion": producto.descripcion or "Sin descripción",
                "precio": float(producto.precio) if producto.precio else 0,
                "precio_oferta": float(producto.precio_oferta) if producto.precio_oferta else None,
                "sku": producto.sku,
                "stock": producto.stock,
                "categoria": categoria.nombre if categoria else "Sin categoría",
                "imagen": producto.imagen_1 if hasattr(producto, 'imagen_1') else None
            })
        
        return {
            "titulo": titulo,
            "productos": productos_data,
            "total_productos": len(productos_data),
            "fecha_generacion": "2025",
            "empresa": "JerkHome - Fábrica de Muebles Tapizados",
            "mensaje": "Datos listos para generar PDF"
        }
        
    except Exception as e:
        print(f"Error generando PDF: {e}")
        raise HTTPException(status_code=500, detail="Error al generar PDF")


@router.get("/catalogo/stats")
async def estadisticas_catalogo(db: Session = Depends(get_db)):
    """
    Obtener estadísticas del catálogo
    """
    try:
        total_productos = db.query(Producto).filter(Producto.activo == True).count()
        total_categorias = db.query(Categoria).filter(Categoria.activo == True).count()
        productos_destacados = db.query(Producto).filter(
            Producto.activo == True,
            Producto.destacado == True
        ).count()
        
        # Categoría con más productos
        from sqlalchemy import func
        categoria_popular = db.query(
            Categoria.nombre,
            func.count(Producto.id).label('total_productos')
        ).join(Producto).filter(
            Categoria.activo == True,
            Producto.activo == True
        ).group_by(Categoria.id, Categoria.nombre).order_by(
            func.count(Producto.id).desc()
        ).first()
        
        # Precio promedio
        precio_promedio = db.query(func.avg(Producto.precio)).filter(
            Producto.activo == True,
            Producto.precio.isnot(None)
        ).scalar()
        
        return {
            "total_productos": total_productos,
            "total_categorias": total_categorias,
            "productos_destacados": productos_destacados,
            "precio_promedio": float(precio_promedio) if precio_promedio else 0,
            "categoria_mas_popular": {
                "nombre": categoria_popular[0] if categoria_popular else "N/A",
                "productos": categoria_popular[1] if categoria_popular else 0
            }
        }
        
    except Exception as e:
        print(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener estadísticas")


# Función auxiliar para verificar si una categoría tiene productos
def categoria_tiene_productos(categoria_id: int, db: Session) -> bool:
    """
    Verificar si una categoría tiene productos activos
    """
    count = db.query(Producto).filter(
        Producto.categoria_id == categoria_id,
        Producto.activo == True
    ).count()
    return count > 0