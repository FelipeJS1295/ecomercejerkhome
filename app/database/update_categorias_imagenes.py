from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.models.categoria import Categoria

def agregar_imagenes_categorias():
    db = SessionLocal()
    
    # Imágenes por defecto para cada categoría
    imagenes_categorias = {
        "Sofás": "categoria-sofas.jpg",
        "Seccionales": "categoria-seccionales.jpg", 
        "Poltronas": "categoria-poltronas.jpg",
        "Camas": "categoria-camas.jpg",
        "Respaldos": "categoria-respaldos.jpg",
        "Living": "categoria-living.jpg"
    }
    
    # Actualizar cada categoría con su imagen
    for nombre_categoria, imagen in imagenes_categorias.items():
        categoria = db.query(Categoria).filter(Categoria.nombre == nombre_categoria).first()
        if categoria:
            categoria.imagen = imagen
            print(f"Imagen '{imagen}' agregada a la categoría '{nombre_categoria}'")
        else:
            print(f"Categoría '{nombre_categoria}' no encontrada")
    
    db.commit()
    db.close()
    print("Imágenes de categorías actualizadas exitosamente.")

if __name__ == "__main__":
    agregar_imagenes_categorias()