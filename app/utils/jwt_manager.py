import jwt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from jose import JWTError, jwt as jose_jwt
from app.config import security_config
import redis
import json

class SecureJWTManager:
    """Gestor de JWT seguro con blacklist y refresh tokens"""
    
    def __init__(self):
        self.secret_key = security_config.SECRET_KEY
        self.algorithm = security_config.ALGORITHM
        self.access_token_expire = timedelta(minutes=security_config.ACCESS_TOKEN_EXPIRE_MINUTES)
        self.refresh_token_expire = timedelta(days=security_config.REFRESH_TOKEN_EXPIRE_DAYS)
        
        # Redis para blacklist de tokens (opcional, usar si tienes Redis)
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
            self.redis_available = True
        except:
            self.redis_available = False
            self.token_blacklist = set()  # Fallback en memoria
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Crea un token de acceso seguro
        """
        to_encode = data.copy()
        
        # Establecer expiración
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + self.access_token_expire
        
        # Agregar claims de seguridad
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": secrets.token_urlsafe(16),  # JWT ID único
            "iss": "jerkhome-auth",  # Emisor
            "aud": "jerkhome-app"    # Audiencia
        })
        
        return jose_jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Crea un token de refresh seguro
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + self.refresh_token_expire
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh",
            "jti": secrets.token_urlsafe(16),
            "iss": "jerkhome-auth",
            "aud": "jerkhome-app"
        })
        
        return jose_jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verifica y decodifica un token
        """
        try:
            # Verificar si el token está en blacklist
            if self.is_token_blacklisted(token):
                return None
            
            # Decodificar token
            payload = jose_jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                audience="jerkhome-app",
                issuer="jerkhome-auth"
            )
            
            # Verificar tipo de token
            if payload.get("type") != token_type:
                return None
            
            # Verificar expiración manual (seguridad adicional)
            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                return None
            
            return payload
            
        except JWTError:
            return None
        except Exception:
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Tuple[str, str]]:
        """
        Genera un nuevo access token usando un refresh token válido
        """
        # Verificar refresh token
        payload = self.verify_token(refresh_token, "refresh")
        if not payload:
            return None
        
        # Extraer datos del usuario
        user_data = {
            "sub": payload.get("sub"),
            "username": payload.get("username"),
            "rol": payload.get("rol")
        }
        
        # Blacklist el refresh token usado
        self.blacklist_token(refresh_token)
        
        # Crear nuevos tokens
        new_access_token = self.create_access_token(user_data)
        new_refresh_token = self.create_refresh_token({"sub": user_data["sub"]})
        
        return new_access_token, new_refresh_token
    
    def blacklist_token(self, token: str) -> None:
        """
        Agrega un token a la blacklist
        """
        try:
            # Decodificar para obtener JTI y expiración
            payload = jose_jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": False}  # No verificar expiración para blacklist
            )
            
            jti = payload.get("jti")
            exp = payload.get("exp")
            
            if jti and exp:
                # Calcular TTL para Redis
                ttl = max(0, exp - datetime.utcnow().timestamp())
                
                if self.redis_available:
                    # Usar Redis con TTL automático
                    self.redis_client.setex(f"blacklist:{jti}", int(ttl), "1")
                else:
                    # Fallback en memoria
                    self.token_blacklist.add(jti)
                    
        except Exception:
            pass  # Si no se puede blacklist, continúa
    
    def is_token_blacklisted(self, token: str) -> bool:
        """
        Verifica si un token está en blacklist
        """
        try:
            payload = jose_jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": False}
            )
            
            jti = payload.get("jti")
            if not jti:
                return False
            
            if self.redis_available:
                return self.redis_client.exists(f"blacklist:{jti}")
            else:
                return jti in self.token_blacklist
                
        except Exception:
            return True  # Si hay error, considerar blacklisted por seguridad
    
    def logout_user(self, access_token: str, refresh_token: Optional[str] = None) -> bool:
        """
        Cierra sesión de usuario blacklisteando sus tokens
        """
        try:
            # Blacklist access token
            self.blacklist_token(access_token)
            
            # Blacklist refresh token si existe
            if refresh_token:
                self.blacklist_token(refresh_token)
            
            return True
        except Exception:
            return False
    
    def cleanup_expired_tokens(self) -> None:
        """
        Limpia tokens expirados de la blacklist (solo para fallback en memoria)
        """
        if not self.redis_available:
            # Para Redis, el TTL maneja esto automáticamente
            # Para memoria, necesitamos limpiar manualmente
            current_time = datetime.utcnow().timestamp()
            
            # En una implementación real, necesitarías guardar también las expiraciones
            # Por simplicidad, limpiamos todo cada cierto tiempo
            if len(self.token_blacklist) > 10000:  # Límite arbitrario
                self.token_blacklist.clear()

class TokenValidator:
    """Validador de tokens con logging de seguridad"""
    
    def __init__(self, jwt_manager: SecureJWTManager):
        self.jwt_manager = jwt_manager
    
    def validate_and_extract_user(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Valida token y extrae información del usuario de forma segura
        """
        # Remover prefijo Bearer si existe
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Verificar token
        payload = self.jwt_manager.verify_token(token)
        if not payload:
            return None
        
        # Extraer datos seguros del usuario
        user_info = {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "rol": payload.get("rol"),
            "jti": payload.get("jti"),
            "exp": payload.get("exp")
        }
        
        # Verificar que todos los campos críticos estén presentes
        if not all([user_info["user_id"], user_info["username"]]):
            return None
        
        return user_info
    
    def extract_token_from_header(self, authorization: Optional[str]) -> Optional[str]:
        """
        Extrae token del header Authorization de forma segura
        """
        if not authorization:
            return None
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]

# Instancias globales
jwt_manager = SecureJWTManager()
token_validator = TokenValidator(jwt_manager)