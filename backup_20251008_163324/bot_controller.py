# utils/bot_controller.py
"""
BotController con persistencia en vivo:
- Guarda equity/cash/open_positions en SQLite periódicamente (PositionManager.save_equity_point).
- Registra trades cerrados a demanda (PositionManager.record_filled_trade).
- Manejo de start/stop thread-safe + status para el dashboard.

Interfaz estable para dashboard/app.py:
    ctrl = BotController(api_client)
    ctrl.start_bot()
    ctrl.stop_bot()
    st = ctrl.get_status()

Integraciones clave:
    - PositionManager.suggest_size_for_signal(...) (para sizing en vivo si lo usas aquí)
    - PositionManager.save_equity_point(...)
    - PositionManager.record_filled_trade(...)

No asume cómo cierras trades: expone `record_trade_close(...)` para que tu
módulo de ejecución llame cuando haya un cierre real (deal cerrado en broker).
"""

from __future__ import annotations

import threading
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timezone

try:
    # Dependencia local del proyecto
    from trading.position_manager import PositionManager
except Exception:  # pragma: no cover
    PositionManager = None  # Para no romper import si estás instalando deps

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class ControllerStatus:
    running: bool = False
    manual_override: bool = False
    last_command: Optional[str] = None
    last_heartbeat_utc: Optional[str] = None
    last_equity_saved_utc: Optional[str] = None
    last_error: Optional[str] = None


