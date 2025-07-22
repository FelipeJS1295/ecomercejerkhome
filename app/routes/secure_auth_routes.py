from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.usuario import Usuario, EstadoUsuario, RolUsuario
from app.utils.password_manager import password_manager
from app.utils.jwt_manager import jwt_manager
from app.utils.rate_limiter import rate_limiter
from app.middleware.secure_auth_middleware import (
    security_middleware, get_current_user_secure, require_auth_secure
)
from datetime import datetime, timedelta
from typing import Optional
import logging
import secrets
import re

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
security = HTTPBearer(auto_error=False)

# Logger de seguridad
auth_logger = logging.getLogger("auth")

class LoginAttemptTracker:
    """Rastrea intentos de login para detectar patrones sospechosos"""
    
    def __init__(self):
        self.failed_attempts = {}
        self.suspicious_ips = set()
    
    def record_failed_attempt(self, ip: str, username: str, reason: str):
        """Registra un intento fallido"""
        auth_logger.warning(
            f"LOGIN_FAILED: IP={ip} | USERNAME={username} | REASON={reason}"
        )
        
        # Marcar IP como sospechosa si hay muchos fallos
        if rate_limiter.get_stats(ip).get("failed_auth", {}).get("current", 0) > 5:
            self.suspicious_ips.add(ip)
    
    def is_ip_suspicious(self, ip: str) -> bool:
        """Verifica si una IP es sospechosa"""
        return ip in self.suspicious_ips or rate_limiter.is_ip_suspicious(ip)

login_tracker = LoginAttemptTracker()

def validate_login_input(username: str, password: str) -> tuple[bool, str]:
    """Valida los datos de entrada del login"""
    
    # Verificar longitud básica
    if not username or len(username.strip()) < 3:
        return False, "Nombre de usuario inválido"
    
    if not password or len(password) < 6:
        return False, "Contraseña muy corta"
    
    # Verificar caracteres permitidos en username
    if not re.match(r'^[a-zA-Z0-9@._-]+$', username):
        return False, "Caracteres no permitidos en el nombre de usuario"
    
    # Verificar longitud máxima (prevenir DoS)
    if len(username) > 100 or len(password) > 128:
        return False, "Datos de entrada muy largos"
    
    return True, ""

@router.get("/login")
async def login_page(request: Request):
    """Página de login con protecciones de seguridad"""
    
    client_ip = security_middleware.get_client_ip(request)
    
    # Verificar si la IP está bloqueada por rate limiting
    if rate_limiter.is_rate_limited(client_ip, "login_attempts"):
        remaining_time = rate_limiter.get_remaining_time(client_ip, "login_attempts")
        
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": f"Demasiados intentos fallidos. Intente nuevamente en {remaining_time//60} minutos.",
            "blocked": True
        })
    
    # Verificar si ya está autenticado
    current_user = get_current_user_secure(request, None, next(get_db()))
    if current_user:
        return RedirectResponse(url="/admin", status_code=302)
    
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "error": None,
        "blocked": False
    })

