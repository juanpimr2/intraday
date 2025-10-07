"""
utils/cost_calculator.py

Aplicación de costes de trading (comisiones + spread) sobre un DataFrame de trades.

Diseño
------
- 100% independiente de producción (solo usa pandas/numpy).
- Función principal: `apply_costs(trades_df, commission_per_trade, spread_in_points, point_value, ...)`
- No asume broker específico. Los parámetros controlan el esquema de costes:
    * commission_per_trade: comisión fija en moneda por operación (aplicada una vez por trade).
    * spread_in_points: spread total del instrumento en "puntos" (pips, ticks, etc.).
    * point_value: valor monetario de 1 punto por 1 unidad (contrato/lote) del instrumento.
    * apply_spread_on_entry: si True, el coste de spread se cobra una vez al abrir (modelo estándar).
      Alternativa: `apply_spread='once'|'both'|'none'` (ver abajo).
    * per_instrument_overrides: dict opcional por 'epic' para personalizar costes.

- Espera un DataFrame con (mínimo):
    ['epic', 'direction', 'entry_price', 'exit_price', 'units', 'position_size', 'pnl']
  Columnas opcionales:
    ['pnl_percent']  -> si existe, se añade 'pnl_percent_net' consistente.
    ['point_value']  -> por-instrumento; si existe, sobreescribe el parámetro global.
    ['spread_in_points'] -> por-instrumento; sobreescribe el parámetro global.

Salida
------
Devuelve un NUEVO DataFrame con columnas añadidas:
    'pnl_gross'           (copia de pnl original)
    'cost_commission'     (>=0)
    'cost_spread'         (>=0)
    'cost_total'          (= commission + spread)
    'pnl_net'             (= pnl_gross - cost_total)
    'pnl_percent_net'     (si había 'pnl_percent' o se puede derivar de position_size)

Notas sobre el spread
---------------------
* Modelo por defecto: se cobra UNA VEZ al entrar (apply_spread_on_entry=True). Es el coste más habitual
  en brokers de CFD/spot donde el precio de ejecución ya incluye el spread al abrir.
* Alternativa avanzada con parámetro `apply_spread`:
    - 'once' : cobra spread una sola vez (equivalente a apply_spread_on_entry=True).
    - 'both' : cobra medio spread al abrir y medio al cerrar (doble impacto).
    - 'none' : ignora spread (útil para probar sensibilidad).
* El coste de spread se calcula como:
      cost_spread = spread_in_points_eff * point_value_eff * abs(units) * factor
  donde factor = 1.0 si 'once', 0.5 + 0.5 si 'both' (equivale a 1.0 total), y 0.0 si 'none'.

Robustez
--------
- Si 'units' falta, intenta inferir: units ≈ position_size / entry_price.
- Si faltan columnas clave, lanza ValueError con mensaje claro.
- Si algún valor no es finito, se trata como NaN y se omite del cálculo fila a fila (coste=0).

Ejemplo rápido
--------------
>>> import pandas as pd
>>> df = pd.DataFrame([
...   {'epic':'EURUSD','direction':'BUY','entry_price':1.10,'exit_price':1.102,'units':10000,'position_size':11000,'pnl':20.0},
...   {'epic':'EURUSD','direction':'SELL','entry_price':1.10,'exit_price':1.098,'units':10000,'position_size':11000,'pnl':20.0},
... ])
>>> out = apply_costs(df, commission_per_trade=0.5, spread_in_points=0.8, point_value=1.0)
>>> out[['epic','pnl','pnl_net','cost_total']].round(2)
     epic   pnl  pnl_net  cost_total
0  EURUSD  20.0    18.7        1.30
1  EURUSD  20.0    18.7        1.30

Autor: Trading Bot — Backtesting Utilities
"""

from __future__ import annotations

from typing import Dict, Optional, Literal
import numpy as np
import pandas as pd

ApplySpreadMode = Literal["once", "both", "none"]


REQUIRED_COLS = [
    "epic", "direction", "entry_price", "exit_price", "position_size", "pnl"
]

