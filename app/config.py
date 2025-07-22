import os
import secrets
from datetime import timedelta
from typing import Optional

class SecurityConfig:
    """Configuración de seguridad centralizada"""
    
    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password Policy
    MIN_PASSWORD_LENGTH: int = 8
    REQUIRE_UPPERCASE: bool = True
    REQUIRE_LOWERCASE: bool = True
    REQUIRE_NUMBERS: bool = True
    REQUIRE_SPECIAL_CHARS: bool = True
    
    # Rate Limiting
    LOGIN_RATE_LIMIT: int = 5  # intentos por ventana
    LOGIN_RATE_WINDOW: int = 900  # 15 minutos en segundos
    LOCKOUT_DURATION: int = 3600  # 1 hora en segundos
    
    # Session Security
    SESSION_COOKIE_SECURE: bool = True  # Solo HTTPS
    SESSION_COOKIE_HTTPONLY: bool = True  # No accesible via JS
    SESSION_COOKIE_SAMESITE: str = "lax"
    
    # Security Headers
    SECURITY_HEADERS: dict = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data: https:; font-src 'self' https://cdnjs.cloudflare.com;",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
    
    @classmethod
    def validate_environment(cls) -> None:
        """Valida que las variables de entorno críticas estén configuradas"""
        if not os.getenv("SECRET_KEY"):
            print("⚠️  WARNING: SECRET_KEY no está configurada, usando una generada automáticamente")
            print(f"📝 Para producción, configura: SECRET_KEY={cls.SECRET_KEY}")
        
        if os.getenv("ENVIRONMENT") == "production":
            required_vars = ["SECRET_KEY", "DATABASE_URL"]
            missing = [var for var in required_vars if not os.getenv(var)]
            if missing:
                raise ValueError(f"Variables de entorno requeridas en producción: {missing}")

# Inicializar configuración
security_config = SecurityConfig()
security_config.validate_environment()