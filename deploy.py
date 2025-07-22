#!/usr/bin/env python3
"""
Script de deployment para JerkHome
Configura el proyecto para producción
"""

import os
import sys
import subprocess
from pathlib import Path
import secrets
import string

def generate_secret_key():
    """Genera una clave secreta segura"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(50))

def create_production_env():
    """Crea archivo .env para producción"""
    print("🔐 Configurando variables de entorno para producción...")
    
    env_content = f"""# Configuración de Producción - JerkHome
DEBUG=False

# Base de datos - Actualiza con tus credenciales reales
DATABASE_URL=sqlite:///./jerkhome_production.db
# Para PostgreSQL: DATABASE_URL=postgresql://usuario:password@localhost/jerkhome

# JWT - Clave generada automáticamente
JWT_SECRET_KEY={generate_secret_key()}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60

# Servidor
HOST=0.0.0.0
PORT=8000

# Transbank Producción - ACTUALIZA CON TUS CREDENCIALES REALES
TRANSBANK_COMMERCE_CODE=tu_commerce_code_aqui
TRANSBANK_API_KEY=tu_api_key_aqui
TRANSBANK_ENVIRONMENT=production

# URLs - Actualiza con tu dominio real
SITE_URL=https://tudominio.com
RETURN_URL=https://tudominio.com/webpay/return

# Email (opcional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@tudominio.com

# Archivos
MAX_FILE_SIZE=5242880
ALLOWED_IMAGE_EXTENSIONS=jpg,jpeg,png,webp

# Logs
LOG_LEVEL=WARNING
LOG_FILE=jerkhome_production.log
"""
    
    env_file = Path('.env.production')
    env_file.write_text(env_content)
    
    print(f"✅ Archivo {env_file} creado")
    print("⚠️  IMPORTANTE: Actualiza las credenciales de Transbank y la URL del sitio")

def install_production_dependencies():
    """Instala dependencias adicionales para producción"""
    print("📦 Instalando dependencias de producción...")
    
    production_deps = [
        "gunicorn",  # Servidor WSGI
        "psycopg2-binary",  # PostgreSQL driver
        "redis",  # Para cache si se necesita
    ]
    
    try:
        for dep in production_deps:
            subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                          check=True, capture_output=True)
        
        # Actualizar requirements.txt
        subprocess.run([sys.executable, "-m", "pip", "freeze", ">", "requirements.txt"], 
                      shell=True, check=True)
        
        print("✅ Dependencias de producción instaladas")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error instalando dependencias: {e}")

def create_gunicorn_config():
    """Crea configuración para Gunicorn"""
    print("🚀 Creando configuración de Gunicorn...")
    
    gunicorn_config = """# Configuración Gunicorn para JerkHome
bind = "0.0.0.0:8000"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 10000
max_requests_jitter = 1000
preload_app = True
timeout = 120
keepalive = 2

# Logging
access_log = "logs/gunicorn_access.log"
error_log = "logs/gunicorn_error.log"
log_level = "info"

# Proceso
daemon = False
pidfile = "jerkhome.pid"
user = "www-data"  # Cambia por el usuario apropiado
group = "www-data"  # Cambia por el grupo apropiado

# Optimizaciones
worker_tmp_dir = "/dev/shm"
tmp_upload_dir = "/tmp"
"""
    
    config_file = Path('gunicorn.conf.py')
    config_file.write_text(gunicorn_config)
    
    print("✅ Configuración de Gunicorn creada")

def create_systemd_service():
    """Crea archivo de servicio systemd"""
    print("🔧 Creando servicio systemd...")
    
    current_dir = Path.cwd()
    venv_path = current_dir / "venv"
    
    service_content = f"""[Unit]
Description=JerkHome E-commerce Application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory={current_dir}
Environment=PATH={venv_path}/bin
ExecStart={venv_path}/bin/gunicorn app.main:app -c gunicorn.conf.py
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path('jerkhome.service')
    service_file.write_text(service_content)
    
    print(f"✅ Archivo de servicio creado: {service_file}")
    print("💡 Para instalar el servicio:")
    print(f"   sudo cp {service_file} /etc/systemd/system/")
    print("   sudo systemctl daemon-reload")
    print("   sudo systemctl enable jerkhome")
    print("   sudo systemctl start jerkhome")

def create_nginx_config():
    """Crea configuración básica de Nginx"""
    print("🌐 Creando configuración de Nginx...")
    
    nginx_config = """# Configuración Nginx para JerkHome
server {
    listen 80;
    server_name tudominio.com www.tudominio.com;
    
    # Redirigir HTTP a HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tudominio.com www.tudominio.com;
    
    # SSL Configuration (usa Let's Encrypt o tus certificados)
    ssl_certificate /path/to/your/certificate.crt;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Configuraciones de seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # Archivos estáticos
    location /static/ {
        alias /path/to/jerkhome/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Proxy a la aplicación
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # WebSocket support (si se necesita)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Límites de tamaño de archivo
    client_max_body_size 10M;
    
    # Logs
    access_log /var/log/nginx/jerkhome_access.log;
    error_log /var/log/nginx/jerkhome_error.log;
}
"""
    
    nginx_file = Path('jerkhome_nginx.conf')
    nginx_file.write_text(nginx_config)
    
    print(f"✅ Configuración de Nginx creada: {nginx_file}")
    print("💡 Para usar la configuración:")
    print(f"   sudo cp {nginx_file} /etc/nginx/sites-available/jerkhome")
    print("   sudo ln -s /etc/nginx/sites-available/jerkhome /etc/nginx/sites-enabled/")
    print("   sudo nginx -t && sudo systemctl reload nginx")