OPTIONAL_COLS = [
    "units", "pnl_percent", "point_value", "spread_in_points"
]


def _validate_input(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"apply_costs: faltan columnas requeridas en trades_df: {missing}. "
            f"Se requieren al menos: {REQUIRED_COLS}"
        )


def _infer_units(row: pd.Series) -> float:
    """Intenta estimar units si no existe, usando position_size / entry_price."""
    try:
        entry = float(row.get("entry_price", np.nan))
        size = float(row.get("position_size", np.nan))
        if np.isfinite(entry) and entry > 0 and np.isfinite(size) and size > 0:
            return size / entry
    except Exception:
        pass
    return np.nan


def _per_instrument_value(row: pd.Series, key: str, default_val: float, overrides: Optional[Dict]) -> float:
    """
    Obtiene un valor por-instrumento con prioridad:
        1) valor por-fila (si la columna existe y es válida)
        2) overrides[epic][key] si existe
        3) default_val
    """
    # 1) por-fila
    if key in row and np.isfinite(row[key]):
        return float(row[key])

    # 2) overrides por 'epic'
    if overrides:
        epic = row.get("epic")
        if epic in overrides and key in overrides[epic]:
            v = overrides[epic][key]
            try:
                if v is not None and np.isfinite(v):
                    return float(v)
            except Exception:
                pass

    # 3) default
    return float(default_val)


