from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.usuario import Usuario, EstadoUsuario
from app.routes.auth_routes import verify_token
from typing import Optional
import jwt

def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[Usuario]:
    """Obtiene el usuario actual desde el token"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        return None
    
    token = access_token.replace("Bearer ", "")
    username = verify_token(token)
    if not username:
        return None
    
    usuario = db.query(Usuario).filter(Usuario.username == username).first()
    if not usuario or usuario.estado != EstadoUsuario.ACTIVO:
        return None
    
    return usuario

def require_auth(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Middleware que requiere autenticación"""
    usuario = get_current_user(request, db)
    if not usuario:
        # Si es una petición AJAX, devolver 401
        if request.headers.get("Content-Type") == "application/json" or request.headers.get("Accept") == "application/json":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No autenticado"
            )
        # Si es una petición normal, redirigir al login
        raise HTTPException(
            status_code=status.HTTP_302_FOUND,
            detail="Redirigir al login",
            headers={"Location": "/login"}
        )
    
    return usuario

def require_admin(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Middleware que requiere ser administrador"""
    usuario = require_auth(request, db)
    if not usuario.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes"
        )
    
    return usuario