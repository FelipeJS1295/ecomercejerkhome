from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.models.categoria import Categoria

def crear_categorias_iniciales():
    db = SessionLocal()
    
    # Verificar si ya existen categorías
    categorias_existentes = db.query(Categoria).count()
    if categorias_existentes > 0:
        print("Las categorías ya existen en la base de datos.")
        db.close()
        return
    
    # Crear las categorías principales
    categorias = [
        {"nombre": "Sofás", "descripcion": "Sofás cómodos y elegantes para tu sala de estar"},
        {"nombre": "Seccionales", "descripcion": "Seccionales modulares para espacios amplios"},
        {"nombre": "Poltronas", "descripcion": "Poltronas individuales de máximo confort"},
        {"nombre": "Camas", "descripcion": "Camas tapizadas con diseños modernos"},
        {"nombre": "Respaldos", "descripcion": "Respaldos para camas con acabados premium"},
        {"nombre": "Living", "descripcion": "Conjuntos completos para tu sala de estar"}
    ]
    
    for cat_data in categorias:
        categoria = Categoria(**cat_data)
        db.add(categoria)
    
    db.commit()
    db.close()
    print("Categorías creadas exitosamente.")

if __name__ == "__main__":
    crear_categorias_iniciales()