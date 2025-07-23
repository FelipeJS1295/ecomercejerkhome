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
# 🆕 IMPORTAR MODELOS DE TRANSBANK
from app.models.transbank import TransaccionWebpay, LogWebpay, TipoLog, EstadoTransaccion

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

def crear_log_webpay(db: Session, tipo: TipoLog, mensaje: str, numero_orden: str = None, 
                     token: str = None, datos_adicionales: dict = None, request: Request = None):
    """Función helper para crear logs"""
    ip_address = None
    user_agent = None
    
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    log = LogWebpay.crear_log(
        tipo=tipo,
        mensaje=mensaje,
        numero_orden=numero_orden,
        token=token,
        datos_adicionales=datos_adicionales,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(log)
    db.commit()
    return log

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
        transaccion_existente = db.query(TransaccionWebpay).filter(
            TransaccionWebpay.numero_orden == orden,
            TransaccionWebpay.estado.in_(["iniciada", "completada"])
        ).first()
        
        if transaccion_existente:
            if transaccion_existente.estado == "completada":
                raise HTTPException(status_code=400, detail="Esta orden ya fue pagada")
            else:
                # Si hay una transacción iniciada, la usamos
                logger.info(f"🔄 Reutilizando transacción existente: {transaccion_existente.token}")
                webpay_url = f"https://webpay3gint.transbank.cl/webpayserver/initTransaction?token_ws={transaccion_existente.token}"
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
            
            # Log del error
            crear_log_webpay(
                db, TipoLog.ERROR_INICIO, error_msg,
                numero_orden=orden, 
                datos_adicionales={"response": response},
                request=request
            )
            
            raise HTTPException(status_code=500, detail=error_msg)
        
        logger.info(f"✅ Respuesta WebPay: {response}")
        
        # 💾 CREAR REGISTRO EN TRANSACCIONES_WEBPAY
        nueva_transaccion = TransaccionWebpay(
            numero_orden=orden,
            token=response['token'],
            session_id=session_id,
            monto=monto,
            estado="iniciada"  # Usar string directamente
        )
        
        db.add(nueva_transaccion)
        
        # Actualizar estado de la venta
        venta.estado_pago = EstadoPago.PENDIENTE
        
        # Log de transacción iniciada
        crear_log_webpay(
            db, TipoLog.TRANSACCION_INICIADA, 
            f"Transacción iniciada correctamente",
            numero_orden=orden,
            token=response['token'],
            datos_adicionales={
                "monto": monto,
                "session_id": session_id,
                "return_url": return_url,
                "webpay_response": response
            },
            request=request
        )
        
        db.commit()
        
        webpay_url = f"{response['url']}?token_ws={response['token']}"
        logger.info(f"🔄 Redirigiendo a WebPay: {webpay_url}")
        logger.info(f"💾 Token guardado: {response['token']}")
        
        return RedirectResponse(url=webpay_url, status_code=303)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error iniciando transacción: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        # Log del error
        crear_log_webpay(
            db, TipoLog.ERROR_INICIO, error_msg,
            numero_orden=orden,
            datos_adicionales={"error": str(e)},
            request=request
        )
        
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
        
        logger.info(f"🔍 Confirmando transacción con token: {token_ws}")
        
        # Buscar la transacción en nuestra base de datos
        transaccion_webpay = db.query(TransaccionWebpay).filter(
            TransaccionWebpay.token == token_ws
        ).first()
        
        if not transaccion_webpay:
            error_msg = "Token de transacción no encontrado en la base de datos"
            logger.error(f"❌ {error_msg}")
            crear_log_webpay(
                db, TipoLog.ERROR_CONFIRMACION, error_msg,
                token=token_ws, request=request
            )
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
            # Actualizar manualmente en lugar de usar el método
            transaccion_webpay.estado = "completada"
            transaccion_webpay.authorization_code = authorization_code
            transaccion_webpay.payment_type_code = payment_type_code
            transaccion_webpay.response_code = response_code
            transaccion_webpay.resultado_completo = result
            transaccion_webpay.updated_at = datetime.now()
            
            # Actualizar ventas
            for venta in ventas:
                venta.estado_pago = EstadoPago.PAGADA
                venta.estado_venta = EstadoVenta.NUEVA
            
            # Log de éxito
            crear_log_webpay(
                db, TipoLog.TRANSACCION_CONFIRMADA,
                f"Pago confirmado exitosamente",
                numero_orden=buy_order,
                token=token_ws,
                datos_adicionales={
                    "authorization_code": authorization_code,
                    "amount": amount,
                    "payment_type": payment_type_code,
                    "webpay_result": result
                },
                request=request
            )
            
            db.commit()
            logger.info(f"✅ Pago exitoso - Orden: {buy_order}, Autorización: {authorization_code}")
            
            # Página de éxito
            return templates.TemplateResponse("webpay_exito.html", {
                "request": request,
                "buy_order": buy_order,
                "amount": amount,
                "authorization_code": authorization_code,
                "tipo_pago": transaccion_webpay.tipo_pago_descripcion,
                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ventas": ventas,
                "transaccion": transaccion_webpay
            })
        else:
            # ❌ PAGO FALLIDO
            # Actualizar manualmente en lugar de usar el método
            transaccion_webpay.estado = "fallida"
            transaccion_webpay.response_code = response_code
            transaccion_webpay.resultado_completo = result
            transaccion_webpay.updated_at = datetime.now()
            
            # Actualizar ventas
            for venta in ventas:
                venta.estado_pago = EstadoPago.ANULADA
            
            # Log de fallo
            crear_log_webpay(
                db, TipoLog.ERROR_CONFIRMACION,
                f"Pago fallido - Status: {status}, Response Code: {response_code}",
                numero_orden=buy_order,
                token=token_ws,
                datos_adicionales={"webpay_result": result},
                request=request
            )
            
            db.commit()
            logger.warning(f"⚠️ Pago fallido - Orden: {buy_order}, Status: {status}")
            
            return templates.TemplateResponse("webpay_error.html", {
                "request": request,
                "buy_order": buy_order,
                "amount": amount,
                "response_code": response_code,
                "error_message": get_response_description(response_code),
                "transaccion": transaccion_webpay
            })
        
    except Exception as e:
        error_msg = f"Error confirmando transacción: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        crear_log_webpay(
            db, TipoLog.ERROR_CONFIRMACION, error_msg,
            token=token_ws,
            datos_adicionales={"error": str(e)},
            request=request
        )
        
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
        
        # Verificar si ya existe una transacción
        transaccion = db.query(TransaccionWebpay).filter(
            TransaccionWebpay.numero_orden == order_id
        ).first()
        
        # Calcular total
        total = sum(venta.cantidad * venta.precio for venta in ventas)
        
        return templates.TemplateResponse("webpay_pago.html", {
            "request": request,
            "order_id": order_id,
            "total": int(total),
            "ventas": ventas,
            "transaccion_existente": transaccion
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
        
        # Buscar transacción de WebPay
        transaccion = db.query(TransaccionWebpay).filter(
            TransaccionWebpay.numero_orden == order_id
        ).first()
        
        return {
            "order_id": order_id,
            "estado_pago": venta.estado_pago,
            "estado_venta": venta.estado_venta,
            "total": sum(v.cantidad * v.precio for v in ventas),
            "cliente": venta.nombre_cliente,
            # 🆕 DATOS DE WEBPAY DESDE TABLA DEDICADA
            "webpay": {
                "token": transaccion.token if transaccion else None,
                "estado": transaccion.estado if transaccion else None,
                "authorization_code": transaccion.authorization_code if transaccion else None,
                "payment_type": transaccion.payment_type_code if transaccion else None,
                "payment_type_description": transaccion.tipo_pago_descripcion if transaccion else None,
                "monto": transaccion.monto if transaccion else None,
                "fecha_transaccion": transaccion.created_at if transaccion else None,
                "es_exitosa": transaccion.es_exitosa if transaccion else False
            }
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
        transaccion = db.query(TransaccionWebpay).filter(
            TransaccionWebpay.token == token
        ).first()
        
        if not transaccion:
            raise HTTPException(status_code=404, detail="Token no encontrado")
        
        # Buscar venta asociada
        ventas = db.query(Venta).filter(
            Venta.orden_compra == transaccion.numero_orden
        ).all()
        
        return {
            "token": token,
            "orden_compra": transaccion.numero_orden,
            "estado_transaccion": transaccion.estado,
            "monto": transaccion.monto,
            "authorization_code": transaccion.authorization_code,
            "payment_type": transaccion.payment_type_code,
            "payment_type_description": transaccion.tipo_pago_descripcion,
            "fecha_transaccion": transaccion.created_at,
            "fecha_actualizacion": transaccion.updated_at,
            "es_exitosa": transaccion.es_exitosa,
            "resultado_completo": transaccion.resultado_completo,
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

@router.get("/webpay/dashboard")
async def dashboard_webpay(
    request: Request,
    db: Session = Depends(get_db)
):
    """Dashboard con estadísticas de WebPay"""
    try:
        from sqlalchemy import func, desc
        from datetime import date, timedelta
        
        # Estadísticas generales
        total_transacciones = db.query(func.count(TransaccionWebpay.id)).scalar()
        transacciones_exitosas = db.query(func.count(TransaccionWebpay.id)).filter(
            TransaccionWebpay.estado == "completada"
        ).scalar()
        
        # Transacciones de hoy
        hoy = date.today()
        transacciones_hoy = db.query(TransaccionWebpay).filter(
            func.date(TransaccionWebpay.created_at) == hoy
        ).all()
        
        # Últimas 10 transacciones
        ultimas_transacciones = db.query(TransaccionWebpay).order_by(
            desc(TransaccionWebpay.created_at)
        ).limit(10).all()
        
        return templates.TemplateResponse("webpay_dashboard.html", {
            "request": request,
            "total_transacciones": total_transacciones,
            "transacciones_exitosas": transacciones_exitosas,
            "transacciones_hoy": len(transacciones_hoy),
            "ultimas_transacciones": ultimas_transacciones,
            "tasa_exito": (transacciones_exitosas / total_transacciones * 100) if total_transacciones > 0 else 0
        })
        
    except Exception as e:
        logger.error(f"❌ Error en dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Error cargando dashboard")

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