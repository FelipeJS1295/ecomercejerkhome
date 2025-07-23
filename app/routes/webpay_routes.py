from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import json
import logging
from datetime import datetime
import os
from app.models import Venta, EstadoPago, EstadoVenta

# Importaciones de Transbank
from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_type import IntegrationType

from app.database.database import get_db
from app.models import Venta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración según el ambiente
ENVIRONMENT = os.getenv("ENVIRONMENT", "testing")

if ENVIRONMENT == "production":
    COMMERCE_CODE = os.getenv("WEBPAY_COMMERCE_CODE")
    API_KEY = os.getenv("WEBPAY_API_KEY") 
    INTEGRATION_TYPE = IntegrationType.LIVE
    
    if not COMMERCE_CODE or not API_KEY:
        raise ValueError("En producción debes configurar WEBPAY_COMMERCE_CODE y WEBPAY_API_KEY")
else:
    COMMERCE_CODE = "52991676"
    API_KEY = "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C"
    INTEGRATION_TYPE = IntegrationType.TEST

# Inicializar WebPay con las opciones
webpay_options = WebpayOptions(COMMERCE_CODE, API_KEY, INTEGRATION_TYPE)
transaction = Transaction(webpay_options)

@router.post("/webpay/iniciar")
async def iniciar_transaccion_webpay(
    request: Request,
    monto: int = Form(...),
    orden: str = Form(...),
    db: Session = Depends(get_db)
):
    """Iniciar transacción WebPay Plus"""
    try:
        logger.info(f"Iniciando transacción - Orden: {orden}, Monto: {monto}")
        
        if monto <= 0:
            raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
        
        if not orden:
            raise HTTPException(status_code=400, detail="El número de orden es obligatorio")
        
        venta = db.query(Venta).filter(Venta.orden_compra == orden).first()
        
        if not venta:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        session_id = f"session_{orden}_{datetime.now().timestamp()}"
        base_url = str(request.base_url).rstrip('/')
        return_url = f"{base_url}/webpay/confirmar"
        
        logger.info(f"URL de retorno: {return_url}")
        
        # 🚨 Intenta crear la transacción
        response = transaction.create(
            buy_order=orden,
            session_id=session_id,
            amount=monto,
            return_url=return_url
        )

        # ✅ Verificación adicional para evitar el error 'NoneType'
        if not response or 'url' not in response or 'token' not in response:
            raise HTTPException(status_code=500, detail="No se pudo iniciar la transacción con Webpay")
        
        logger.info(f"Respuesta WebPay: {response}")
        
        venta.estado_pago = EstadoPago.PENDIENTE
        db.commit()
        
        webpay_url = f"{response['url']}?token_ws={response['token']}"
        logger.info(f"Redirigiendo a WebPay: {webpay_url}")
        
        return RedirectResponse(url=webpay_url, status_code=303)
        
    except Exception as e:
        logger.error(f"Error iniciando transacción: {str(e)}")
        return templates.TemplateResponse("webpay_error.html", {
            "request": request,
            "error_message": f"Error al procesar el pago: {str(e)}",
            "numero_orden": orden,
            "datetime": datetime
        })


