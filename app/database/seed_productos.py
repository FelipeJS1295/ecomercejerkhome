from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.models.categoria import Categoria
from app.models.producto import Producto

def crear_productos_prueba():
    db = SessionLocal()
    
    # Verificar si ya existen productos
    productos_existentes = db.query(Producto).count()
    if productos_existentes > 0:
        print("Los productos ya existen en la base de datos.")
        db.close()
        return
    
    # Obtener categorías
    categorias = {cat.nombre: cat.id for cat in db.query(Categoria).all()}
    
    # Productos de prueba
    productos = [
        {
            "sku": "SOF001",
            "nombre": "Sofá Madrid Clásico",
            "descripcion": "Sofá de 3 plazas tapizado en tela premium con estructura de madera sólida",
            "precio": 850000,
            "precio_oferta": 750000,
            "stock": 5,
            "categoria_id": categorias.get("Sofás"),
            "destacado": True
        },
        {
            "sku": "SEC001", 
            "nombre": "Seccional Barcelona",
            "descripcion": "Seccional modular de 5 plazas ideal para espacios amplios",
            "precio": 1200000,
            "stock": 3,
            "categoria_id": categorias.get("Seccionales"),
            "destacado": True
        },
        {
            "sku": "POL001",
            "nombre": "Poltrona Comfort",
            "descripcion": "Poltrona individual reclinable con tapizado de cuero sintético",
            "precio": 450000,
            "stock": 8,
            "categoria_id": categorias.get("Poltronas")
        }
    ]
    
    for prod_data in productos:
        producto = Producto(**prod_data)
        db.add(producto)
    
    db.commit()
    db.close()
    print("Productos de prueba creados exitosamente.")

if __name__ == "__main__":
    crear_productos_prueba()