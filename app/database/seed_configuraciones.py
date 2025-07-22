from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.models.configuracion import Configuracion

def crear_configuraciones_iniciales():
    db = SessionLocal()
    
    # Verificar si ya existen configuraciones
    configuraciones_existentes = db.query(Configuracion).count()
    if configuraciones_existentes > 0:
        print("Las configuraciones ya existen en la base de datos.")
        db.close()
        return
    
    # Configuraciones iniciales
    configuraciones = [
        # Información General
        {
            "clave": "sitio_nombre",
            "valor": "JerkHome",
            "tipo": "texto",
            "categoria": "general",
            "descripcion": "Nombre del sitio web"
        },
        {
            "clave": "sitio_descripcion",
            "valor": "Fábrica de muebles tapizados de alta calidad",
            "tipo": "texto",
            "categoria": "general",
            "descripcion": "Descripción corta del sitio"
        },
        {
            "clave": "sitio_slogan",
            "valor": "Calidad y confort en cada pieza",
            "tipo": "texto",
            "categoria": "general",
            "descripcion": "Slogan del sitio"
        },
        
        # Información de Contacto
        {
            "clave": "contacto_telefono",
            "valor": "+56 9 1234 5678",
            "tipo": "telefono",
            "categoria": "contacto",
            "descripcion": "Teléfono principal"
        },
        {
            "clave": "contacto_email",
            "valor": "contacto@jerkhome.cl",
            "tipo": "email",
            "categoria": "contacto",
            "descripcion": "Email de contacto"
        },
        {
            "clave": "contacto_direccion",
            "valor": "La Pintana, Santiago, Chile",
            "tipo": "texto",
            "categoria": "contacto",
            "descripcion": "Dirección física"
        },
        {
            "clave": "contacto_horarios",
            "valor": "Lunes a Viernes: 9:00 - 18:00 hrs",
            "tipo": "texto",
            "categoria": "contacto",
            "descripcion": "Horarios de atención"
        },
        
        # Redes Sociales
        {
            "clave": "redes_facebook",
            "valor": "https://facebook.com/jerkhome",
            "tipo": "url",
            "categoria": "redes_sociales",
            "descripcion": "URL de Facebook"
        },
        {
            "clave": "redes_instagram",
            "valor": "https://instagram.com/jerkhome",
            "tipo": "url",
            "categoria": "redes_sociales",
            "descripcion": "URL de Instagram"
        },
        {
            "clave": "redes_whatsapp",
            "valor": "+56912345678",
            "tipo": "telefono",
            "categoria": "redes_sociales",
            "descripcion": "WhatsApp para contacto"
        },
        
        # Banner/Hero Section
        {
            "clave": "banner_titulo",
            "valor": "JerkHome",
            "tipo": "texto",
            "categoria": "banner",
            "descripcion": "Título principal del banner"
        },
        {
            "clave": "banner_subtitulo",
            "valor": "Fábrica de Muebles Tapizados de Alta Calidad",
            "tipo": "texto",
            "categoria": "banner",
            "descripcion": "Subtítulo del banner"
        },
        {
            "clave": "banner_descripcion",
            "valor": "Sofás, seccionales, poltronas, camas, respaldos y living diseñados especialmente para tu hogar.",
            "tipo": "texto",
            "categoria": "banner",
            "descripcion": "Descripción del banner"
        },
        {
            "clave": "banner_imagen",
            "valor": "hero-sofa.jpg",
            "tipo": "imagen",
            "categoria": "banner",
            "descripcion": "Imagen principal del banner"
        },
        
        # SEO
        {
            "clave": "seo_titulo",
            "valor": "JerkHome - Fábrica de Muebles Tapizados",
            "tipo": "texto",
            "categoria": "seo",
            "descripcion": "Título SEO del sitio"
        },
        {
            "clave": "seo_descripcion",
            "valor": "Descubre nuestra amplia gama de muebles tapizados: sofás, seccionales, poltronas y más. Calidad y confort garantizados.",
            "tipo": "texto",
            "categoria": "seo",
            "descripcion": "Meta descripción para SEO"
        },
        {
            "clave": "seo_palabras_clave",
            "valor": "muebles tapizados, sofás, seccionales, poltronas, camas, JerkHome, Chile",
            "tipo": "texto",
            "categoria": "seo",
            "descripcion": "Palabras clave SEO"
        }
    ]
    
    for config_data in configuraciones:
        configuracion = Configuracion(**config_data)
        db.add(configuracion)
    
    db.commit()
    db.close()
    print("Configuraciones iniciales creadas exitosamente.")

if __name__ == "__main__":
    crear_configuraciones_iniciales()