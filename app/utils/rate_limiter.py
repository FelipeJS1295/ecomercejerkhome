import time
import redis
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from app.config import security_config
import threading
import logging

class RateLimiter:
    """Sistema de rate limiting avanzado con múltiples estrategias"""
    
    def __init__(self):
        self.limits = {
            # Autenticación
            "login_attempts": {"count": 5, "window": 900},  # 5 intentos en 15 min
            "failed_auth": {"count": 10, "window": 3600},   # 10 fallos en 1 hora
            "auth_check": {"count": 100, "window": 60},     # 100 checks por minuto
            
            # API general
            "api_requests": {"count": 1000, "window": 3600}, # 1000 req/hora
            "file_upload": {"count": 10, "window": 300},     # 10 uploads en 5 min
            
            # Admin panel
            "admin_actions": {"count": 50, "window": 300},   # 50 acciones en 5 min
            "password_changes": {"count": 3, "window": 3600}, # 3 cambios/hora
        }
        
        # Intentar conectar con Redis
        try:
            self.redis_client = redis.Redis(
                host='localhost', 
                port=6379, 
                db=2, 
                decode_responses=True,
                socket_connect_timeout=1
            )
            self.redis_client.ping()
            self.redis_available = True
            self.logger = logging.getLogger("rate_limiter")
            self.logger.info("Rate limiter using Redis backend")
        except:
            self.redis_available = False
            self.in_memory_store = defaultdict(lambda: defaultdict(deque))
            self.cleanup_lock = threading.Lock()
            self.logger = logging.getLogger("rate_limiter")
            self.logger.warning("Rate limiter using in-memory backend (not recommended for production)")
    
    def _get_key(self, identifier: str, action: str) -> str:
        """Genera clave única para el rate limiting"""
        return f"rate_limit:{action}:{identifier}"
    
    def _cleanup_memory_store(self) -> None:
        """Limpia entradas expiradas del store en memoria"""
        with self.cleanup_lock:
            current_time = time.time()
            
            for action in list(self.in_memory_store.keys()):
                for identifier in list(self.in_memory_store[action].keys()):
                    window = self.limits.get(action, {}).get("window", 3600)
                    cutoff_time = current_time - window
                    
                    # Remover entradas antiguas
                    queue = self.in_memory_store[action][identifier]
                    while queue and queue[0] < cutoff_time:
                        queue.popleft()
                    
                    # Remover identificadores vacíos
                    if not queue:
                        del self.in_memory_store[action][identifier]
                
                # Remover acciones vacías
                if not self.in_memory_store[action]:
                    del self.in_memory_store[action]
    
    def is_rate_limited(self, identifier: str, action: str) -> bool:
        """
        Verifica si un identificador está rate limited para una acción
        """
        if action not in self.limits:
            return False
        
        limit_config = self.limits[action]
        max_count = limit_config["count"]
        window = limit_config["window"]
        
        if self.redis_available:
            return self._is_rate_limited_redis(identifier, action, max_count, window)
        else:
            return self._is_rate_limited_memory(identifier, action, max_count, window)
    
    def _is_rate_limited_redis(self, identifier: str, action: str, 
                              max_count: int, window: int) -> bool:
        """Rate limiting usando Redis"""
        key = self._get_key(identifier, action)
        current_time = time.time()
        
        try:
            pipe = self.redis_client.pipeline()
            
            # Remover entradas antiguas
            pipe.zremrangebyscore(key, 0, current_time - window)
            
            # Contar entradas actuales
            pipe.zcard(key)
            
            results = pipe.execute()
            current_count = results[1]
            
            return current_count >= max_count
            
        except Exception as e:
            self.logger.error(f"Redis rate limit check failed: {e}")
            return False  # En caso de error, no bloquear
    
    def _is_rate_limited_memory(self, identifier: str, action: str,
                               max_count: int, window: int) -> bool:
        """Rate limiting usando memoria"""
        current_time = time.time()
        cutoff_time = current_time - window
        
        # Limpiar periódicamente
        if time.time() % 60 < 1:  # Cada minuto aproximadamente
            self._cleanup_memory_store()
        
        queue = self.in_memory_store[action][identifier]
        
        # Remover entradas antiguas
        while queue and queue[0] < cutoff_time:
            queue.popleft()
        
        return len(queue) >= max_count
    
    def increment_attempts(self, identifier: str, action: str) -> Tuple[bool, int, int]:
        """
        Incrementa el contador de intentos
        Returns: (is_rate_limited, current_count, remaining_count)
        """
        if action not in self.limits:
            return False, 0, float('inf')
        
        limit_config = self.limits[action]
        max_count = limit_config["count"]
        window = limit_config["window"]
        
        if self.redis_available:
            return self._increment_redis(identifier, action, max_count, window)
        else:
            return self._increment_memory(identifier, action, max_count, window)
    
    def _increment_redis(self, identifier: str, action: str,
                        max_count: int, window: int) -> Tuple[bool, int, int]:
        """Incrementa contador usando Redis"""
        key = self._get_key(identifier, action)
        current_time = time.time()
        
        try:
            pipe = self.redis_client.pipeline()
            
            # Remover entradas antiguas
            pipe.zremrangebyscore(key, 0, current_time - window)
            
            # Agregar nueva entrada
            pipe.zadd(key, {str(current_time): current_time})
            
            # Contar entradas actuales
            pipe.zcard(key)
            
            # Establecer TTL
            pipe.expire(key, window + 60)  # TTL con margen
            
            results = pipe.execute()
            current_count = results[2]
            
            is_limited = current_count > max_count
            remaining = max(0, max_count - current_count)
            
            if is_limited:
                self.logger.warning(
                    f"Rate limit exceeded: {identifier} for {action} "
                    f"({current_count}/{max_count})"
                )
            
            return is_limited, current_count, remaining
            
        except Exception as e:
            self.logger.error(f"Redis increment failed: {e}")
            return False, 0, max_count
    
    def _increment_memory(self, identifier: str, action: str,
                         max_count: int, window: int) -> Tuple[bool, int, int]:
        """Incrementa contador usando memoria"""
        current_time = time.time()
        cutoff_time = current_time - window
        
        queue = self.in_memory_store[action][identifier]
        
        # Remover entradas antiguas
        while queue and queue[0] < cutoff_time:
            queue.popleft()
        
        # Agregar nueva entrada
        queue.append(current_time)
        
        current_count = len(queue)
        is_limited = current_count > max_count
        remaining = max(0, max_count - current_count)
        
        if is_limited:
            self.logger.warning(
                f"Rate limit exceeded: {identifier} for {action} "
                f"({current_count}/{max_count})"
            )
        
        return is_limited, current_count, remaining
    
    def get_remaining_time(self, identifier: str, action: str) -> int:
        """
        Obtiene el tiempo restante hasta que se resetee el rate limit
        """
        if action not in self.limits:
            return 0
        
        window = self.limits[action]["window"]
        
        if self.redis_available:
            key = self._get_key(identifier, action)
            try:
                # Obtener la entrada más antigua
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                if oldest:
                    oldest_time = oldest[0][1]
                    remaining = max(0, window - (time.time() - oldest_time))
                    return int(remaining)
            except:
                pass
        else:
            queue = self.in_memory_store[action][identifier]
            if queue:
                oldest_time = queue[0]
                remaining = max(0, window - (time.time() - oldest_time))
                return int(remaining)
        
        return 0
    
    def reset_counter(self, identifier: str, action: str) -> bool:
        """
        Resetea el contador para un identificador y acción específicos
        """
        if self.redis_available:
            key = self._get_key(identifier, action)
            try:
                self.redis_client.delete(key)
                return True
            except:
                return False
        else:
            if action in self.in_memory_store:
                if identifier in self.in_memory_store[action]:
                    del self.in_memory_store[action][identifier]
                    return True
        
        return False
    
    def get_stats(self, identifier: str) -> Dict[str, Dict[str, int]]:
        """
        Obtiene estadísticas de rate limiting para un identificador
        """
        stats = {}
        
        for action in self.limits:
            if self.redis_available:
                key = self._get_key(identifier, action)
                try:
                    current_count = self.redis_client.zcard(key)
                except:
                    current_count = 0
            else:
                current_count = len(self.in_memory_store[action][identifier])
            
            max_count = self.limits[action]["count"]
            remaining_time = self.get_remaining_time(identifier, action)
            
            stats[action] = {
                "current": current_count,
                "limit": max_count,
                "remaining": max(0, max_count - current_count),
                "reset_in": remaining_time
            }
        
        return stats
    
    def is_ip_suspicious(self, ip: str) -> bool:
        """
        Determina si una IP es sospechosa basándose en patrones de uso
        """
        stats = self.get_stats(ip)
        
        # Múltiples rate limits activos
        active_limits = sum(1 for action_stats in stats.values() 
                           if action_stats["current"] >= action_stats["limit"] * 0.8)
        
        if active_limits >= 3:
            return True
        
        # Alto número de intentos fallidos de autenticación
        auth_stats = stats.get("failed_auth", {})
        if auth_stats.get("current", 0) >= auth_stats.get("limit", 10) * 0.6:
            return True
        
        return False

# Instancia global del rate limiter
rate_limiter = RateLimiter()