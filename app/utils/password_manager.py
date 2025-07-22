import re
import bcrypt
import secrets
from typing import Tuple, Optional
from datetime import datetime, timedelta
from passlib.context import CryptContext
from passlib.hash import bcrypt as passlib_bcrypt

class SecurePasswordManager:
    """Gestor de contraseñas seguro con políticas estrictas"""
    
    def __init__(self):
        # Configuración de bcrypt con trabajo factor alto
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=12  # Factor de trabajo alto para seguridad
        )
        
        # Patrones para validación de contraseñas
        self.patterns = {
            'uppercase': re.compile(r'[A-Z]'),
            'lowercase': re.compile(r'[a-z]'),
            'numbers': re.compile(r'\d'),
            'special': re.compile(r'[!@#$%^&*(),.?":{}|<>]')
        }
    
    def validate_password_strength(self, password: str) -> Tuple[bool, list]:
        """
        Valida la fortaleza de una contraseña
        Returns: (es_válida, lista_de_errores)
        """
        errors = []
        
        # Longitud mínima
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres")
        
        # Máxima longitud (prevenir DoS)
        if len(password) > 128:
            errors.append("La contraseña no puede exceder 128 caracteres")
        
        # Mayúsculas
        if not self.patterns['uppercase'].search(password):
            errors.append("Debe contener al menos una letra mayúscula")
        
        # Minúsculas
        if not self.patterns['lowercase'].search(password):
            errors.append("Debe contener al menos una letra minúscula")
        
        # Números
        if not self.patterns['numbers'].search(password):
            errors.append("Debe contener al menos un número")
        
        # Caracteres especiales
        if not self.patterns['special'].search(password):
            errors.append("Debe contener al menos un carácter especial (!@#$%^&*)")
        
        # Patrones débiles comunes
        weak_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'admin',
            r'jerkhome',
            r'(.)\1{3,}',  # Caracteres repetidos
        ]
        
        for pattern in weak_patterns:
            if re.search(pattern, password.lower()):
                errors.append("La contraseña contiene patrones comunes o débiles")
                break
        
        return len(errors) == 0, errors
    
    def hash_password(self, password: str) -> str:
        """
        Hashea una contraseña de forma segura
        """
        # Validar fortaleza antes de hashear
        is_valid, errors = self.validate_password_strength(password)
        if not is_valid:
            raise ValueError(f"Contraseña no cumple con los requisitos: {', '.join(errors)}")
        
        # Generar hash seguro
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifica una contraseña contra su hash
        """
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception:
            # Log del intento fallido pero no exponer detalles
            return False
    
    def generate_secure_password(self, length: int = 12) -> str:
        """
        Genera una contraseña segura automáticamente
        """
        if length < 8:
            length = 8
        if length > 128:
            length = 128
        
        # Caracteres disponibles
        uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        lowercase = 'abcdefghijklmnopqrstuvwxyz'
        numbers = '0123456789'
        special = '!@#$%^&*'
        
        # Garantizar al menos uno de cada tipo
        password_chars = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(numbers),
            secrets.choice(special)
        ]
        
        # Completar con caracteres aleatorios
        all_chars = uppercase + lowercase + numbers + special
        for _ in range(length - 4):
            password_chars.append(secrets.choice(all_chars))
        
        # Mezclar aleatoriamente
        secrets.SystemRandom().shuffle(password_chars)
        
        return ''.join(password_chars)
    
    def check_password_history(self, user_id: int, new_password: str, 
                             password_history: list) -> bool:
        """
        Verifica que la contraseña no haya sido usada recientemente
        """
        # Verificar contra las últimas 5 contraseñas
        for old_hash in password_history[-5:]:
            if self.verify_password(new_password, old_hash):
                return False
        return True
    
    def get_password_strength_score(self, password: str) -> int:
        """
        Calcula un puntaje de fortaleza de 0 a 100
        """
        score = 0
        
        # Longitud (máximo 25 puntos)
        length_score = min(25, len(password) * 2)
        score += length_score
        
        # Variedad de caracteres (máximo 60 puntos)
        if self.patterns['lowercase'].search(password):
            score += 15
        if self.patterns['uppercase'].search(password):
            score += 15
        if self.patterns['numbers'].search(password):
            score += 15
        if self.patterns['special'].search(password):
            score += 15
        
        # Penalizar patrones débiles (máximo -30 puntos)
        weak_patterns = [
            (r'(.)\1{2,}', -10),  # Caracteres repetidos
            (r'123|abc|qwe', -10),  # Secuencias comunes
            (r'password|admin', -10)  # Palabras comunes
        ]
        
        for pattern, penalty in weak_patterns:
            if re.search(pattern, password.lower()):
                score += penalty
        
        # Bonus por longitud extra (máximo 15 puntos)
        if len(password) >= 12:
            score += 10
        if len(password) >= 16:
            score += 5
        
        return max(0, min(100, score))

# Instancia global del gestor de contraseñas
password_manager = SecurePasswordManager()