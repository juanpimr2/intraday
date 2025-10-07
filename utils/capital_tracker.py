"""
utils/capital_tracker.py

Gestor de capital diario y por trade con priorización por confianza.

Objetivo (Paso 5 de la hoja de ruta):
- Distribuir el capital operativo en *presupuesto diario* (p. ej. 8% del equity)
- Asignar a señales priorizando por `confidence`
- Respetar un máximo por operación (2–5% del equity, configurable)
- No romper producción: módulo desacoplado, integrable desde `position_manager`
  o directamente desde el motor de backtesting.

Conceptos clave
---------------
- *Daily Budget*: Porcentaje del equity asignable en el día (ej.: 8%).
- *Per-Trade Cap*: Límite por operación (ej.: 2%–5% del equity).
- *Confidence Priority*: Se ordenan las señales por `confidence` (desc).

Integración mínima sugerida (sin tocar tests):
----------------------------------------------
1) Instanciar el tracker al inicio del día o del backtest:
       tracker = CapitalTracker(initial_equity, daily_budget_pct=0.08, per_trade_cap_pct=0.03)

2) Antes de abrir posiciones, pedir asignaciones:
       allocations = tracker.allocate_for_signals(
           equity=current_equity,
           signals=signals,  # [{'epic': 'EURUSD', 'confidence': 0.73, 'current_price': 1.0831, ...}, ...]
           current_dt=current_datetime
       )

   `allocations` es un dict: { 'EURUSD': euros_asignados, 'GBPUSD': euros_asignados, ... }

3) Al ejecutar una orden, registrar el consumo:
       size_eur = allocations[signal['epic']]
       tracker.record_fill(epic=signal['epic'], amount=size_eur, when=current_datetime)

Notas:
- Si no hay suficiente presupuesto diario, asignará 0 a las señales de menor prioridad.
- Si una señal no tiene `confidence`, se asume 0.
- Este módulo es *stateless respecto a la estrategia* y puede testearse en aislamiento.

Autor: Trading Bot — Backtesting/Execution Utilities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


def _ensure_utc(dt: datetime) -> datetime:
    """Devuelve `dt` con tzinfo UTC (si no lo tiene, asume UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _same_utc_day(a: datetime, b: datetime) -> bool:
    a = _ensure_utc(a)
    b = _ensure_utc(b)
    return (a.year, a.month, a.day) == (b.year, b.month, b.day)


@dataclass
class CapitalTracker:
    """
    Controla el presupuesto diario y el límite por operación con prioridad por confianza.
    """

    initial_equity: float
    daily_budget_pct: float = 0.08          # 8% del equity por día (target: 40% semanal / 5 días)
    per_trade_cap_pct: float = 0.03         # 3% del equity por trade (recomendado 0.02–0.05)
    min_allocation_eur: float = 0.0         # piso por trade (opcional)
    last_reset_at: Optional[datetime] = None
    _spent_today_eur: float = field(default=0.0, init=False)

    # --- API pública --------------------------------------------------------

    def reset_day_if_needed(self, now: datetime) -> None:
        """
        Reinicia el presupuesto si ha cambiado el día (UTC).
        """
        now = _ensure_utc(now)
        if self.last_reset_at is None or not _same_utc_day(now, self.last_reset_at):
            self.last_reset_at = now
            self._spent_today_eur = 0.0

    def budget_today_eur(self, equity: float) -> float:
        """
        Presupuesto total del día en euros (equity * daily_budget_pct).
        """
        budget = max(equity, 0.0) * max(self.daily_budget_pct, 0.0)
        return float(budget)

    def remaining_today_eur(self, equity: float) -> float:
        """
        Presupuesto restante para hoy en euros.
        """
        remaining = self.budget_today_eur(equity) - self._spent_today_eur
        return float(max(0.0, remaining))

    def per_trade_cap_eur(self, equity: float) -> float:
        """
        Límite por operación en euros (equity * per_trade_cap_pct).
        """
        cap = max(equity, 0.0) * max(self.per_trade_cap_pct, 0.0)
        return float(max(cap, self.min_allocation_eur))

    def allocate_for_signals(
        self,
        equity: float,
        signals: List[Dict],
        current_dt: datetime,
        *,
        allow_partial: bool = True,
    ) -> Dict[str, float]:
        """
        Asigna presupuesto a una lista de señales priorizando por `confidence`.

        Parámetros
        ----------
        equity : float
            Equity actual (para calcular presupuesto y límites).
        signals : List[Dict]
            Señales con al menos 'epic' y 'confidence'. Ej.:
                {'epic': 'EURUSD', 'confidence': 0.72, 'current_price': 1.0831, ...}
        current_dt : datetime
            Momento actual (para control de día).
        allow_partial : bool
            Si True, la última señal puede recibir menos del `per_trade_cap` si el resto
            del presupuesto diario no alcanza. Si False, se asigna 0 en ese caso.

        Retorna
        -------
        Dict[str, float]
            Mapa epic -> euros asignados (0 si no alcanzó el presupuesto).
        """
        self.reset_day_if_needed(current_dt)
        remaining = self.remaining_today_eur(equity)
        cap_per_trade = self.per_trade_cap_eur(equity)

        # Ordenar por confianza desc
        ordered = sorted(signals, key=lambda s: float(s.get("confidence", 0.0)), reverse=True)

        allocations: Dict[str, float] = {}

        for sig in ordered:
            epic = str(sig.get("epic", ""))
            if not epic:
                continue

            if remaining <= 0.0:
                allocations[epic] = 0.0
                continue

            desired = cap_per_trade

            if remaining >= desired:
                size = desired
            else:
                size = remaining if allow_partial else 0.0

            # Enforce mínimo
            if size < self.min_allocation_eur:
                allocations[epic] = 0.0
                continue

            allocations[epic] = float(size)
            remaining -= size

        return allocations

    def record_fill(self, epic: str, amount: float, when: Optional[datetime] = None) -> None:
        """
        Registra el consumo de presupuesto tras una ejecución.

        `amount` es el tamaño monetario de la posición abierta (en euros).
        """
        if amount <= 0:
            return
        if when is not None:
            self.reset_day_if_needed(when)
        self._spent_today_eur += float(amount)

    # --- Utilidades --------------------------------------------------------

    def set_limits(self, *, daily_budget_pct: Optional[float] = None, per_trade_cap_pct: Optional[float] = None) -> None:
        """
        Actualiza límites en caliente (útil para experimentos A/B).
        """
        if daily_budget_pct is not None:
            self.daily_budget_pct = float(max(0.0, daily_budget_pct))
        if per_trade_cap_pct is not None:
            self.per_trade_cap_pct = float(max(0.0, per_trade_cap_pct))

    def snapshot(self, equity: float, when: datetime) -> Dict:
        """
        Devuelve un resumen del estado interno (para logging/monitoring).
        """
        self.reset_day_if_needed(when)
        return {
            "date_utc": _ensure_utc(when).date().isoformat(),
            "daily_budget_pct": self.daily_budget_pct,
            "per_trade_cap_pct": self.per_trade_cap_pct,
            "budget_today_eur": self.budget_today_eur(equity),
            "spent_today_eur": self._spent_today_eur,
            "remaining_today_eur": self.remaining_today_eur(equity),
        }


# =========================
# Funciones puras auxiliares
# =========================

def allocate_by_confidence(
    equity: float,
    signals: List[Dict],
    *,
    daily_budget_pct: float = 0.08,
    per_trade_cap_pct: float = 0.03,
    min_allocation_eur: float = 0.0,
    allow_partial: bool = True,
) -> Dict[str, float]:
    """
    Versión funcional (pura) de asignación por confianza — útil para tests unitarios.

    Ejemplo:
        signals = [
            {"epic": "EURUSD", "confidence": 0.9},
            {"epic": "GBPUSD", "confidence": 0.6},
            {"epic": "SPX500", "confidence": 0.3},
        ]
        allocate_by_confidence(10000, signals, daily_budget_pct=0.08, per_trade_cap_pct=0.03)
        # => {'EURUSD': 300.0, 'GBPUSD': 300.0, 'SPX500': 200.0}  (si allow_partial=True)
    """
    tracker = CapitalTracker(
        initial_equity=equity,
        daily_budget_pct=daily_budget_pct,
        per_trade_cap_pct=per_trade_cap_pct,
        min_allocation_eur=min_allocation_eur,
    )
    now = datetime.now(timezone.utc)
    tracker.reset_day_if_needed(now)
    return tracker.allocate_for_signals(
        equity=equity,
        signals=signals,
        current_dt=now,
        allow_partial=allow_partial,
    )


# =========================
# Ejecución de prueba mínima
# =========================

if __name__ == "__main__":
    # Demo simple
    eq = 10000.0
    tracker = CapitalTracker(eq, daily_budget_pct=0.08, per_trade_cap_pct=0.03)
    now = datetime.now(timezone.utc)

    demo_signals = [
        {"epic": "EURUSD", "confidence": 0.82, "current_price": 1.0831},
        {"epic": "GBPUSD", "confidence": 0.67, "current_price": 1.2735},
        {"epic": "SPX500", "confidence": 0.41, "current_price": 5560.0},
        {"epic": "XAUUSD", "confidence": 0.20, "current_price": 2400.0},
    ]

    allocs = tracker.allocate_for_signals(eq, demo_signals, now)
    print("Asignaciones:", allocs)
    # Simular fills
    for epic, amt in allocs.items():
        if amt > 0:
            tracker.record_fill(epic, amt, now)

    print("Snapshot:", tracker.snapshot(eq, now))
