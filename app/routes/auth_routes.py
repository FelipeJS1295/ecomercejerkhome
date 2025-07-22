from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.usuario import Usuario, EstadoUsuario
from datetime import datetime, timedelta
import bcrypt
import jwt
from typing import Optional

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Configuración JWT
SECRET_KEY = "jerkhome_secret_key_2024"  # En producción usar variable de entorno
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas

security = HTTPBearer()

def verify_password(password: str, hashed: str) -> bool:
    """Verifica una contraseña contra su hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except:
        return False

def create_access_token(data: dict):
    """Crea un token JWT"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Verifica y decodifica un token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except jwt.PyJWTError:
        return None

@router.get("/login")
async def login_form(request: Request):
    """Mostrar formulario de login"""
    return templates.TemplateResponse("auth/login.html", {
        "request": request
    })

@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Procesar login"""
    
    # Buscar usuario por username o email
    usuario = db.query(Usuario).filter(
        (Usuario.username == username) | (Usuario.email == username)
    ).first()
    
    # Verificar si el usuario existe
    if not usuario:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Usuario o contraseña incorrectos"
        })
    
    # Verificar si el usuario está activo
    if usuario.estado != EstadoUsuario.ACTIVO:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Usuario inactivo o suspendido"
        })
    
    # Verificar si el usuario está bloqueado
    if usuario.is_blocked:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": f"Usuario bloqueado. Intente más tarde."
        })
    
    # Verificar contraseña
    if not verify_password(password, usuario.password_hash):
        # Incrementar intentos fallidos
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos >= 5:
            usuario.bloqueado_hasta = datetime.now() + timedelta(minutes=30)
        db.commit()
        
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Usuario o contraseña incorrectos"
        })
    
    # Login exitoso
    # Resetear intentos fallidos
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = datetime.now()
    db.commit()
    
    # Crear token
    access_token = create_access_token(data={"sub": usuario.username})
    
    # Crear respuesta con redirección
    if usuario.cambiar_password:
        response = RedirectResponse(url="/cambiar-password", status_code=status.HTTP_302_FOUND)
    else:
        response = RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
    
    # Establecer cookie con el token
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False  # En producción cambiar a True con HTTPS
    )
    
    return response

@router.get("/logout")
async def logout(request: Request):
    """Cerrar sesión"""
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response

@router.get("/cambiar-password")
async def cambiar_password_form(request: Request):
    """Formulario para cambiar contraseña"""
    return templates.TemplateResponse("auth/cambiar_password.html", {
        "request": request
    })

@router.post("/cambiar-password")
async def cambiar_password(
    request: Request,
    password_actual: str = Form(...),
    password_nueva: str = Form(...),
    password_confirmar: str = Form(...),
    db: Session = Depends(get_db)
):
    """Procesar cambio de contraseña"""
    
    # Obtener usuario del token
    access_token = request.cookies.get("access_token")
    if not access_token:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    token = access_token.replace("Bearer ", "")
    username = verify_token(token)
    if not username:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    usuario = db.query(Usuario).filter(Usuario.username == username).first()
    if not usuario:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # Verificar contraseña actual
    if not verify_password(password_actual, usuario.password_hash):
        return templates.TemplateResponse("auth/cambiar_password.html", {
            "request": request,
            "error": "La contraseña actual es incorrecta"
        })
    
    # Verificar que las contraseñas nuevas coincidan
    if password_nueva != password_confirmar:
        return templates.TemplateResponse("auth/cambiar_password.html", {
            "request": request,
            "error": "Las contraseñas nuevas no coinciden"
        })
    
    # Verificar longitud mínima
    if len(password_nueva) < 6:
        return templates.TemplateResponse("auth/cambiar_password.html", {
            "request": request,
            "error": "La contraseña debe tener al menos 6 caracteres"
        })
    
    # Actualizar contraseña
    usuario.password_hash = bcrypt.hashpw(password_nueva.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    usuario.cambiar_password = False
    db.commit()
    
    # Redirigir al admin
    return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)

# Función para obtener usuario actual (helper)
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
    return usuario