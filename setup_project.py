#!/usr/bin/env python3
"""
Script de configuración inicial para JerkHome
Crea la base de datos y el usuario administrador inicial
"""

import os
import sys
from pathlib import Path

def create_database():
    """Crea las tablas de la base de datos"""
    try:
        from app.database.database import engine, Base
        from app.models import *
        
        print("📊 Creando tablas de la base de datos...")
        
        # Importar todos los modelos para que se creen las tablas
        from app.models.categoria import Categoria
        from app.models.producto import Producto  
        from app.models.configuracion import Configuracion
        from app.models.ventas import Venta
        from app.models.transbank import TransaccionWebpay, LogWebpay, ConfiguracionWebpay, EstadisticaWebpay
        from app.models.usuario import Usuario
        
        # Crear todas las tablas
        Base.metadata.create_all(bind=engine)
        print("✅ Base de datos creada correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear la base de datos: {e}")
        return False

def create_admin_user():
    """Crea el usuario administrador inicial"""
    try:
        from app.database.database import get_db
        from app.models.usuario import Usuario, RolUsuario, EstadoUsuario
        import bcrypt
        
        print("👤 Creando usuario administrador...")
        
        db = next(get_db())
        
        # Verificar si ya existe un admin
        existing_admin = db.query(Usuario).filter(Usuario.username == 'admin').first()
        if existing_admin:
            print("⚠️  El usuario 'admin' ya existe")
            return True
        
        # Crear hash de la contraseña
        import bcrypt
        password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Crear usuario admin
        admin = Usuario(
            nombre='Administrador',
            apellido='Sistema',
            email='admin@jerkhome.cl',
            username='admin',
            password_hash=password_hash,
            rol=RolUsuario.ADMIN,
            estado=EstadoUsuario.ACTIVO,
            cambiar_password=False  # Para que no pida cambio en el primer login
        )
        
        db.add(admin)
        db.commit()
        
        print("✅ Usuario administrador creado:")
        print("   👤 Usuario: admin")
        print("   🔑 Contraseña: admin123")
        print("   📧 Email: admin@jerkhome.cl")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear usuario administrador: {e}")
        return False

def create_sample_configurations():
    """Crea configuraciones básicas del sitio"""
    try:
        from app.database.database import get_db
        from app.models.configuracion import Configuracion
        
        print("⚙️  Creando configuraciones básicas...")
        
        db = next(get_db())
        
        # Configuraciones básicas
        configs = [
            # Información general
            Configuracion(
                clave="site_name",
                valor="JerkHome",
                tipo="texto",
                categoria="general",
                descripcion="Nombre del sitio web"
            ),
            Configuracion(
                clave="site_description", 
                valor="Fábrica de Muebles Tapizados de Alta Calidad",
                tipo="texto",
                categoria="general",
                descripcion="Descripción del sitio web"
            ),
            Configuracion(
                clave="site_keywords",
                valor="muebles, tapizados, sofás, seccionales, poltronas, Chile",
                tipo="texto",
                categoria="seo",
                descripcion="Palabras clave SEO"
            ),
            
            # Información de contacto
            Configuracion(
                clave="contact_phone",
                valor="+56 9 1234 5678",
                tipo="telefono",
                categoria="contacto",
                descripcion="Teléfono principal"
            ),
            Configuracion(
                clave="contact_email",
                valor="contacto@jerkhome.cl",
                tipo="email", 
                categoria="contacto",
                descripcion="Email de contacto"
            ),
            Configuracion(
                clave="contact_address",
                valor="Av. Siempre Viva 123, Santiago, Chile",
                tipo="texto",
                categoria="contacto", 
                descripcion="Dirección física"
            ),
            
            # Redes sociales
            Configuracion(
                clave="social_facebook",
                valor="https://facebook.com/jerkhome",
                tipo="url",
                categoria="redes_sociales",
                descripcion="URL de Facebook"
            ),
            Configuracion(
                clave="social_instagram", 
                valor="https://instagram.com/jerkhome",
                tipo="url",
                categoria="redes_sociales",
                descripcion="URL de Instagram"
            ),
            Configuracion(
                clave="social_whatsapp",
                valor="+56912345678",
                tipo="telefono", 
                categoria="redes_sociales",
                descripcion="WhatsApp Business"
            )
        ]
        
        # Verificar si ya existen configuraciones
        existing_count = db.query(Configuracion).count()
        if existing_count > 0:
            print(f"⚠️  Ya existen {existing_count} configuraciones")
            return True
        
        # Agregar configuraciones
        for config in configs:
            db.add(config)
        
        db.commit()
        print(f"✅ {len(configs)} configuraciones básicas creadas")
        return True
        
    except Exception as e:
        print(f"❌ Error al crear configuraciones: {e}")
        return False

def create_directories():
    """Crea los directorios necesarios para el proyecto"""
    dirs = [
        "app/static/images/productos",
        "app/static/images/categorias", 
        "app/static/images/config",
        "logs"
    ]
    
    print("📁 Creando directorios necesarios...")
    
    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        # Crear archivo .gitkeep para mantener directorios vacíos en git
        gitkeep_file = Path(dir_path) / '.gitkeep'
        if not gitkeep_file.exists():
            gitkeep_file.touch()
    
    print("✅ Directorios creados correctamente")

def main():
    """Función principal de configuración"""
    
    print("🛋️  JerkHome - Configuración Inicial")
    print("=" * 50)
    
    # Verificar que estamos en el directorio correcto
    if not Path("app").exists():
        print("❌ Error: No se encuentra el directorio 'app'")
        print("Ejecuta este script desde la raíz del proyecto JerkHome")
        sys.exit(1)
    
    # Verificar archivo .env
    if not Path(".env").exists():
        print("⚠️  Archivo .env no encontrado")
        if Path(".env.example").exists():
            print("💡 Copia .env.example a .env y configúralo antes de continuar")
        else:
            print("💡 Crea un archivo .env con las variables de configuración")
        
        create_env = input("¿Quieres crear un .env básico ahora? (s/N): ").lower().strip()
        if create_env in ['s', 'si', 'y', 'yes']:
            try:
                import shutil
                shutil.copy('.env.example', '.env')
                print("✅ Archivo .env creado desde .env.example")
                print("🔧 Edita .env y configura las variables necesarias")
            except Exception as e:
                print(f"❌ Error al crear .env: {e}")
                sys.exit(1)
        else:
            print("❌ Configuración cancelada")
            sys.exit(1)
    
    success_count = 0
    total_steps = 4
    
    # Crear directorios
    create_directories()
    success_count += 1
    
    # Crear base de datos
    if create_database():
        success_count += 1
    
    # Crear usuario admin
    if create_admin_user():
        success_count += 1
    
    # Crear configuraciones
    if create_sample_configurations():
        success_count += 1
    
    # Resumen
    print("\n" + "=" * 50)
    print(f"✅ Configuración completada: {success_count}/{total_steps} pasos exitosos")
    
    if success_count == total_steps:
        print("\n🎉 ¡JerkHome está listo para usar!")
        print("\n📖 Próximos pasos:")
        print("   1. Ejecuta: python run_dev.py")
        print("   2. Abre: http://localhost:8000")
        print("   3. Panel admin: http://localhost:8000/login")
        print("      Usuario: admin / Contraseña: admin123")
    else:
        print("\n⚠️  Algunos pasos fallaron. Revisa los errores anteriores.")

if __name__ == "__main__":
    main()