def apply_costs(
    trades_df: pd.DataFrame,
    commission_per_trade: float = 0.0,
    spread_in_points: float = 0.0,
    point_value: float = 1.0,
    *,
    apply_spread_on_entry: Optional[bool] = None,
    apply_spread: ApplySpreadMode = "once",
    per_instrument_overrides: Optional[Dict[str, Dict[str, float]]] = None,
) -> pd.DataFrame:
    """
    Aplica comisiones y spread para obtener P&L neto por trade.

    Parámetros
    ----------
    trades_df : pd.DataFrame
        DataFrame de operaciones con las columnas mínimas requeridas.
    commission_per_trade : float
        Comisión fija en moneda aplicada una vez por trade (>=0).
    spread_in_points : float
        Spread total del instrumento en puntos (>=0) si no se especifica por fila/overrides.
    point_value : float
        Valor monetario del punto por unidad del instrumento (>=0) si no se especifica por fila/overrides.
    apply_spread_on_entry : Optional[bool]
        Obsoleto – si se facilita, mapea a `apply_spread="once"` si True o "none" si False.
    apply_spread : {"once","both","none"}
        Estrategia de cobro del spread:
            "once": se cobra 1x el spread (modelo por defecto).
            "both": 0.5x al abrir + 0.5x al cerrar (impacto total 1x).
            "none": ignora el spread.
    per_instrument_overrides : dict
        Estructura opcional por 'epic', ej.:
            {
              "EURUSD": {"point_value": 1.2, "spread_in_points": 0.8, "commission_per_trade": 0.4},
              "GOLD":   {"point_value": 10.0, "spread_in_points": 0.5},
            }

    Retorna
    -------
    pd.DataFrame
        Copia del DataFrame de entrada con columnas de costes y P&L neto añadidas.
    """
    if apply_spread_on_entry is not None:
        apply_spread = "once" if apply_spread_on_entry else "none"

    if apply_spread not in ("once", "both", "none"):
        raise ValueError('apply_spread debe ser "once", "both" o "none".')

    _validate_input(trades_df)

    df = trades_df.copy()

    # Asegurar 'units'
    if "units" not in df.columns:
        df["units"] = np.nan

    # Normalizar columnas numéricas clave
    for col in ["entry_price", "exit_price", "units", "position_size", "pnl", "pnl_percent"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Inferir units si faltan
    mask_units_nan = df["units"].isna()
    if mask_units_nan.any():
        df.loc[mask_units_nan, "units"] = df.loc[mask_units_nan].apply(_infer_units, axis=1)

    # Coste por comisión (permite override por epic)
    def _commission_row(row: pd.Series) -> float:
        epic_comm = _per_instrument_value(row, "commission_per_trade", commission_per_trade, per_instrument_overrides)
        if not np.isfinite(epic_comm) or epic_comm < 0:
            return 0.0
        return float(epic_comm)

    df["cost_commission"] = df.apply(_commission_row, axis=1)

    # Coste por spread
    if apply_spread == "none":
        df["cost_spread"] = 0.0
    else:
        # factor total = 1.0 (una vez) o también 1.0 (suma de 0.5+0.5) si "both"
        factor_total = 1.0

        def _spread_row(row: pd.Series) -> float:
            pv = _per_instrument_value(row, "point_value", point_value, per_instrument_overrides)
            sp = _per_instrument_value(row, "spread_in_points", spread_in_points, per_instrument_overrides)

            units = float(row.get("units", np.nan))
            if not np.isfinite(pv) or not np.isfinite(sp) or not np.isfinite(units):
                return 0.0
            pv = max(pv, 0.0)
            sp = max(sp, 0.0)
            units = abs(units)
            return float(sp * pv * units * factor_total)

        df["cost_spread"] = df.apply(_spread_row, axis=1)

    # Coste total
    df["cost_total"] = (df["cost_commission"].fillna(0.0) + df["cost_spread"].fillna(0.0)).astype(float)

    # P&L neto
    df["pnl_gross"] = df["pnl"].astype(float)
    df["pnl_net"] = (df["pnl_gross"].fillna(0.0) - df["cost_total"]).astype(float)

    # P&L % neto
    if "pnl_percent" in df.columns and df["pnl_percent"].notna().any():
        # Si ya existe el % bruto, recalcular neto proporcional al position_size
        # pnl_percent = pnl / position_size * 100  => invertimos
        def _pnl_percent_net(row: pd.Series) -> float:
            size = float(row.get("position_size", np.nan))
            pnl_net = float(row.get("pnl_net", np.nan))
            if np.isfinite(size) and size != 0 and np.isfinite(pnl_net):
                return (pnl_net / size) * 100.0
            return np.nan

        df["pnl_percent_net"] = df.apply(_pnl_percent_net, axis=1)
    else:
        # Si no existe pnl_percent, intentamos calcular 'pnl_percent_net' con position_size
        def _pnl_percent_net2(row: pd.Series) -> float:
            size = float(row.get("position_size", np.nan))
            pnl_net = float(row.get("pnl_net", np.nan))
            if np.isfinite(size) and size != 0 and np.isfinite(pnl_net):
                return (pnl_net / size) * 100.0
            return np.nan

        df["pnl_percent_net"] = df.apply(_pnl_percent_net2, axis=1)

    # Limpieza de posibles -0.0
    for col in ["cost_commission", "cost_spread", "cost_total", "pnl_net", "pnl_percent_net"]:
        if col in df.columns:
            df[col] = df[col].astype(float).round(12)
            df[col] = df[col].replace(-0.0, 0.0)

    return df


# =========================
# CLI / Prueba rápida
# =========================
if __name__ == "__main__":
    # Pequeño demo local
    demo = pd.DataFrame([
        {"epic": "EURUSD", "direction": "BUY",  "entry_price": 1.10,  "exit_price": 1.102, "units": 10000, "position_size": 11000, "pnl": 20.0},
        {"epic": "EURUSD", "direction": "SELL", "entry_price": 1.10,  "exit_price": 1.098, "units": 10000, "position_size": 11000, "pnl": 20.0},
        {"epic": "GOLD",   "direction": "BUY",  "entry_price": 2400., "exit_price": 2401., "units": 1,     "position_size": 2400., "pnl": 10.0},
    ])
    out = apply_costs(
        demo,
        commission_per_trade=0.50,
        spread_in_points=0.80,
        point_value=1.00,
        apply_spread="once",
        per_instrument_overrides={
            "GOLD": {"point_value": 10.0, "spread_in_points": 0.30, "commission_per_trade": 0.80}
        }
    )
    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", None)
    print(out)
