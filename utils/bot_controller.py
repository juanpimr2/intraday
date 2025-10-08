# utils/bot_controller.py
"""
BotController - Control de estado del bot (solo en memoria, sin BD)

Gestiona el estado de ejecución del bot (running/paused) sin persistencia.
El estado es volátil y vive solo en memoria durante la ejecución.

Interfaz para el dashboard:
    controller = BotController(api_client)
    controller.start_bot()
    controller.stop_bot()
    status = controller.get_status()
"""

import threading
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BotController:
    """
    Controla el estado de ejecución del bot (en memoria, thread-safe)
    
    NO persiste estado en base de datos.
    El bot arranca pausado por defecto y requiere llamada explícita a start_bot().
    """
    
    def __init__(self, api_client, *, poll_seconds: int = 15):
        """
        Args:
            api_client: Cliente de Capital.com API
            poll_seconds: Intervalo de polling (reservado para uso futuro)
        """
        self.api = api_client
        self._poll_seconds = max(int(poll_seconds), 3)
        
        # Lock para thread-safety
        self._lock = threading.RLock()
        
        # Estado interno (EN MEMORIA)
        self._is_running = False
        self._manual_override = False
        self._last_command = None
        self._last_heartbeat = None
    
    # =========================================================================
    # API PÚBLICA (usada por dashboard y trading_bot)
    # =========================================================================
    
    def start_bot(self) -> None:
        """
        Inicia el bot (marca como running)
        Thread-safe: puede ser llamado desde el dashboard mientras el bot corre
        """
        with self._lock:
            if self._is_running:
                logger.info("🔄 start_bot(): Bot ya estaba corriendo (no-op)")
                self._last_command = "start (already running)"
                return
            
            self._is_running = True
            self._manual_override = False
            self._last_command = "start"
            self._last_heartbeat = datetime.now()
            
            logger.info("✅ BotController: Bot iniciado (running=True)")
    
    def stop_bot(self) -> None:
        """
        Pausa el bot (marca como stopped)
        Thread-safe: puede ser llamado desde el dashboard mientras el bot corre
        """
        with self._lock:
            if not self._is_running:
                logger.info("🔄 stop_bot(): Bot ya estaba pausado (no-op)")
                self._last_command = "stop (already stopped)"
                return
            
            self._is_running = False
            self._manual_override = True
            self._last_command = "stop"
            self._last_heartbeat = datetime.now()
            
            logger.info("⏸️ BotController: Bot pausado (running=False)")
    
    def is_running(self) -> bool:
        """
        Verifica si el bot está corriendo
        
        Returns:
            bool: True si el bot debe operar, False si está pausado
        """
        with self._lock:
            return self._is_running
    
    def get_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado completo del bot
        
        Returns:
            Dict con:
                - running: bool
                - manual_override: bool
                - last_command: str
                - last_heartbeat: str (ISO format)
        """
        with self._lock:
            return {
                'running': self._is_running,
                'manual_override': self._manual_override,
                'last_command': self._last_command,
                'last_heartbeat': self._last_heartbeat.isoformat() if self._last_heartbeat else None
            }
    
    def update_heartbeat(self) -> None:
        """
        Actualiza el timestamp del último heartbeat
        Debe ser llamado periódicamente desde el loop principal del bot
        """
        with self._lock:
            self._last_heartbeat = datetime.now()
    
    # =========================================================================
    # UTILIDADES INTERNAS
    # =========================================================================
    
    def reset(self) -> None:
        """
        Resetea el estado del controlador (útil para testing)
        ⚠️ NO usar en producción a menos que sea necesario
        """
        with self._lock:
            self._is_running = False
            self._manual_override = False
            self._last_command = "reset"
            self._last_heartbeat = datetime.now()
            logger.warning("⚠️ BotController reseteado manualmente")