@router.post("/webpay/confirmar")
@router.get("/webpay/confirmar")
async def confirmar_pago_webpay(
    request: Request,
    token_ws: str = Form(None),
    db: Session = Depends(get_db)
):
    """Confirmar transacción WebPay Plus"""
    try:
        # El token puede venir por POST o GET
        if not token_ws:
            token_ws = request.query_params.get('token_ws')
        
        if not token_ws:
            raise HTTPException(status_code=400, detail="Token de transacción no encontrado")
        
        logger.info(f"Confirmando transacción con token: {token_ws}")
        
        # Confirmar transacción con WebPay
        result = transaction.commit(token_ws)
        
        logger.info(f"Resultado WebPay: {json.dumps(result, indent=2)}")
        
        # Extraer información de la respuesta
        buy_order = result.get('buy_order')
        status = result.get('status')
        amount = result.get('amount')
        authorization_code = result.get('authorization_code')
        payment_type_code = result.get('payment_type_code')
        response_code = result.get('response_code')
        
        # Buscar las ventas asociadas a esta orden
        ventas = db.query(Venta).filter(Venta.orden_compra == buy_order).all()
        
        if not ventas:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Si el pago fue exitoso, actualizar las ventas
        if status == 'AUTHORIZED':
            for venta in ventas:
                venta.estado_pago = EstadoPago.PAGADA
                venta.estado_venta = EstadoVenta.NUEVA
            
            db.commit()
            logger.info(f"Pago exitoso - Orden: {buy_order}, Autorización: {authorization_code}")
            
            # Página de éxito
            return templates.TemplateResponse("webpay_exito.html", {
                "request": request,
                "buy_order": buy_order,
                "amount": amount,
                "authorization_code": authorization_code,
                "tipo_pago": get_payment_type_description(payment_type_code),
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ventas": ventas
            })
        else:
            # Pago fallido
            for venta in ventas:
                venta.estado_pago = EstadoPago.ANULADA
            
            db.commit()
            logger.warning(f"Pago fallido - Orden: {buy_order}, Status: {status}")
            
            return templates.TemplateResponse("webpay_error.html", {
                "request": request,
                "buy_order": buy_order,
                "amount": amount,
                "response_code": response_code,
                "error_message": get_response_description(response_code)
            })
        
    except Exception as e:
        logger.error(f"Error confirmando transacción: {str(e)}")
        
        return templates.TemplateResponse("webpay_error.html", {
            "request": request,
            "error_message": f"Error procesando el resultado del pago: {str(e)}",
            "token": token_ws
        })

@router.get("/webpay/pagar/{order_id}")
async def pagina_pago_webpay(
    request: Request, 
    order_id: str,
    db: Session = Depends(get_db)
):
    """Página para iniciar el pago con Webpay"""
    try:
        # Obtener el pedido
        ventas = db.query(Venta).filter(Venta.orden_compra == order_id).all()
        
        if not ventas:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        
        # Calcular total
        total = sum(venta.cantidad * venta.precio for venta in ventas)
        
        return templates.TemplateResponse("webpay_pago.html", {
            "request": request,
            "order_id": order_id,
            "total": int(total),  # Webpay requiere entero
            "ventas": ventas
        })
        
    except Exception as e:
        logger.error(f"Error en página de pago: {str(e)}")
        raise HTTPException(status_code=500, detail="Error cargando página de pago")

@router.get("/webpay/estado/{order_id}")
async def consultar_estado_pago(
    order_id: str,
    db: Session = Depends(get_db)
):
    """Consultar estado de un pago"""
    try:
        ventas = db.query(Venta).filter(Venta.orden_compra == order_id).all()

        
        if not ventas:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        
        venta = ventas[0]
        
        return {
            "order_id": order_id,
            "estado_pago": venta.estado_pago,
            "estado_venta": venta.estado_venta,
            "total": sum(v.cantidad * v.precio for v in ventas),
            "cliente": venta.nombre_cliente
        }
        
    except Exception as e:
        logger.error(f"Error consultando estado: {str(e)}")
        raise HTTPException(status_code=500, detail="Error consultando estado del pago")

def get_payment_type_description(payment_type_code):
    """Obtener descripción del tipo de pago"""
    types = {
        'VD': 'Tarjeta de Débito',
        'VN': 'Tarjeta de Crédito',
        'VC': 'Tarjeta de Crédito',
        'SI': 'Sin Interés',
        'S2': '2 cuotas sin interés',
        'S3': '3 cuotas sin interés',
        'N2': '2 cuotas con interés',
        'N3': '3 cuotas con interés',
        'N4': '4 cuotas con interés'
    }
    return types.get(payment_type_code, f'Tipo {payment_type_code}')

def get_response_description(response_code):
    """Obtener descripción del código de respuesta"""
    codes = {
        '0': 'Transacción aprobada',
        '-1': 'Rechazo - Transacción rechazada',
        '-2': 'Transacción debe reintentarse',
        '-3': 'Error en transacción',
        '-4': 'Rechazo - Transacción rechazada',
        '-5': 'Rechazo - Transacción rechazada',
        '-6': 'Rechazo - Transacción rechazada',
        '-7': 'Rechazo - Transacción rechazada',
        '-8': 'Rechazo - Transacción rechazada'
    }
    return codes.get(str(response_code), f'Código {response_code}')