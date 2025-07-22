#!/usr/bin/env python3
"""
Script para ejecutar JerkHome en modo desarrollo
"""

import uvicorn
import os
from pathlib import Path

def main():
    """Ejecuta el servidor en modo desarrollo"""
    
    # Verificar que existe el archivo .env
    env_file = Path('.env')
    if not env_file.exists():
        print("⚠️  Archivo .env no encontrado!")
        print("Copia .env.example a .env y configura las variables necesarias")
        return
    
    # Verificar que existe la carpeta de la aplicación
    app_dir = Path('app')
    if not app_dir.exists():
        print("❌ Directorio 'app' no encontrado!")
        print("Asegúrate de ejecutar este script desde la raíz del proyecto")
        return
    
    print("🚀 Iniciando JerkHome en modo desarrollo...")
    print("🌐 La aplicación estará disponible en: http://localhost:8000")
    print("🔧 Panel de administración en: http://localhost:8000/login")
    print("📚 Documentación API en: http://localhost:8000/docs")
    print("⏹️  Presiona Ctrl+C para detener el servidor")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            reload_dirs=["app"],
            reload_includes=["*.py", "*.html", "*.css", "*.js"],
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido. ¡Hasta luego!")
    except Exception as e:
        print(f"❌ Error al iniciar el servidor: {e}")

if __name__ == "__main__":
    main()