@router.post("/login")
async def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    """Autenticación segura de usuarios"""
    
    client_ip = security_middleware.get_client_ip(request)
    
    # Rate limiting estricto para intentos de login
    is_limited, current_attempts, remaining = rate_limiter.increment_attempts(
        client_ip, "login_attempts"
    )
    
    if is_limited:
        login_tracker.record_failed_attempt(
            client_ip, username, "RATE_LIMITED"
        )
        
        remaining_time = rate_limiter.get_remaining_time(client_ip, "login_attempts")
        
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": f"Demasiados intentos. Espere {remaining_time//60} minutos.",
            "blocked": True
        })
    
    # Validar entrada
    is_valid, error_msg = validate_login_input(username, password)
    if not is_valid:
        login_tracker.record_failed_attempt(client_ip, username, f"INVALID_INPUT: {error_msg}")
        
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Datos de acceso inválidos",
            "blocked": False
        })
    
    # Detectar patrones sospechosos
    if security_middleware.is_suspicious_request(request):
        login_tracker.record_failed_attempt(
            client_ip, username, "SUSPICIOUS_PATTERNS"
        )
        
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Acceso denegado",
            "blocked": True
        })
    
    try:
        # Buscar usuario (username o email)
        usuario = db.query(Usuario).filter(
            (Usuario.username == username) | (Usuario.email == username)
        ).first()
        
        # Verificar existencia del usuario
        if not usuario:
            login_tracker.record_failed_attempt(
                client_ip, username, "USER_NOT_FOUND"
            )
            
            # Agregar delay artificial para prevenir enumeración de usuarios
            import time
            time.sleep(1)
            
            return templates.TemplateResponse("auth/login.html", {
                "request": request,
                "error": "Credenciales incorrectas",
                "blocked": False
            })
        
        # Verificar estado del usuario
        if usuario.estado != EstadoUsuario.ACTIVO:
            login_tracker.record_failed_attempt(
                client_ip, username, f"USER_INACTIVE: {usuario.estado.value}"
            )
            
            return templates.TemplateResponse("auth/login.html", {
                "request": request,
                "error": "Cuenta inactiva. Contacte al administrador.",
                "blocked": True
            })
        
        # Verificar bloqueo temporal
        if usuario.is_blocked:
            login_tracker.record_failed_attempt(
                client_ip, username, "USER_BLOCKED"
            )
            
            return templates.TemplateResponse("auth/login.html", {
                "request": request,
                "error": "Cuenta temporalmente bloqueada",
                "blocked": True
            })
        
        # Verificar contraseña
        if not password_manager.verify_password(password, usuario.password_hash):
            # Incrementar intentos fallidos del usuario
            usuario.intentos_fallidos += 1
            
            # Bloquear usuario después de 5 intentos fallidos
            if usuario.intentos_fallidos >= 5:
                usuario.bloqueado_hasta = datetime.now() + timedelta(hours=1)
                auth_logger.warning(
                    f"USER_BLOCKED_AUTO: {usuario.username} after {usuario.intentos_fallidos} failed attempts"
                )
            
            db.commit()
            
            login_tracker.record_failed_attempt(
                client_ip, username, f"WRONG_PASSWORD (attempt {usuario.intentos_fallidos})"
            )
            
            return templates.TemplateResponse("auth/login.html", {
                "request": request,
                "error": "Credenciales incorrectas",
                "blocked": False
            })
        
        # LOGIN EXITOSO
        
        # Resetear intentos fallidos
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        usuario.ultimo_acceso = datetime.now()
        db.commit()
        
        # Resetear rate limiting para IP exitosa
        rate_limiter.reset_counter(client_ip, "login_attempts")
        
        # Crear tokens JWT
        user_data = {
            "sub": str(usuario.id),
            "username": usuario.username,
            "rol": usuario.rol.value,
            "nombre": usuario.nombre_completo
        }
        
        # Determinar duración del token
        if remember:
            access_token_expires = timedelta(days=7)
        else:
            access_token_expires = timedelta(minutes=30)
        
        access_token = jwt_manager.create_access_token(
            data=user_data, 
            expires_delta=access_token_expires
        )
        refresh_token = jwt_manager.create_refresh_token({"sub": str(usuario.id)})
        
        # Log del acceso exitoso
        auth_logger.info(
            f"LOGIN_SUCCESS: USER={usuario.username} | "
            f"IP={client_ip} | "
            f"ROLE={usuario.rol.value} | "
            f"REMEMBER={remember}"
        )
        
        # Verificar si necesita cambiar contraseña
        if usuario.cambiar_password:
            # Crear token temporal para cambio de contraseña
            temp_token = jwt_manager.create_access_token(
                data={**user_data, "temp": True, "action": "change_password"},
                expires_delta=timedelta(minutes=15)
            )
            
            response = RedirectResponse(url="/cambiar-password", status_code=302)
            response.set_cookie(
                key="temp_token",
                value=f"Bearer {temp_token}",
                max_age=900,  # 15 minutos
                httponly=True,
                secure=True,
                samesite="lax"
            )
            return response
        
        # Redirigir según el rol
        if usuario.is_admin:
            redirect_url = "/admin"
        else:
            redirect_url = "/admin"  # Todos van al admin por ahora
        
        response = RedirectResponse(url=redirect_url, status_code=302)
        
        # Configurar cookies seguras
        max_age = 604800 if remember else 1800  # 7 días o 30 min
        
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            max_age=max_age,
            httponly=True,
            secure=True,  # Solo HTTPS
            samesite="lax"
        )
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=604800,  # 7 días
            httponly=True,
            secure=True,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        auth_logger.error(f"LOGIN_ERROR: {str(e)} | IP={client_ip} | USERNAME={username}")
        
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Error interno del servidor",
            "blocked": False
        })

@router.get("/logout")
async def logout_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """Cierre de sesión seguro"""
    
    client_ip = security_middleware.get_client_ip(request)
    
    # Obtener tokens
    access_token = None
    refresh_token = None
    
    if credentials:
        access_token = credentials.credentials
    
    # También intentar desde cookies
    if not access_token:
        cookie_token = request.cookies.get("access_token")
        if cookie_token and cookie_token.startswith("Bearer "):
            access_token = cookie_token[7:]
    
    refresh_token = request.cookies.get("refresh_token")
    
    # Blacklist tokens si existen
    if access_token:
        jwt_manager.logout_user(access_token, refresh_token)
    
    # Log del logout
    user_data = None
    if access_token:
        from app.utils.jwt_manager import token_validator
        user_data = token_validator.validate_and_extract_user(access_token)
    
    auth_logger.info(
        f"LOGOUT: USER={user_data.get('username', 'unknown') if user_data else 'unknown'} | "
        f"IP={client_ip}"
    )
    
    # Redirigir al login
    response = RedirectResponse(url="/login", status_code=302)
    
    # Limpiar cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    response.delete_cookie("temp_token")
    
    return response

