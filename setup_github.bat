@echo off
echo 🛋️ JerkHome - Configuración y subida a GitHub
echo ================================================

REM Crear requirements.txt con las dependencias actuales
echo 📦 Generando requirements.txt...
pip freeze > requirements.txt

REM Crear archivo .env para desarrollo local (si no existe)
if not exist .env (
    echo 🔧 Creando archivo .env desde .env.example...
    copy .env.example .env
    echo ⚠️  Edita el archivo .env con tus configuraciones antes de continuar
    pause
)

REM Crear directorios necesarios
echo 📁 Creando directorios necesarios...
if not exist "app\static\images\productos" mkdir "app\static\images\productos"
if not exist "app\static\images\categorias" mkdir "app\static\images\categorias"
if not exist "app\static\images\config" mkdir "app\static\images\config"
if not exist "logs" mkdir "logs"

REM Crear archivos .gitkeep
echo. > app\static\images\productos\.gitkeep
echo. > app\static\images\categorias\.gitkeep
echo. > app\static\images\config\.gitkeep
echo. > logs\.gitkeep

REM Inicializar Git si no está inicializado
if not exist .git (
    echo 🔄 Inicializando repositorio Git...
    git init
)

REM Agregar remote si no existe
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo 🔗 Agregando remote de GitHub...
    git remote add origin https://github.com/FelipeJS1295/ecomercejerkhome.git
)

REM Verificar estado de Git
echo 📋 Verificando archivos a subir...
git status

echo.
echo ✅ Todo listo para subir a GitHub
echo.
echo Ejecuta los siguientes comandos:
echo   git add .
echo   git commit -m "Initial commit: Complete JerkHome e-commerce system"
echo   git push -u origin main
echo.
pause