def create_backup_script():
    """Crea script de respaldo"""
    print("💾 Creando script de respaldo...")
    
    backup_script = """#!/bin/bash
# Script de respaldo para JerkHome

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/jerkhome"
PROJECT_DIR="/path/to/jerkhome"

# Crear directorio de respaldo
mkdir -p $BACKUP_DIR

# Respaldar base de datos
echo "Respaldando base de datos..."
cp $PROJECT_DIR/jerkhome_production.db $BACKUP_DIR/jerkhome_$DATE.db

# Respaldar imágenes
echo "Respaldando imágenes..."
tar -czf $BACKUP_DIR/images_$DATE.tar.gz -C $PROJECT_DIR/app/static images/

# Respaldar logs
echo "Respaldando logs..."
tar -czf $BACKUP_DIR/logs_$DATE.tar.gz -C $PROJECT_DIR logs/

# Limpiar respaldos antiguos (mantener últimos 7 días)
find $BACKUP_DIR -name "jerkhome_*.db" -mtime +7 -delete
find $BACKUP_DIR -name "images_*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "logs_*.tar.gz" -mtime +7 -delete

echo "Respaldo completado: $DATE"
"""
    
    backup_file = Path('backup.sh')
    backup_file.write_text(backup_script)
    backup_file.chmod(0o755)
    
    print(f"✅ Script de respaldo creado: {backup_file}")
    print("💡 Para automatizar respaldos diarios:")
    print("   crontab -e")
    print(f"   0 2 * * * {Path.cwd()}/backup.sh")

def check_system_requirements():
    """Verifica requisitos del sistema"""
    print("🔍 Verificando requisitos del sistema...")
    
    # Verificar Python
    python_version = sys.version_info
    if python_version < (3, 8):
        print("❌ Python 3.8+ requerido")
        return False
    
    print(f"✅ Python {python_version.major}.{python_version.minor}")
    
    # Verificar pip
    try:
        import pip
        print("✅ pip disponible")
    except ImportError:
        print("❌ pip no encontrado")
        return False
    
    return True

def main():
    """Función principal de deployment"""
    print("🚀 JerkHome - Configuración para Producción")
    print("=" * 50)
    
    if not check_system_requirements():
        sys.exit(1)
    
    # Verificar directorio del proyecto
    if not Path("app").exists():
        print("❌ Error: No se encuentra el directorio 'app'")
        print("Ejecuta este script desde la raíz del proyecto JerkHome")
        sys.exit(1)
    
    print("\n⚠️  Este script preparará JerkHome para producción.")
    print("Se crearán archivos de configuración y dependencias adicionales.")
    
    confirm = input("\n¿Continuar? (s/N): ").lower().strip()
    if confirm not in ['s', 'si', 'y', 'yes']:
        print("❌ Deployment cancelado")
        sys.exit(0)
    
    steps = [
        ("Crear directorio logs", lambda: Path("logs").mkdir(exist_ok=True)),
        ("Configuración de producción", create_production_env),
        ("Dependencias de producción", install_production_dependencies),  
        ("Configuración Gunicorn", create_gunicorn_config),
        ("Servicio systemd", create_systemd_service),
        ("Configuración Nginx", create_nginx_config),
        ("Script de respaldo", create_backup_script),
    ]
    
    success_count = 0
    
    for step_name, step_func in steps:
        try:
            print(f"\n🔄 {step_name}...")
            step_func()
            success_count += 1
        except Exception as e:
            print(f"❌ Error en {step_name}: {e}")
    
    # Resumen
    print("\n" + "=" * 50)
    print(f"✅ Deployment configurado: {success_count}/{len(steps)} pasos")
    
    if success_count == len(steps):
        print("\n🎉 ¡JerkHome está listo para producción!")
        print("\n📋 Lista de verificación final:")
        print("   1. ✅ Actualiza .env.production con credenciales reales")
        print("   2. ✅ Configura certificados SSL")
        print("   3. ✅ Instala y configura PostgreSQL (recomendado)")
        print("   4. ✅ Configura firewall (puertos 80, 443)")
        print("   5. ✅ Instala servicio systemd")
        print("   6. ✅ Configura Nginx")
        print("   7. ✅ Configura respaldos automáticos")
        
        print("\n🚀 Comandos de inicio rápido:")
        print("   # Usar configuración de producción")
        print("   cp .env.production .env")
        print("   # Inicializar base de datos")
        print("   python setup_project.py")
        print("   # Iniciar con Gunicorn")
        print("   gunicorn app.main:app -c gunicorn.conf.py")
        
    else:
        print("\n⚠️  Algunos pasos fallaron. Revisa los errores.")

if __name__ == "__main__":
    main()