from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.usuario import Usuario, EstadoUsuario
from app.utils.jwt_manager import jwt_manager, token_validator
from app.utils.rate_limiter import rate_limiter
from app.config import security_config
from typing import Optional
import logging
from datetime import datetime
import ipaddress

# Configurar logging de seguridad
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)

# Security bearer scheme
security = HTTPBearer(auto_error=False)

class SecurityMiddleware:
    """Middleware de seguridad avanzado"""
    
    def __init__(self):
        self.suspicious_patterns = [
            'union', 'select', 'drop', 'insert', 'update', 'delete',
            '<script', 'javascript:', 'onload=', 'onerror=',
            '../', '..\\', '/etc/passwd', '/windows/system32'
        ]
    
    def get_client_ip(self, request: Request) -> str:
        """Obtiene la IP real del cliente"""
        # Verificar headers de proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def is_suspicious_request(self, request: Request) -> bool:
        """Detecta patrones sospechosos en la request"""
        # Verificar URL
        url_path = str(request.url.path).lower()
        query_params = str(request.url.query).lower()
        
        # Buscar patrones maliciosos
        content_to_check = f"{url_path} {query_params}"
        
        for pattern in self.suspicious_patterns:
            if pattern in content_to_check:
                return True
        
        # Verificar headers sospechosos
        user_agent = request.headers.get("User-Agent", "").lower()
        if not user_agent or len(user_agent) < 10:
            return True
        
        # Verificar longitud excesiva
        if len(url_path) > 2048 or len(query_params) > 4096:
            return True
        
        return False
    
    def log_security_event(self, event_type: str, request: Request, 
                          user_id: Optional[int] = None, details: str = ""):
        """Registra eventos de seguridad"""
        client_ip = self.get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "Unknown")
        
        security_logger.warning(
            f"SECURITY_EVENT: {event_type} | "
            f"IP: {client_ip} | "
            f"USER_ID: {user_id} | "
            f"PATH: {request.url.path} | "
            f"USER_AGENT: {user_agent} | "
            f"DETAILS: {details}"
        )

security_middleware = SecurityMiddleware()

def get_current_user_secure(
    request: Request, 
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[Usuario]:
    """
    Obtiene el usuario actual de forma segura con validaciones adicionales
    """
    client_ip = security_middleware.get_client_ip(request)
    
    # Verificar rate limiting
    if rate_limiter.is_rate_limited(client_ip, "auth_check"):
        security_middleware.log_security_event(
            "RATE_LIMIT_EXCEEDED", request, details="Auth check rate limit"
        )
        return None
    
    # Verificar request sospechosa
    if security_middleware.is_suspicious_request(request):
        security_middleware.log_security_event(
            "SUSPICIOUS_REQUEST", request, details="Malicious patterns detected"
        )
        return None
    
    # Intentar obtener token de diferentes fuentes
    token = None
    
    # 1. Authorization header
    if credentials:
        token = credentials.credentials
    
    # 2. Cookie (fallback)
    if not token:
        token = request.cookies.get("access_token")
        if token and token.startswith("Bearer "):
            token = token[7:]
    
    if not token:
        return None
    
    try:
        # Validar token
        user_data = token_validator.validate_and_extract_user(token)
        if not user_data:
            security_middleware.log_security_event(
                "INVALID_TOKEN", request, details="Token validation failed"
            )
            return None
        
        # Obtener usuario de la base de datos
        usuario = db.query(Usuario).filter(
            Usuario.id == user_data["user_id"],
            Usuario.username == user_data["username"]
        ).first()
        
        if not usuario:
            security_middleware.log_security_event(
                "USER_NOT_FOUND", request, user_id=user_data["user_id"]
            )
            return None
        
        # Verificar estado del usuario
        if usuario.estado != EstadoUsuario.ACTIVO:
            security_middleware.log_security_event(
                "INACTIVE_USER_ACCESS", request, user_id=usuario.id,
                details=f"User status: {usuario.estado.value}"
            )
            return None
        
        # Verificar si está bloqueado
        if usuario.is_blocked:
            security_middleware.log_security_event(
                "BLOCKED_USER_ACCESS", request, user_id=usuario.id
            )
            return None
        
        # Actualizar último acceso (solo si ha pasado más de 5 minutos)
        now = datetime.now()
        if not usuario.ultimo_acceso or (now - usuario.ultimo_acceso).seconds > 300:
            usuario.ultimo_acceso = now
            db.commit()
        
        return usuario
        
    except Exception as e:
        security_middleware.log_security_event(
            "AUTH_EXCEPTION", request, details=str(e)
        )
        return None

def require_auth_secure(
    request: Request, 
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Middleware que requiere autenticación con seguridad mejorada
    """
    usuario = get_current_user_secure(request, credentials, db)
    
    if not usuario:
        client_ip = security_middleware.get_client_ip(request)
        
        # Incrementar contador de intentos fallidos
        rate_limiter.increment_attempts(client_ip, "failed_auth")
        
        # Verificar si es AJAX/API
        if (request.headers.get("Content-Type") == "application/json" or 
            request.headers.get("Accept") == "application/json" or
            "api" in request.url.path):
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticación inválido o expirado",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Para requests web, redirigir al login
        security_middleware.log_security_event(
            "UNAUTHORIZED_ACCESS", request, details="Redirecting to login"
        )
        
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Redirigir al login",
            headers={"Location": "/login"}
        )
    
    return usuario

def require_admin_secure(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Middleware que requiere privilegios de administrador
    """
    usuario = require_auth_secure(request, credentials, db)
    
    if not usuario.is_admin:
        security_middleware.log_security_event(
            "ADMIN_ACCESS_DENIED", request, user_id=usuario.id,
            details=f"User role: {usuario.rol.value}"
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos de administrador requeridos"
        )
    
    return usuario

def require_role_secure(allowed_roles: list):
    """
    Decorator para requerir roles específicos
    """
    def role_checker(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: Session = Depends(get_db)
    ) -> Usuario:
        usuario = require_auth_secure(request, credentials, db)
        
        if usuario.rol.value not in allowed_roles:
            security_middleware.log_security_event(
                "ROLE_ACCESS_DENIED", request, user_id=usuario.id,
                details=f"Required: {allowed_roles}, User: {usuario.rol.value}"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rol requerido: {', '.join(allowed_roles)}"
            )
        
        return usuario
    
    return role_checker

class SecurityHeadersMiddleware:
    """Middleware para agregar headers de seguridad"""
    
    async def __call__(self, request: Request, call_next):
        response = await call_next(request)
        
        # Agregar headers de seguridad
        for header, value in security_config.SECURITY_HEADERS.items():
            response.headers[header] = value
        
        # Header específico para admin panel
        if request.url.path.startswith("/admin"):
            response.headers["X-Admin-Panel"] = "true"
        
        return response

# Instancia del middleware de headers
security_headers_middleware = SecurityHeadersMiddleware()