from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict
from app.database.database import get_db
from app.models import Usuario

async def get_current_user(request: Request) -> Optional[Dict]:
    """
    Obtiene el usuario actual desde la sesión
    Ajustar según tu sistema de autenticación existente
    """
    try:
        # Si usas sesiones con FastAPI
        if hasattr(request, 'session'):
            session = request.session
            if 'user_id' in session:
                return {
                    'id': session.get('user_id'),
                    'nombre': session.get('user_nombre', 'Usuario'),
                    'email': session.get('user_email'),
                    'es_admin': session.get('es_admin', False)
                }
        
        # Si usas cookies
        auth_cookie = request.cookies.get('auth_token')
        if auth_cookie:
            # Verificar cookie y obtener usuario
            # Implementar según tu lógica
            pass
        
        return None
        
    except Exception as e:
        print(f"Error obteniendo usuario actual: {e}")
        return None

async def require_auth(request: Request) -> Dict:
    """
    Requiere que el usuario esté autenticado
    """
    current_user = await get_current_user(request)
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesión para acceder a esta página"
        )
    return current_user

async def require_admin(request: Request) -> Dict:
    """
    Requiere que el usuario sea administrador
    """
    current_user = await require_auth(request)
    if not current_user.get('es_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador para acceder a esta página"
        )
    return current_user

# Función alternativa usando la base de datos directamente
async def get_user_by_session(request: Request, db: Session = Depends(get_db)) -> Optional[Usuario]:
    """
    Obtiene el usuario actual desde la base de datos
    """
    try:
        # Si tienes el user_id en la sesión
        if hasattr(request, 'session') and 'user_id' in request.session:
            user_id = request.session['user_id']
            return db.query(Usuario).filter(Usuario.id == user_id).first()
        
        return None
        
    except Exception as e:
        print(f"Error obteniendo usuario desde DB: {e}")
        return None

# Funciones de verificación de permisos
def check_admin_permissions(user: Dict) -> bool:
    """
    Verifica si el usuario tiene permisos de administrador
    """
    return user.get('es_admin', False) if user else False

def check_user_permissions(user: Dict, required_permission: str) -> bool:
    """
    Verifica si el usuario tiene un permiso específico
    """
    if not user:
        return False
    
    # Si es admin, tiene todos los permisos
    if user.get('es_admin', False):
        return True
    
    # Implementar lógica de permisos específicos según tu sistema
    user_permissions = user.get('permisos', [])
    return required_permission in user_permissions