class BotController:
    """
    Controla el ciclo en vivo del bot con guardado periódico de equity y registro de cierres.
    """

    def __init__(self, api_client, *, poll_seconds: int = 15):
        """
        Args:
            api_client: cliente de Capital.com (debe exponer get_account_info(), get_positions(), etc.)
            poll_seconds: intervalo del loop para guardar equity en DB.
        """
        if PositionManager is None:
            raise RuntimeError("No se pudo importar trading.position_manager.PositionManager")

        self.api = api_client
        self.pm = PositionManager(self.api, enable_db=True)  # instancia con DB habilitada

        self._poll_seconds = max(int(poll_seconds), 3)
        self._thread: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()
        self._lock = threading.RLock()
        self._status = ControllerStatus(running=False)

    # ---------------------------------------------------------------------
    # PÚBLICO (dashboard)
    # ---------------------------------------------------------------------
    def start_bot(self) -> None:
        with self._lock:
            if self._status.running:
                logger.info("BotController.start_bot(): ya estaba en ejecución.")
                self._status.last_command = "start (noop)"
                return

            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._run_loop, name="BotLiveLoop", daemon=True)
            self._thread.start()
            self._status.running = True
            self._status.last_command = "start"
            logger.info("✅ BotController: hilo de ejecución iniciado.")

    def stop_bot(self) -> None:
        with self._lock:
            if not self._status.running:
                logger.info("BotController.stop_bot(): ya estaba detenido.")
                self._status.last_command = "stop (noop)"
                return

            self._stop_evt.set()
            th = self._thread
            self._thread = None
            self._status.running = False
            self._status.last_command = "stop"
        if th and th.is_alive():
            th.join(timeout=3.0)
        logger.info("🛑 BotController: hilo de ejecución detenido.")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            st = {
                "status": "running" if self._status.running else "stopped",
                "running": self._status.running,
                "manual_override": self._status.manual_override,
                "last_command": self._status.last_command,
                "last_heartbeat_utc": self._status.last_heartbeat_utc,
                "last_equity_saved_utc": self._status.last_equity_saved_utc,
                "is_trading_hours": self._is_trading_hours_now(),
                "last_error": self._status.last_error,
            }
        return st

    # ---------------------------------------------------------------------
    # API para registrar un trade cerrado (tu motor debe llamar a esto)
    # ---------------------------------------------------------------------
    def record_trade_close(
        self,
        *,
        epic: str,
        side: str,
        entry_ts,
        exit_ts,
        entry_price: float,
        exit_price: float,
        size_eur: float,
        units: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
        confidence: float,
        regime: str = "lateral",
        duration_hours: float = 0.0,
    ) -> None:
        """
        Registra un trade CERRADO en la base SQLite (ver trading/db.py).
        Llama a esto desde tu flujo de ejecución real cuando detectes un cierre en broker.
        """
        try:
            self.pm.record_filled_trade(
                epic=epic, side=side,
                entry_ts=entry_ts, exit_ts=exit_ts,
                entry_price=entry_price, exit_price=exit_price,
                size_eur=size_eur, units=units,
                pnl=pnl, pnl_pct=pnl_pct,
                reason=reason, confidence=confidence,
                regime=regime, duration_hours=duration_hours,
            )
            logger.info(f"💾 Trade registrado en DB: {epic} {side} pnl={pnl:.2f}€ ({pnl_pct:.2f}%)")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo registrar trade en DB: {e}")
            with self._lock:
                self._status.last_error = str(e)

    # ---------------------------------------------------------------------
    # LOOP PRINCIPAL
    # ---------------------------------------------------------------------
    def _run_loop(self) -> None:
        """
        Loop periódico para persistir equity/cash/open_positions.
        No abre/cierra operaciones; solo registra estado de cuenta/posiciones.
        Tus módulos de ejecución pueden usar self.pm para sizing/SLTP y al cerrar,
        deben llamar a record_trade_close(...).
        """
        logger.info("▶️ BotController loop iniciado.")
        while not self._stop_evt.is_set():
            try:
                now_utc = datetime.now(timezone.utc)
                with self._lock:
                    self._status.last_heartbeat_utc = now_utc.isoformat().replace("+00:00", "Z")

                if self._is_trading_hours_now():
                    self._persist_equity_snapshot(now_utc)
                else:
                    logger.debug("Fuera de trading hours; no se persiste equity en este tick.")

                # pequeño sleep con respuesta rápida al stop
                for _ in range(self._poll_seconds):
                    if self._stop_evt.is_set():
                        break
                    time.sleep(1.0)

            except Exception as e:  # protección del loop
                logger.exception(f"Error en loop del BotController: {e}")
                with self._lock:
                    self._status.last_error = str(e)
                # evita tight-loop en caso de fallo
                time.sleep(2.0)

        logger.info("⏸️ BotController loop finalizado.")

    def _persist_equity_snapshot(self, now_utc: datetime) -> None:
        """
        Lee cuenta y posiciones desde la API y guarda un punto de equity.
        """
        try:
            # 1) Obtener info de cuenta (balance/disponible)
            account_info = self.api.get_account_info()
            balance = float(account_info.get("balance", {}).get("balance", 0.0))
            available = float(account_info.get("balance", {}).get("available", 0.0))

            # 2) Posiciones abiertas
            positions = []
            try:
                positions = self.api.get_positions()
            except Exception as e:
                logger.debug(f"No se pudieron leer posiciones: {e}")
            open_positions = int(len(positions) if positions else 0)

            # 3) Persistir equity (equity ≈ balance; cash ≈ available)
            self.pm.save_equity_point(
                equity=balance,
                cash=available,
                open_positions=open_positions,
                ts_utc=now_utc,
            )

            with self._lock:
                self._status.last_equity_saved_utc = now_utc.isoformat().replace("+00:00", "Z")

            logger.debug(f"💾 Equity guardada: equity={balance:.2f}, cash={available:.2f}, open={open_positions}")

        except Exception as e:
            logger.warning(f"⚠️ No se pudo persistir equity: {e}")
            with self._lock:
                self._status.last_error = str(e)

    # ---------------------------------------------------------------------
    # UTILIDADES
    # ---------------------------------------------------------------------
    def _is_trading_hours_now(self) -> bool:
        """
        Comprueba si estamos dentro del horario de trading configurado (CET/CEST).
        Usa START_HOUR y END_HOUR de Config.
        """
        try:
            # hora local Madrid
            # Nota: evitamos dependencias externas. Asumimos offset de 1h (CET) o 2h (CEST)
            # Para mayor precisión podrías usar zoneinfo('Europe/Madrid').
            now_utc = datetime.now(timezone.utc)
            # offset "aprox" por estación: si prefieres exacto, usa zoneinfo
            # aquí optamos por heurística simple: marzo–octubre (inclusive) => +2, resto +1
            month = now_utc.month
            offset_hours = 2 if 3 <= month <= 10 else 1
            hour_cet = (now_utc.hour + offset_hours) % 24

            start_h = int(getattr(Config, "START_HOUR", 9))
            end_h = int(getattr(Config, "END_HOUR", 22))

            if start_h <= hour_cet < end_h:
                return True
            return False
        except Exception:
            return True  # si hay error, no bloquear el loop
