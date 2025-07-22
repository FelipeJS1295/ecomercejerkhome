from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import uuid
from random import randint

from app.database.database import get_db
from app.models import Producto, Categoria, Configuracion, Venta, EstadoPago, EstadoVenta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Modelos Pydantic para el checkout
class CartItem(BaseModel):
    id: int
    name: str
    price: float
    image: str
    quantity: int

class CustomerInfo(BaseModel):
    firstName: str
    lastName: str
    email: str  # Cambiar de EmailStr a str
    phone: str
    rut: str

class DeliveryInfo(BaseModel):
    address: str
    city: str
    comuna: str
    region: str = "Región Metropolitana"
    notes: Optional[str] = None

class PaymentInfo(BaseModel):
    method: str  # 'transfer' or 'cash'

class OrderData(BaseModel):
    customer: CustomerInfo
    delivery: DeliveryInfo
    payment: PaymentInfo
    items: List[CartItem]
    total: float

# Función helper para obtener configuraciones
def get_configuraciones(db: Session):
    configs = db.query(Configuracion).filter(Configuracion.activo == True).all()
    return {config.clave: config.valor for config in configs}

@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request, db: Session = Depends(get_db)):
    """Página de checkout"""
    configuraciones = get_configuraciones(db)
    
    return templates.TemplateResponse("checkout.html", {
        "request": request,
        "config": configuraciones
    })

@router.get("/checkout/confirmacion", response_class=HTMLResponse)
async def confirmacion_page(request: Request, order: Optional[str] = None, db: Session = Depends(get_db)):
    """Página de confirmación de pedido"""
    configuraciones = get_configuraciones(db)
    
    return templates.TemplateResponse("confirmacion.html", {
        "request": request,
        "order_id": order,
        "config": configuraciones
    })

@router.post("/api/checkout/validar-productos")
async def validar_productos_carrito(items: List[CartItem], db: Session = Depends(get_db)):
    """Validar que los productos del carrito existan y tengan stock"""
    productos_validados = []
    errores = []
    
    for item in items:
        producto = db.query(Producto).filter(
            Producto.id == item.id,
            Producto.activo == True
        ).first()
        
        if not producto:
            errores.append(f"El producto '{item.name}' ya no está disponible")
            continue
            
        if producto.stock < item.quantity:
            errores.append(f"Stock insuficiente para '{producto.nombre}'. Stock disponible: {producto.stock}")
            continue
            
        # Verificar precio actual
        precio_actual = producto.precio_oferta if producto.precio_oferta else producto.precio
        if abs(precio_actual - item.price) > 0.01:  # Permitir diferencias mínimas por redondeo
            errores.append(f"El precio de '{producto.nombre}' ha cambiado")
            continue
            
        productos_validados.append({
            "id": producto.id,
            "nombre": producto.nombre,
            "precio": precio_actual,
            "stock": producto.stock,
            "imagen": producto.imagen_1 or "/static/images/no-image.jpg"
        })
    
    return {
        "validos": len(errores) == 0,
        "productos": productos_validados,
        "errores": errores
    }

