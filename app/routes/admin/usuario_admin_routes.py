from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.usuario import Usuario, RolUsuario, EstadoUsuario
from app.middleware.auth_middleware import require_auth, require_admin
import bcrypt

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")

def hash_password(password: str) -> str:
    """Hashea una contraseña usando bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

@router.get("/usuarios")
async def admin_usuarios(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)  # Solo admins pueden gestionar usuarios
):
    try:
        usuarios = db.query(Usuario).all()
        
        stats = {
            "total_usuarios": len(usuarios),
            "usuarios_activos": len([u for u in usuarios if u.estado.value == 'ACTIVO']),
            "usuarios_admin": len([u for u in usuarios if u.rol.value == 'ADMIN'])
        }
        
        return templates.TemplateResponse("admin/usuarios.html", {
            "request": request,
            "usuarios": usuarios,
            "stats": stats,
            "rol_filter": None,
            "estado_filter": None,
            "buscar": "",
            "current_user": current_user
        })
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(url="/login", status_code=302)
        raise e

@router.get("/usuarios/nuevo")
async def nuevo_usuario_form(
    request: Request,
    current_user: Usuario = Depends(require_admin)
):
    try:
        return templates.TemplateResponse("admin/usuario_form.html", {
            "request": request,
            "usuario": None,
            "accion": "Crear",
            "current_user": current_user
        })
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(url="/login", status_code=302)
        raise e

@router.post("/usuarios/nuevo")
async def crear_usuario(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    email: str = Form(...),
    telefono: str = Form(""),
    username: str = Form(...),
    password: str = Form(...),
    rol: str = Form(...),
    estado: str = Form("ACTIVO"),
    cambiar_password: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    try:
        # Verificar que el email no exista
        existing_email = db.query(Usuario).filter(Usuario.email == email).first()
        if existing_email:
            return templates.TemplateResponse("admin/usuario_form.html", {
                "request": request,
                "usuario": None,
                "accion": "Crear",
                "error": "Ya existe un usuario con este email",
                "current_user": current_user
            })
        
        # Verificar que el username no exista
        existing_username = db.query(Usuario).filter(Usuario.username == username).first()
        if existing_username:
            return templates.TemplateResponse("admin/usuario_form.html", {
                "request": request,
                "usuario": None,
                "accion": "Crear",
                "error": "Ya existe un usuario con este nombre de usuario",
                "current_user": current_user
            })
        
        # Crear el usuario
        nuevo_usuario = Usuario(
            nombre=nombre,
            apellido=apellido,
            email=email,
            telefono=telefono if telefono else None,
            username=username,
            password_hash=hash_password(password),
            rol=RolUsuario(rol),
            estado=EstadoUsuario(estado),
            cambiar_password=cambiar_password
        )
        
        db.add(nuevo_usuario)
        db.commit()
        db.refresh(nuevo_usuario)
        
        return RedirectResponse(url="/admin/usuarios", status_code=status.HTTP_302_FOUND)
    
    except HTTPException as e:
        if e.status_code == 302:
            return RedirectResponse(url="/login", status_code=302)
        raise e