# trading/db.py
"""
Persistencia simple de trades y equity en SQLite (listo para DEMO 1 semana).

- Sin dependencias externas (usa sqlite3 de la stdlib).
- Archivo por defecto: ./data/trades.sqlite3 (configurable via env TRADES_DB_PATH).
- Tablas:
    trades(id, epic, side, entry_ts, exit_ts, entry_price, exit_price, size_eur,
           units, pnl, pnl_pct, reason, confidence, regime, duration_hours, created_at)
    equity_points(id, ts_utc, equity, cash, open_positions, created_at)
- Índices optimizados para filtrado básico (fecha/epic).
- Modo WAL para mejor durabilidad en ejecución continua.

Uso típico (en vivo):
    from trading.db import DB
    db = DB()  # crea/abre ./data/trades.sqlite3, asegura tablas

    # guardar un trade cuando se cierra:
    db.save_trade(
        epic="DE40", side="BUY",
        entry_ts=entry_dt_utc, exit_ts=exit_dt_utc,
        entry_price=15800.5, exit_price=15850.0,
        size_eur=300.0, units=0.01897,
        pnl=+12.35, pnl_pct=+4.11,
        reason="TAKE_PROFIT", confidence=0.78, regime="trending",
        duration_hours=5.0
    )

    # guardar un punto de equity (puedes registrar cada X minutos u on_bar):
    db.save_equity_point(ts_utc=now_utc, equity=10125.3, cash=9860.1, open_positions=1)

    # leer últimos N trades (para dashboard, export rápido):
    rows = db.get_latest_trades(limit=50)
    # rows -> List[dict]

Notas:
- Todas las fechas deben ser "aware UTC" (datetime con tz UTC) o ISO-8601 UTC. Si pasas naive, se asume UTC.
- Seguro ante tipos: convierte a float/str según corresponda.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _to_utc_iso(dt: Any) -> str:
    """
    Normaliza un datetime a ISO-8601 UTC (Z). Acepta:
      - datetime tz-aware → convierte a UTC
      - datetime naive     → asume UTC
      - str                → devuelve tal cual (se recomienda ISO-8601)
    """
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    if isinstance(dt, (int, float)):
        # soporta epoch segundos (no recomendado, pero útil)
        return datetime.fromtimestamp(float(dt), tz=timezone.utc).isoformat().replace("+00:00", "Z")
    # asume str ISO ya correcto
    return str(dt)


def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


@dataclass
class DBConfig:
    db_path: str = os.getenv("TRADES_DB_PATH", "data/trades.sqlite3")
    pragmas: Iterable[str] = (
        "PRAGMA journal_mode=WAL;",
        "PRAGMA synchronous=NORMAL;",
        "PRAGMA foreign_keys=ON;",
    )


class DB:
    def __init__(self, config: Optional[DBConfig] = None) -> None:
        self.config = config or DBConfig()
        self._ensure_dir()
        self._conn = sqlite3.connect(self.config.db_path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._apply_pragmas()
        self._create_tables()

    # ---------- infra ----------
    def _ensure_dir(self) -> None:
        p = Path(self.config.db_path)
        p.parent.mkdir(parents=True, exist_ok=True)

    def _apply_pragmas(self) -> None:
        cur = self._conn.cursor()
        for stmt in self.config.pragmas:
            cur.execute(stmt)
        cur.close()

    def _create_tables(self) -> None:
        cur = self._conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              epic TEXT NOT NULL,
              side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
              entry_ts TEXT NOT NULL,
              exit_ts  TEXT NOT NULL,
              entry_price REAL NOT NULL,
              exit_price  REAL NOT NULL,
              size_eur  REAL NOT NULL,
              units     REAL NOT NULL,
              pnl       REAL NOT NULL,
              pnl_pct   REAL NOT NULL,
              reason    TEXT NOT NULL,
              confidence REAL NOT NULL,
              regime     TEXT NOT NULL,
              duration_hours REAL NOT NULL,
              created_at  TEXT NOT NULL DEFAULT (DATETIME('now'))
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS ix_trades_exit_ts ON trades(exit_ts);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_trades_epic ON trades(epic);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_trades_reason ON trades(reason);")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS equity_points (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts_utc TEXT NOT NULL,
              equity REAL NOT NULL,
              cash REAL NOT NULL,
              open_positions INTEGER NOT NULL,
              created_at TEXT NOT NULL DEFAULT (DATETIME('now'))
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS ix_equity_ts ON equity_points(ts_utc);")

        self._conn.commit()
        cur.close()

    # ---------- API pública ----------
    def save_trade(
        self,
        *,
        epic: str,
        side: str,
        entry_ts: Any,
        exit_ts: Any,
        entry_price: Any,
        exit_price: Any,
        size_eur: Any,
        units: Any,
        pnl: Any,
        pnl_pct: Any,
        reason: str,
        confidence: Any,
        regime: str = "lateral",
        duration_hours: Any = 0.0,
    ) -> int:
        """
        Inserta un trade cerrado. Devuelve id de fila.
        """
        row = {
            "epic": str(epic),
            "side": "BUY" if str(side).upper().startswith("B") else "SELL",
            "entry_ts": _to_utc_iso(entry_ts),
            "exit_ts": _to_utc_iso(exit_ts),
            "entry_price": _to_float(entry_price),
            "exit_price": _to_float(exit_price),
            "size_eur": _to_float(size_eur),
            "units": _to_float(units),
            "pnl": _to_float(pnl),
            "pnl_pct": _to_float(pnl_pct),
            "reason": str(reason),
            "confidence": _to_float(confidence),
            "regime": str(regime),
            "duration_hours": _to_float(duration_hours),
        }
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO trades
              (epic, side, entry_ts, exit_ts, entry_price, exit_price, size_eur, units,
               pnl, pnl_pct, reason, confidence, regime, duration_hours)
            VALUES
              (:epic, :side, :entry_ts, :exit_ts, :entry_price, :exit_price, :size_eur, :units,
               :pnl, :pnl_pct, :reason, :confidence, :regime, :duration_hours)
            """,
            row,
        )
        self._conn.commit()
        last_id = int(cur.lastrowid)
        cur.close()
        return last_id

    def save_equity_point(self, *, ts_utc: Any, equity: Any, cash: Any, open_positions: Any) -> int:
        """
        Inserta un punto de equity/cash/open_positions en UTC.
        """
        row = {
            "ts_utc": _to_utc_iso(ts_utc),
            "equity": _to_float(equity),
            "cash": _to_float(cash),
            "open_positions": int(open_positions),
        }
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO equity_points (ts_utc, equity, cash, open_positions)
            VALUES (:ts_utc, :equity, :cash, :open_positions)
            """,
            row,
        )
        self._conn.commit()
        last_id = int(cur.lastrowid)
        cur.close()
        return last_id

    def get_latest_trades(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            f"""
            SELECT id, epic, side, entry_ts, exit_ts, entry_price, exit_price, size_eur, units,
                   pnl, pnl_pct, reason, confidence, regime, duration_hours, created_at
            FROM trades
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def get_equity_series(self, *, limit: int = 1000) -> List[Dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT id, ts_utc, equity, cash, open_positions, created_at
            FROM equity_points
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# ---------------------------- CLI de prueba (opcional) ----------------------------
if __name__ == "__main__":
    # Pequeño smoke que no toca el resto del proyecto:
    db = DB()
    now = datetime.now(timezone.utc)
    # Equity dummy
    db.save_equity_point(ts_utc=now, equity=10_000.0, cash=10_000.0, open_positions=0)
    # Trade dummy
    db.save_trade(
        epic="SMOKE.EPIC", side="BUY",
        entry_ts=now, exit_ts=now,
        entry_price=100.0, exit_price=101.0,
        size_eur=300.0, units=3.0,
        pnl=+3.0, pnl_pct=+1.0,
        reason="END_OF_BACKTEST", confidence=0.99, regime="trending",
        duration_hours=0.0,
    )
    print(f"OK — DB en {Path(DBConfig().db_path).resolve().as_posix()}")