@router.post("/api/checkout/crear-pedido")
async def crear_pedido(order_data: OrderData, db: Session = Depends(get_db)):
    try:
        productos_validacion = await validar_productos_carrito(order_data.items, db)

        if not productos_validacion["validos"]:
            raise HTTPException(
                status_code=400,
                detail={"message": "Error en validación de productos", "errores": productos_validacion["errores"]}
            )

        ventas_creadas = []

        # 👇 Genera primero el número de orden
        numero_orden = f"OC{randint(10000000, 99999999)}"

        for item in order_data.items:
            producto = db.query(Producto).filter(Producto.id == item.id).first()
            if not producto:
                continue

            nueva_venta = Venta(
                orden_compra=numero_orden,  # ✅ ahora sí puedes usarlo
                rut_cliente=order_data.customer.rut,
                nombre_cliente=f"{order_data.customer.firstName} {order_data.customer.lastName}",
                direccion_cliente=order_data.delivery.address,
                comuna_cliente=order_data.delivery.comuna,
                region_cliente=order_data.delivery.region,
                numero_telefono=order_data.customer.phone,
                email=order_data.customer.email,
                sku=getattr(producto, 'sku', f"PROD{producto.id:03d}"),
                nombre=item.name,
                cantidad=item.quantity,
                precio=item.price,
                estado_pago=EstadoPago.PENDIENTE,
                estado_venta=EstadoVenta.NUEVA
            )

            db.add(nueva_venta)
            ventas_creadas.append(nueva_venta)

            if producto.stock >= item.quantity:
                producto.stock -= item.quantity
            else:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para {producto.nombre}")

        db.commit()

        for venta in ventas_creadas:
            db.refresh(venta)

        return {
            "success": True,
            "order_id": numero_orden,
            "message": "Pedido creado exitosamente",
            "total": order_data.total,
            "ventas_creadas": len(ventas_creadas),
            "payment_method": order_data.payment.method,
            "redirect_url": f"/webpay/pagar/{numero_orden}" if order_data.payment.method == "webpay" else f"/checkout/confirmacion?order={numero_orden}"
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print("⛔ ERROR EN CREAR PEDIDO:", str(e))
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")



@router.get("/api/checkout/pedido/{order_id}")
async def obtener_pedido(order_id: str, db: Session = Depends(get_db)):
    """Obtener detalles de un pedido específico desde la tabla ventas"""
    # Extraer el ID numérico del order_id (formato JH000001)
    try:
        venta_id = int(order_id.replace("JH", "").lstrip("0") or "0")
    except:
        raise HTTPException(status_code=400, detail="ID de pedido inválido")
    
    # Obtener todas las ventas relacionadas con este pedido
    ventas = db.query(Venta).filter(Venta.id >= venta_id).all()
    
    if not ventas:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    # Tomar la primera venta como referencia para datos del cliente
    venta_principal = ventas[0]
    
    # Construir items del pedido
    items = []
    total = 0
    for venta in ventas:
        items.append({
            "id": venta.id,
            "name": venta.nombre,
            "price": float(venta.precio),
            "quantity": venta.cantidad,
            "image": f"/static/images/productos/{venta.sku.lower()}.jpg"
        })
        total += float(venta.cantidad * venta.precio)
    
    return {
        "order_id": order_id,
        "status": venta_principal.estado_venta,
        "customer": {
            "firstName": venta_principal.nombre_cliente.split()[0],
            "lastName": " ".join(venta_principal.nombre_cliente.split()[1:]),
            "email": venta_principal.email,
            "phone": venta_principal.numero_telefono,
            "rut": venta_principal.rut_cliente
        },
        "delivery": {
            "address": venta_principal.direccion_cliente,
            "city": "Santiago",
            "comuna": venta_principal.comuna_cliente,
            "region": venta_principal.region_cliente,
            "notes": ""
        },
        "payment": {
            "method": "transfer",
            "status": venta_principal.estado_pago
        },
        "items": items,
        "total": total,
        "created_at": venta_principal.fecha_compra.isoformat(),
        "estimated_delivery": venta_principal.fecha_entrega.isoformat() if venta_principal.fecha_entrega else None
    }

@router.post("/api/carrito/agregar")
async def agregar_al_carrito(
    producto_id: int,
    quantity: int = 1,
    db: Session = Depends(get_db)
):
    """Validar producto antes de agregar al carrito"""
    producto = db.query(Producto).filter(
        Producto.id == producto_id,
        Producto.activo == True
    ).first()
    
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    if producto.stock < quantity:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Disponible: {producto.stock}")
    
    precio = producto.precio_oferta if producto.precio_oferta else producto.precio
    imagen = producto.imagen_1 or "/static/images/no-image.jpg"
    
    return {
        "success": True,
        "producto": {
            "id": producto.id,
            "name": producto.nombre,
            "price": precio,
            "image": f"/static/images/productos/{imagen}",
            "stock_disponible": producto.stock
        }
    }

@router.get("/api/productos/verificar-stock")
async def verificar_stock_productos(ids: str, db: Session = Depends(get_db)):
    """Verificar stock de múltiples productos (IDs separados por comas)"""
    try:
        producto_ids = [int(id_str.strip()) for id_str in ids.split(',') if id_str.strip()]
        
        productos = db.query(Producto).filter(
            Producto.id.in_(producto_ids),
            Producto.activo == True
        ).all()
        
        stock_info = {}
        for producto in productos:
            precio = producto.precio_oferta if producto.precio_oferta else producto.precio
            stock_info[producto.id] = {
                "nombre": producto.nombre,
                "stock": producto.stock,
                "precio": precio,
                "activo": producto.activo,
                "disponible": producto.stock > 0
            }
        
        return stock_info
        
    except ValueError:
        raise HTTPException(status_code=400, detail="IDs de productos inválidos")

@router.get("/api/checkout/shipping-info")
async def obtener_info_envio(comuna: str, db: Session = Depends(get_db)):
    """Obtener información de envío según la comuna"""
    # Configurar costos de envío por comuna
    envio_gratis_comunas = [
        "la-pintana", "puente-alto", "san-bernardo", 
        "el-bosque", "la-cisterna", "lo-espejo"
    ]
    
    if comuna.lower() in envio_gratis_comunas:
        costo_envio = 0
        tiempo_estimado = "3-5 días hábiles"
        mensaje = "¡Envío gratis a tu comuna!"
    else:
        costo_envio = 15000
        tiempo_estimado = "5-7 días hábiles"
        mensaje = "Envío disponible con costo adicional"
    
    return {
        "comuna": comuna,
        "costo_envio": costo_envio,
        "tiempo_estimado": tiempo_estimado,
        "mensaje": mensaje,
        "disponible": True
    }