@router.get("/cambiar-password")
async def change_password_page(request: Request):
    """Página para cambio obligatorio de contraseña"""
    
    # Verificar token temporal
    temp_token = request.cookies.get("temp_token")
    if not temp_token:
        return RedirectResponse(url="/login", status_code=302)
    
    if temp_token.startswith("Bearer "):
        temp_token = temp_token[7:]
    
    # Validar token temporal
    from app.utils.jwt_manager import token_validator
    user_data = token_validator.validate_and_extract_user(temp_token)
    
    if not user_data or not user_data.get("temp") or user_data.get("action") != "change_password":
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("auth/cambiar_password.html", {
        "request": request,
        "error": None
    })

@router.post("/cambiar-password")
async def change_password_submit(
    request: Request,
    password_actual: str = Form(...),
    password_nueva: str = Form(...),
    password_confirmar: str = Form(...),
    db: Session = Depends(get_db)
):
    """Procesa el cambio de contraseña"""
    
    client_ip = security_middleware.get_client_ip(request)
    
    # Rate limiting para cambios de contraseña
    if rate_limiter.is_rate_limited(client_ip, "password_changes"):
        return templates.TemplateResponse("auth/cambiar_password.html", {
            "request": request,
            "error": "Demasiados intentos de cambio de contraseña"
        })
    
    # Verificar token temporal
    temp_token = request.cookies.get("temp_token")
    if not temp_token or not temp_token.startswith("Bearer "):
        return RedirectResponse(url="/login", status_code=302)
    
    temp_token = temp_token[7:]
    from app.utils.jwt_manager import token_validator
    user_data = token_validator.validate_and_extract_user(temp_token)
    
    if not user_data or not user_data.get("temp"):
        return RedirectResponse(url="/login", status_code=302)
    
    # Obtener usuario
    usuario = db.query(Usuario).filter(Usuario.id == int(user_data["sub"])).first()
    if not usuario:
        return RedirectResponse(url="/login", status_code=302)
    
    # Validaciones
    if password_nueva != password_confirmar:
        rate_limiter.increment_attempts(client_ip, "password_changes")
        return templates.TemplateResponse("auth/cambiar_password.html", {
            "request": request,
            "error": "Las contraseñas nuevas no coinciden"
        })
    
    # Verificar contraseña actual
    if not password_manager.verify_password(password_actual, usuario.password_hash):
        rate_limiter.increment_attempts(client_ip, "password_changes")
        return templates.TemplateResponse("auth/cambiar_password.html", {
            "request": request,
            "error": "Contraseña actual incorrecta"
        })
    
    # Validar fortaleza de la nueva contraseña
    try:
        new_password_hash = password_manager.hash_password(password_nueva)
    except ValueError as e:
        rate_limiter.increment_attempts(client_ip, "password_changes")
        return templates.TemplateResponse("auth/cambiar_password.html", {
            "request": request,
            "error": str(e)
        })
    
    # Actualizar contraseña
    usuario.password_hash = new_password_hash
    usuario.cambiar_password = False
    usuario.updated_at = datetime.now()
    db.commit()
    
    # Log del cambio
    auth_logger.info(f"PASSWORD_CHANGED: USER={usuario.username} | IP={client_ip}")
    
    # Invalidar token temporal y redirigir al login
    response = RedirectResponse(url="/login?mensaje=password_changed", status_code=302)
    response.delete_cookie("temp_token")
    
    return response

@router.post("/api/refresh-token")
async def refresh_token_endpoint(
    request: Request,
    db: Session = Depends(get_db)
):
    """Endpoint para renovar token de acceso"""
    
    client_ip = security_middleware.get_client_ip(request)
    
    # Rate limiting
    if rate_limiter.is_rate_limited(client_ip, "api_requests"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes"
        )
    
    # Obtener refresh token
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token no encontrado"
        )
    
    # Renovar tokens
    result = jwt_manager.refresh_access_token(refresh_token)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido"
        )
    
    new_access_token, new_refresh_token = result
    
    return JSONResponse(content={
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    })

# Endpoint de verificación de salud
@router.get("/auth/health")
async def auth_health_check():
    """Verificación de salud del sistema de autenticación"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "rate_limiter": "redis" if rate_limiter.redis_available else "memory",
        "jwt_manager": "active"
    }