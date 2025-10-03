"""
Controlador del bot - Gestiona el estado y comandos
"""

import json
import os
import logging
from threading import Lock

logger = logging.getLogger(__name__)

STATE_FILE = 'bot_state.json'

class BotController:
    """Controla el estado del bot de trading"""
    
    def __init__(self):
        self.lock = Lock()
        self._ensure_state_file()
    
    def _ensure_state_file(self):
        """Crea el archivo de estado si no existe"""
        if not os.path.exists(STATE_FILE):
            self._write_state({
                'running': True,
                'manual_override': False,
                'last_command': None
            })
    
    def _read_state(self) -> dict:
        """Lee el estado actual"""
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {'running': True, 'manual_override': False}
    
    def _write_state(self, state: dict):
        """Escribe el estado"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error escribiendo estado: {e}")
    
    def is_running(self) -> bool:
        """Verifica si el bot debe estar corriendo"""
        with self.lock:
            state = self._read_state()
            return state.get('running', True)
    
    def start_bot(self):
        """Inicia el bot"""
        with self.lock:
            state = self._read_state()
            state['running'] = True
            state['manual_override'] = True
            state['last_command'] = 'start'
            self._write_state(state)
            logger.info("✅ Bot iniciado manualmente")
    
    def stop_bot(self):
        """Detiene el bot"""
        with self.lock:
            state = self._read_state()
            state['running'] = False
            state['manual_override'] = True
            state['last_command'] = 'stop'
            self._write_state(state)
            logger.info("🛑 Bot detenido manualmente")
    
    def get_status(self) -> dict:
        """Obtiene el estado completo"""
        with self.lock:
            return self._read_state()