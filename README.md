# 🛋️ JerkHome - E-commerce de Muebles Tapizados

Sistema completo de e-commerce desarrollado en FastAPI para la venta de muebles tapizados con panel de administración completo.

## ✨ Características

### 🛍️ E-commerce Frontend
- Catálogo de productos con imágenes múltiples
- Sistema de categorías
- Carrito de compras
- Checkout completo
- Integración con Webpay Plus (Transbank)
- Diseño responsive

### 🔧 Panel de Administración
- Dashboard con estadísticas
- Gestión completa de productos
- Gestión de categorías
- Sistema de usuarios con roles
- Gestión de ventas
- Configuración del sitio
- Exportación de datos a Excel

### 💳 Sistema de Pagos
- Integración con Transbank Webpay Plus
- Ambiente de testing y producción
- Logs completos de transacciones
- Estadísticas de pagos

### 👥 Sistema de Usuarios
- Autenticación con JWT
- Roles: Admin, Vendedor, Operador
- Control de acceso por endpoints
- Cambio forzado de contraseñas

## 🚀 Tecnologías

- **Backend**: FastAPI, Python 3.8+
- **Base de Datos**: SQLAlchemy (SQLite/PostgreSQL)
- **Frontend**: Jinja2 Templates, TailwindCSS
- **Autenticación**: JWT, bcrypt
- **Pagos**: Transbank SDK
- **Exportación**: openpyxl

## 📋 Requisitos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)

## 🛠️ Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/FelipeJS1295/ecomercejerkhome.git
cd ecomercejerkhome
```

### 2. Crear entorno virtual
```bash
python -m venv venv

# En Windows
venv\Scripts\activate

# En Linux/macOS
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crea un archivo `.env` en la raíz del proyecto:

```env
# Base de datos
DATABASE_URL=sqlite:///./jerkhome.db

# JWT Secret (genera una clave secreta)
JWT_SECRET_KEY=tu_clave_secreta_muy_segura_aqui
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Configuración del servidor
DEBUG=True
HOST=0.0.0.0
PORT=8000

# Transbank (Webpay Plus)
TRANSBANK_COMMERCE_CODE=597055555532
TRANSBANK_API_KEY=579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C
TRANSBANK_ENVIRONMENT=testing  # o 'production'

# URLs del sitio
SITE_URL=http://localhost:8000
RETURN_URL=http://localhost:8000/webpay/return
```

### 5. Crear la base de datos
```bash
python -c "from app.database.database import engine; from app.models import *; Base.metadata.create_all(bind=engine)"
```

### 6. Crear usuario administrador inicial
```bash
python -c "
from app.database.database import get_db
from app.models.usuario import Usuario, RolUsuario, EstadoUsuario
import bcrypt

db = next(get_db())
password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

admin = Usuario(
    nombre='Administrador',
    apellido='Sistema',
    email='admin@jerkhome.cl',
    username='admin',
    password_hash=password_hash,
    rol=RolUsuario.ADMIN,
    estado=EstadoUsuario.ACTIVO,
    cambiar_password=False
)

db.add(admin)
db.commit()
print('Usuario administrador creado: admin / admin123')
"
```

## 🏃‍♂️ Ejecución

### Desarrollo
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Producción
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📁 Estructura del Proyecto

```
ecomercejerkhome/
├── app/
│   ├── database/
│   │   └── database.py          # Configuración de base de datos
│   ├── models/                  # Modelos SQLAlchemy
│   │   ├── categoria.py
│   │   ├── producto.py
│   │   ├── usuario.py
│   │   ├── ventas.py
│   │   ├── transbank.py
│   │   └── configuracion.py
│   ├── routes/                  # Rutas de la API
│   │   ├── admin/              # Rutas del panel admin
│   │   ├── auth_routes.py
│   │   ├── categoria_routes.py
│   │   ├── producto_routes.py
│   │   ├── checkout_routes.py
│   │   └── webpay_routes.py
│   ├── middleware/             # Middlewares
│   │   └── auth_middleware.py
│   ├── templates/              # Templates HTML
│   │   ├── admin/              # Templates del panel admin
│   │   └── auth/               # Templates de autenticación
│   ├── static/                 # Archivos estáticos
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   └── main.py                 # Aplicación principal
├── requirements.txt
├── .gitignore
├── .env.example
└── README.md
```

## 🔑 Credenciales por Defecto

**Panel de Administración:**
- URL: `http://localhost:8000/login`
- Usuario: `admin`
- Contraseña: `admin123`

## 🛡️ Roles de Usuario

### Administrador
- Acceso completo al sistema
- Gestión de usuarios
- Configuración del sitio
- Todas las funcionalidades

### Vendedor
- Gestión de productos y categorías
- Gestión de ventas
- Dashboard y estadísticas

### Operador
- Solo consulta y operaciones básicas
- Visualización de datos

## 💳 Configuración de Pagos

### Webpay Plus (Testing)
El sistema viene configurado con las credenciales de testing de Transbank:

- **Commerce Code**: 597055555532
- **API Key**: 579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C

### Tarjetas de Prueba
- **VISA**: 4051885600446623
- **CVV**: 123
- **Fecha**: Cualquier fecha futura

## 📊 Funcionalidades Principales

### E-commerce
- ✅ Catálogo de productos
- ✅ Carrito de compras
- ✅ Checkout con datos de envío
- ✅ Integración Webpay Plus
- ✅ Seguimiento de órdenes

### Panel Admin
- ✅ Dashboard con estadísticas
- ✅ CRUD completo de productos
- ✅ Gestión de categorías
- ✅ Sistema de usuarios
- ✅ Gestión de ventas
- ✅ Exportación a Excel
- ✅ Configuración del sitio

### Sistema de Pagos
- ✅ Integración Transbank
- ✅ Logs de transacciones
- ✅ Manejo de errores
- ✅ Confirmación automática

## 🚀 Despliegue

### Variables de Producción

Para producción, actualiza el archivo `.env`:

```env
DEBUG=False
TRANSBANK_ENVIRONMENT=production
TRANSBANK_COMMERCE_CODE=tu_commerce_code_real
TRANSBANK_API_KEY=tu_api_key_real
SITE_URL=https://tudominio.com
DATABASE_URL=postgresql://user:password@localhost/jerkhome
```

### Con Docker (Opcional)

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🤝 Contribución

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit tus cambios (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abre un Pull Request

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 📞 Soporte

Para soporte técnico o consultas:

- **Email**: soporte@jerkhome.cl
- **Desarrollador**: Felipe JS
- **GitHub**: https://github.com/FelipeJS1295

---

⭐ Si este proyecto te fue útil, ¡no olvides darle una estrella!