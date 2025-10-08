# utils/bot_state.py
"""
Estado global del bot (compartido entre dashboard y bot principal)
Evita imports circulares y usa un singleton simple
"""

import threading
from datetime import datetime
from typing import Optional, Dict


class BotState:
    """Singleton para manejar el estado del bot EN MEMORIA"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._running = False
        self._manual_override = False
        self._last_command = None
        self._last_heartbeat = None
        self._initialized = True
    
    def start(self) -> None:
        """Inicia el bot"""
        with self._lock:
            self._running = True
            self._manual_override = False
            self._last_command = "START"
            self._last_heartbeat = datetime.now().isoformat()
    
    def stop(self) -> None:
        """Pausa el bot"""
        with self._lock:
            self._running = False
            self._manual_override = True
            self._last_command = "STOP"
            self._last_heartbeat = datetime.now().isoformat()
    
    def update_heartbeat(self) -> None:
        """Actualiza el heartbeat"""
        with self._lock:
            self._last_heartbeat = datetime.now().isoformat()
    
    def get_status(self) -> Dict:
        """Obtiene el estado actual"""
        with self._lock:
            return {
                'running': self._running,
                'manual_override': self._manual_override,
                'last_command': self._last_command,
                'last_heartbeat': self._last_heartbeat
            }
    
    def is_running(self) -> bool:
        """Verifica si el bot está corriendo"""
        with self._lock:
            return self._running


# Instancia global (singleton)
bot_state = BotState()