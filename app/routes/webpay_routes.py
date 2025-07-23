from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
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

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔧 FORZAR MODO TESTING MIENTRAS SE COMPLETA CERTIFICACIÓN
ENVIRONMENT = "testing"

if ENVIRONMENT == "production":
    COMMERCE_CODE = os.getenv("WEBPAY_COMMERCE_CODE")
    API_KEY = os.getenv("WEBPAY_API_KEY") 
    INTEGRATION_TYPE = IntegrationType.LIVE
    
    if not COMMERCE_CODE or not API_KEY:
        logger.warning("⚠️ Credenciales de producción no configuradas, usando testing")
        COMMERCE_CODE = "597055555532"
        API_KEY = "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C"
        INTEGRATION_TYPE = IntegrationType.TEST
else:
    # Credenciales oficiales de testing de Transbank
    COMMERCE_CODE = "597055555532"
    API_KEY = "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C"
    INTEGRATION_TYPE = IntegrationType.TEST

# 📝 Logging para debugging
logger.info(f"🔧 Ambiente WebPay: {ENVIRONMENT}")
logger.info(f"🏪 Commerce Code: {COMMERCE_CODE}")
logger.info(f"🔑 API Key configurada: {'Sí' if API_KEY else 'No'}")
logger.info(f"🌐 Integration Type: {INTEGRATION_TYPE}")

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
        logger.info(f"🚀 Iniciando transacción - Orden: {orden}, Monto: {monto}")
        
        if monto <= 0:
            raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
        
        if not orden:
            raise HTTPException(status_code=400, detail="El número de orden es obligatorio")
        
        # Verificar que la venta existe
        venta = db.query(Venta).filter(Venta.orden_compra == orden).first()
        if not venta:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        
        # Verificar si ya existe una transacción para esta orden
        check_sql = text("""
            SELECT token, estado FROM transacciones_webpay 
            WHERE numero_orden = :orden 
            AND estado IN ('iniciada', 'completada')
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        existing = db.execute(check_sql, {'orden': orden}).fetchone()
        
        if existing:
            if existing.estado == 'completada':
                raise HTTPException(status_code=400, detail="Esta orden ya fue pagada")
            else:
                # Si hay una transacción iniciada, la reutilizamos
                logger.info(f"🔄 Reutilizando transacción existente: {existing.token}")
                webpay_url = f"https://webpay3gint.transbank.cl/webpayserver/initTransaction?token_ws={existing.token}"
                return RedirectResponse(url=webpay_url, status_code=303)
        
        session_id = f"session_{orden}_{datetime.now().timestamp()}"
        base_url = str(request.base_url).rstrip('/')
        return_url = f"{base_url}/webpay/confirmar"
        
        logger.info(f"🔗 URL de retorno: {return_url}")
        
        # 🚨 Crear la transacción con WebPay
        response = transaction.create(
            buy_order=orden,
            session_id=session_id,
            amount=monto,
            return_url=return_url
        )

        if not response or 'url' not in response or 'token' not in response:
            error_msg = "No se pudo iniciar la transacción con Webpay"
            logger.error(f"❌ {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        logger.info(f"✅ Respuesta WebPay: {response}")
        
        # 💾 CREAR REGISTRO CON SQL DIRECTO (evita problemas de enum)
        try:
            sql_insert = text("""
                INSERT INTO transacciones_webpay 
                (numero_orden, token, session_id, monto, estado, created_at) 
                VALUES (:orden, :token, :session_id, :monto, 'iniciada', NOW())
            """)
            
            db.execute(sql_insert, {
                'orden': orden,
                'token': response['token'],
                'session_id': session_id,
                'monto': monto
            })
            
            # Actualizar estado de la venta
            venta.estado_pago = EstadoPago.PENDIENTE
            
            db.commit()
            
            logger.info(f"💾 Transacción creada con SQL directo - Token: {response['token']}")
            
        except Exception as e:
            logger.error(f"❌ Error creando transacción: {str(e)}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Error guardando transacción")
        
        webpay_url = f"{response['url']}?token_ws={response['token']}"
        logger.info(f"🔄 Redirigiendo a WebPay: {webpay_url}")
        
        return RedirectResponse(url=webpay_url, status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error iniciando transacción: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
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
    TBK_TOKEN: str = Form(None),
    TBK_ID_SESION: str = Form(None), 
    TBK_ORDEN_COMPRA: str = Form(None),
    db: Session = Depends(get_db)
):
    """Confirmar transacción WebPay Plus o manejar cancelaciones"""
    try:
        # 🚫 VERIFICAR SI ES UNA CANCELACIÓN POR EL USUARIO
        if not token_ws:
            token_ws = request.query_params.get('token_ws')
        
        # Obtener parámetros de cancelación de query params también
        if not TBK_TOKEN:
            TBK_TOKEN = request.query_params.get('TBK_TOKEN')
        if not TBK_ID_SESION:
            TBK_ID_SESION = request.query_params.get('TBK_ID_SESION')
        if not TBK_ORDEN_COMPRA:
            TBK_ORDEN_COMPRA = request.query_params.get('TBK_ORDEN_COMPRA')
        
        # Si hay TBK_TOKEN, es una cancelación
        if TBK_TOKEN:
            logger.info(f"🚫 Transacción cancelada por el usuario")
            logger.info(f"   Token: {TBK_TOKEN}")
            logger.info(f"   Sesión: {TBK_ID_SESION}")
            logger.info(f"   Orden: {TBK_ORDEN_COMPRA}")
            
            # Actualizar estado en la base de datos
            update_sql = text("""
                UPDATE transacciones_webpay 
                SET estado = 'anulada', updated_at = NOW()
                WHERE token = :token OR numero_orden = :orden
            """)
            
            db.execute(update_sql, {
                'token': TBK_TOKEN,
                'orden': TBK_ORDEN_COMPRA
            })
            
            # Actualizar estado de la venta si existe
            if TBK_ORDEN_COMPRA:
                ventas = db.query(Venta).filter(Venta.orden_compra == TBK_ORDEN_COMPRA).all()
                for venta in ventas:
                    venta.estado_pago = EstadoPago.ANULADA
            
            db.commit()
            
            # Retornar página de cancelación
            return templates.TemplateResponse("webpay_cancelado.html", {
                "request": request,
                "orden": TBK_ORDEN_COMPRA,
                "token": TBK_TOKEN,
                "mensaje": "Transacción cancelada por el usuario",
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            })
        
        # Si no hay token_ws ni TBK_TOKEN, error
        if not token_ws:
            raise HTTPException(status_code=400, detail="Token de transacción no encontrado")
        
        # 🔍 PROCESO NORMAL DE CONFIRMACIÓN
        logger.info(f"🔍 Confirmando transacción con token: {token_ws}")
        
        # Buscar la transacción en nuestra base de datos
        search_sql = text("""
            SELECT numero_orden, token, monto, estado 
            FROM transacciones_webpay 
            WHERE token = :token
        """)
        
        transaccion_data = db.execute(search_sql, {'token': token_ws}).fetchone()
        
        if not transaccion_data:
            error_msg = "Token de transacción no encontrado en la base de datos"
            logger.error(f"❌ {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        # Confirmar transacción con WebPay
        result = transaction.commit(token_ws)
        logger.info(f"📋 Resultado WebPay: {json.dumps(result, indent=2)}")
        
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
        
        # Actualizar la transacción según el resultado
        if status == 'AUTHORIZED':
            # ✅ PAGO EXITOSO
            update_sql = text("""
                UPDATE transacciones_webpay 
                SET estado = 'completada',
                    authorization_code = :auth_code,
                    payment_type_code = :payment_type,
                    response_code = :response_code,
                    resultado_completo = :resultado,
                    updated_at = NOW()
                WHERE token = :token
            """)
            
            db.execute(update_sql, {
                'auth_code': authorization_code,
                'payment_type': payment_type_code,
                'response_code': response_code,
                'resultado': json.dumps(result),
                'token': token_ws
            })
            
            # Actualizar ventas
            for venta in ventas:
                venta.estado_pago = EstadoPago.PAGADA
                venta.estado_venta = EstadoVenta.NUEVA
            
            db.commit()
            logger.info(f"✅ Pago exitoso - Orden: {buy_order}, Autorización: {authorization_code}")
            
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
            # ❌ PAGO FALLIDO
            update_sql = text("""
                UPDATE transacciones_webpay 
                SET estado = 'fallida',
                    response_code = :response_code,
                    resultado_completo = :resultado,
                    updated_at = NOW()
                WHERE token = :token
            """)
            
            db.execute(update_sql, {
                'response_code': response_code,
                'resultado': json.dumps(result),
                'token': token_ws
            })
            
            # Actualizar ventas
            for venta in ventas:
                venta.estado_pago = EstadoPago.ANULADA
            
            db.commit()
            logger.warning(f"⚠️ Pago fallido - Orden: {buy_order}, Status: {status}")
            
            return templates.TemplateResponse("webpay_error.html", {
                "request": request,
                "buy_order": buy_order,
                "amount": amount,
                "response_code": response_code,
                "error_message": get_response_description(response_code)
            })
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error confirmando transacción: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        return templates.TemplateResponse("webpay_error.html", {
            "request": request,
            "error_message": f"Error procesando el resultado del pago: {str(e)}",
            "token": token_ws or TBK_TOKEN
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
        
        # Verificar si ya existe una transacción
        check_sql = text("""
            SELECT token, estado, monto, created_at 
            FROM transacciones_webpay 
            WHERE numero_orden = :orden 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        transaccion_data = db.execute(check_sql, {'orden': order_id}).fetchone()
        
        # Calcular total
        total = sum(venta.cantidad * venta.precio for venta in ventas)
        
        return templates.TemplateResponse("webpay_pago.html", {
            "request": request,
            "order_id": order_id,
            "total": int(total),
            "ventas": ventas,
            "transaccion_existente": transaccion_data
        })
        
    except Exception as e:
        logger.error(f"❌ Error en página de pago: {str(e)}")
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
        
        # Buscar transacción de WebPay con SQL directo
        search_sql = text("""
            SELECT token, estado, authorization_code, payment_type_code, 
                   monto, created_at, updated_at, response_code
            FROM transacciones_webpay 
            WHERE numero_orden = :orden 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        
        transaccion_data = db.execute(search_sql, {'orden': order_id}).fetchone()
        
        webpay_data = None
        if transaccion_data:
            webpay_data = {
                "token": transaccion_data.token,
                "estado": transaccion_data.estado,
                "authorization_code": transaccion_data.authorization_code,
                "payment_type": transaccion_data.payment_type_code,
                "payment_type_description": get_payment_type_description(transaccion_data.payment_type_code),
                "monto": transaccion_data.monto,
                "fecha_transaccion": transaccion_data.created_at,
                "fecha_actualizacion": transaccion_data.updated_at,
                "es_exitosa": transaccion_data.estado == 'completada' and transaccion_data.response_code == 0
            }
        
        return {
            "order_id": order_id,
            "estado_pago": venta.estado_pago,
            "estado_venta": venta.estado_venta,
            "total": sum(v.cantidad * v.precio for v in ventas),
            "cliente": venta.nombre_cliente,
            "webpay": webpay_data
        }
        
    except Exception as e:
        logger.error(f"❌ Error consultando estado: {str(e)}")
        raise HTTPException(status_code=500, detail="Error consultando estado del pago")

@router.get("/webpay/token/{token}")
async def consultar_por_token(
    token: str,
    db: Session = Depends(get_db)
):
    """Consultar transacción por token de WebPay"""
    try:
        # Buscar con SQL directo
        search_sql = text("""
            SELECT numero_orden, token, estado, monto, authorization_code, 
                   payment_type_code, created_at, updated_at, response_code, 
                   resultado_completo
            FROM transacciones_webpay 
            WHERE token = :token
        """)
        
        transaccion_data = db.execute(search_sql, {'token': token}).fetchone()
        
        if not transaccion_data:
            raise HTTPException(status_code=404, detail="Token no encontrado")
        
        # Buscar venta asociada
        ventas = db.query(Venta).filter(
            Venta.orden_compra == transaccion_data.numero_orden
        ).all()
        
        return {
            "token": token,
            "orden_compra": transaccion_data.numero_orden,
            "estado_transaccion": transaccion_data.estado,
            "monto": transaccion_data.monto,
            "authorization_code": transaccion_data.authorization_code,
            "payment_type": transaccion_data.payment_type_code,
            "payment_type_description": get_payment_type_description(transaccion_data.payment_type_code),
            "fecha_transaccion": transaccion_data.created_at,
            "fecha_actualizacion": transaccion_data.updated_at,
            "es_exitosa": transaccion_data.estado == 'completada' and transaccion_data.response_code == 0,
            "resultado_completo": json.loads(transaccion_data.resultado_completo) if transaccion_data.resultado_completo else None,
            # Datos de la venta
            "venta": {
                "cliente": ventas[0].nombre_cliente if ventas else None,
                "estado_pago": ventas[0].estado_pago if ventas else None,
                "estado_venta": ventas[0].estado_venta if ventas else None
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error consultando por token: {str(e)}")
        raise HTTPException(status_code=500, detail="Error consultando transacción")

@router.get("/webpay/transacciones")
async def listar_transacciones(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 50
):
    """Listar últimas transacciones"""
    try:
        # Consultar con SQL directo
        list_sql = text("""
            SELECT numero_orden, token, estado, monto, authorization_code, 
                   payment_type_code, created_at, updated_at
            FROM transacciones_webpay 
            ORDER BY created_at DESC 
            LIMIT :limit
        """)
        
        transacciones = db.execute(list_sql, {'limit': limit}).fetchall()
        
        # Estadísticas rápidas
        stats_sql = text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN estado = 'completada' THEN 1 ELSE 0 END) as exitosas,
                SUM(CASE WHEN estado = 'fallida' THEN 1 ELSE 0 END) as fallidas,
                SUM(CASE WHEN estado = 'iniciada' THEN 1 ELSE 0 END) as pendientes,
                SUM(CASE WHEN estado = 'completada' THEN monto ELSE 0 END) as monto_total
            FROM transacciones_webpay
        """)
        
        stats = db.execute(stats_sql).fetchone()
        
        return {
            "transacciones": [
                {
                    "numero_orden": t.numero_orden,
                    "token": t.token,
                    "estado": t.estado,
                    "monto": t.monto,
                    "authorization_code": t.authorization_code,
                    "payment_type_description": get_payment_type_description(t.payment_type_code),
                    "created_at": t.created_at,
                    "updated_at": t.updated_at
                }
                for t in transacciones
            ],
            "estadisticas": {
                "total": stats.total,
                "exitosas": stats.exitosas,
                "fallidas": stats.fallidas,
                "pendientes": stats.pendientes,
                "monto_total": stats.monto_total,
                "tasa_exito": (stats.exitosas / stats.total * 100) if stats.total > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error listando transacciones: {str(e)}")
        raise HTTPException(status_code=500, detail="Error consultando transacciones")

def get_payment_type_description(payment_type_code):
    """Obtener descripción del tipo de pago"""
    if not payment_type_code:
        return "N/A"
    
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