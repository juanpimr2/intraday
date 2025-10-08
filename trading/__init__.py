# trading/__init__.py
"""Paquete trading: init seguro (sin imports duros que rompan)."""

__all__ = []

# Exponer PositionManager si está disponible (no es obligatorio para importar submódulos)
try:
    from .position_manager import PositionManager  # noqa: F401
    __all__.append("PositionManager")
except Exception:
    pass

# Exponer TradingBot solo si el módulo existe (no bloquear el paquete si falta)
try:
    from .trading_bot import TradingBot  # noqa: F401
    __all__.append("TradingBot")
except Exception:
    pass
