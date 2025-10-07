# backtesting/run_backtest.py
"""
CLI de backtesting unificado.

Características:
- Soporta --data-source csv|api (con fallback: si no hay loader externo, se usa un lector CSV básico).
- Ejecuta BacktestEngine y exporta SIEMPRE a reports/run_<timestamp>/:
    - trades.csv
    - equity.csv        (NUEVO)
    - metrics.json
    - backtest_REPORT.md (resumen del run)
- Mantiene/actualiza un reporte incremental global en reports/backtest_REPORT.md
  con tablas por: métricas generales, por régimen (trending/lateral) y por sesión (EU/US).

Uso típico:
    python -m backtesting.run_backtest --data-source csv --csv-dir ./data/csv
    python -m backtesting.run_backtest --data-source api --from 2025-06-01 --to 2025-10-01
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

# Motor y export helpers
from backtesting.backtest_engine import (
    BacktestEngine,
    export_results_to_csv,
    export_summary_to_json,
    export_equity_to_csv,
)

# Configuración de logging sobria para CLI
logging.basicConfig(
    level=os.getenv("BACKTEST_LOGLEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------------------
# Carga de datos (flexible):
#   - Si existe un loader del proyecto, se usa.
#   - Si no, fallback lector CSV de carpeta: espera archivos <EPIC>.csv con columnas standard.
# --------------------------------------------------------------------------------------------------
def load_historical_data_flexible(
    source: str,
    csv_dir: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Devuelve un dict {epic: DataFrame} con al menos:
        snapshotTime (datetime), open/high/low/close (o openPrice/.../closePrice), volume (opcional)
    """
    source = (source or "csv").lower()

    # 1) Intento: loader del repo (si existe)
    try:
        # Ejemplos aceptados en proyectos similares:
        # - from backtesting.data_loader import load_historical_data
        # - from data.loaders import load_historical_data
        # - from loaders import load_historical_data
        for candidate in (
            "backtesting.data_loader",
            "data.loaders",
            "loaders",
        ):
            mod = __import__(candidate, fromlist=["load_historical_data"])
            if hasattr(mod, "load_historical_data"):
                logger.info(f"Usando loader externo: {candidate}.load_historical_data(...)")
                return mod.load_historical_data(source=source, csv_dir=csv_dir, date_from=date_from, date_to=date_to)
    except Exception as e:
        logger.debug(f"No se encontró/ejecutó loader externo: {e}")

    # 2) Fallback propio:
    if source == "csv":
        if not csv_dir:
            raise ValueError("--csv-dir es obligatorio cuando --data-source=csv sin loader externo")
        return _load_from_csv_dir(csv_dir, date_from, date_to)

    elif source == "api":
        # Permitimos que proyectos con API propia reemplacen este bloque.
        # Aquí dejamos un mensaje claro para guiar integración.
        raise NotImplementedError(
            "Carga desde API no implementada en fallback.\n"
            "Sugerencia: provee un módulo 'backtesting.data_loader' con 'load_historical_data(...)' "
            "o ejecuta con --data-source csv."
        )

    else:
        raise ValueError(f"data-source no reconocido: {source}")


def _load_from_csv_dir(csv_dir: str, date_from: Optional[str], date_to: Optional[str]) -> Dict[str, pd.DataFrame]:
    csv_path = Path(csv_dir)
    if not csv_path.exists():
        raise FileNotFoundError(f"Directorio CSV no existe: {csv_dir}")

    out: Dict[str, pd.DataFrame] = {}

    for f in sorted(csv_path.glob("*.csv")):
        epic = f.stem  # nombre del archivo sin extensión como EPIC
        try:
            df = pd.read_csv(f)
        except Exception as e:
            logger.warning(f"Saltando {f.name}: error de lectura CSV ({e})")
            continue

        # Normalización mínima de columnas
        cols = {c.lower(): c for c in df.columns}
        # Buscar columna de tiempo
        time_col = None
        for cand in ("snapshotTime", "timestamp", "time", "datetime", "date"):
            if cand in df.columns:
                time_col = cand
                break
            if cand.lower() in cols:
                time_col = cols[cand.lower()]
                break
        if time_col is None:
            logger.warning(f"{f.name}: no se encuentra columna temporal (snapshotTime/timestamp/...)")
            continue

        df = df.rename(columns={time_col: "snapshotTime"})
        # Intentamos mapear OHLC
        rename_map = {}
        if "open" in df.columns and "openPrice" not in df.columns:
            rename_map["open"] = "openPrice"
        if "high" in df.columns and "highPrice" not in df.columns:
            rename_map["high"] = "highPrice"
        if "low" in df.columns and "lowPrice" not in df.columns:
            rename_map["low"] = "lowPrice"
        if "close" in df.columns and "closePrice" not in df.columns:
            rename_map["close"] = "closePrice"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Tipos
        df["snapshotTime"] = pd.to_datetime(df["snapshotTime"], utc=True, errors="coerce")
        for c in ("openPrice", "highPrice", "lowPrice", "closePrice", "volume"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # Filtro de fechas si aplica
        if date_from:
            start = pd.to_datetime(date_from, utc=True)
            df = df[df["snapshotTime"] >= start]
        if date_to:
            end = pd.to_datetime(date_to, utc=True)
            df = df[df["snapshotTime"] <= end]

        df = df.dropna(subset=["snapshotTime", "closePrice"]).sort_values("snapshotTime").reset_index(drop=True)
        if df.empty:
            logger.warning(f"{f.name}: sin datos válidos tras limpieza")
            continue

        out[epic] = df

    if not out:
        raise RuntimeError(f"No se cargaron activos desde {csv_dir}. ¿Extensiones/columnas correctas?")
    logger.info(f"Cargados {len(out)} activos desde {csv_dir}: {', '.join(out.keys())}")
    return out


# --------------------------------------------------------------------------------------------------
# Reportería
# --------------------------------------------------------------------------------------------------
def _ensure_run_dir(engine: BacktestEngine) -> Path:
    # el motor crea la carpeta run_<ts>; la tomamos desde el último export o de la curva guardada
    # aquí simplemente inferimos del equity.csv si ya se exportó o, en su defecto, del timestamp actual
    # (pero export_* ya establecen un directorio común y lo retornan)
    now_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = Path("reports") / f"run_{now_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_run_markdown(results_dict: dict, run_dir: Path) -> Path:
    """
    Crea un Markdown **solo de este run** dentro de run_dir/backtest_REPORT.md con:
    - Resumen general
    - Tabla por régimen
    - Tabla por sesión (EU/US)
    """
    md_path = run_dir / "backtest_REPORT.md"
    ts_label = run_dir.name.replace("run_", "")

    # Tablas auxiliares
    def tbl_metrics(d: dict) -> str:
        return (
            "| Métrica | Valor |\n"
            "|---|---:|\n"
            f"| Capital inicial | {d['capital']['initial']:.2f} |\n"
            f"| Capital final | {d['capital']['final']:.2f} |\n"
            f"| Retorno total (€) | {d['capital']['total_return']:.2f} |\n"
            f"| Retorno total (%) | {d['capital']['total_return_percent']:.2f}% |\n"
            f"| CAGR (%) | {d['capital']['cagr']:.2f}% |\n"
            f"| Trades | {d['trades']['total']} |\n"
            f"| Win rate | {d['trades']['win_rate']:.2f}% |\n"
            f"| Profit Factor | {d['trades']['profit_factor']:.2f} |\n"
            f"| Max Drawdown | {d['risk']['max_drawdown']:.2f}% |\n"
            f"| Sharpe | {d['risk']['sharpe_ratio']:.2f} |\n"
            f"| Sortino | {d['risk']['sortino_ratio']:.2f} |\n"
            f"| Volatilidad anualizada | {d['risk']['volatility']:.2f}% |\n"
        )

    def tbl_regime(d: dict) -> str:
        reg = d.get("temporal", {}).get("by_regime", {})
        if not reg:
            return "_Sin datos de régimen para este run._\n"
        lines = ["| Régimen | Trades | Win% | PF | PnL (€) |", "|---|---:|---:|---:|---:|"]
        for k, v in reg.items():
            lines.append(f"| {k} | {v.get('total_trades',0)} | {v.get('win_rate',0.0):.2f}% | {v.get('profit_factor',0.0):.2f} | {v.get('total_pnl',0.0):.2f} |")
        return "\n".join(lines) + "\n"

    def tbl_session(d: dict) -> str:
        ses = d.get("temporal", {}).get("by_session", {})
        if not ses:
            return "_Sin datos por sesión para este run._\n"
        lines = ["| Sesión | Trades | Win% | PF | PnL (€) |", "|---|---:|---:|---:|---:|"]
        order = ["eu_open", "eu_pm", "us_open", "us_pm"]
        for k in order:
            if k in ses:
                v = ses[k]
                lines.append(f"| {k} | {v.get('total_trades',0)} | {v.get('win_rate',0.0):.2f}% | {v.get('profit_factor',0.0):.2f} | {v.get('total_pnl',0.0):.2f} |")
        # incluir sesiones no listadas en order (si existieran)
        for k, v in ses.items():
            if k not in order:
                lines.append(f"| {k} | {v.get('total_trades',0)} | {v.get('win_rate',0.0):.2f}% | {v.get('profit_factor',0.0):.2f} | {v.get('total_pnl',0.0):.2f} |")
        return "\n".join(lines) + "\n"

    content = []
    content.append(f"# Backtest {ts_label}\n")
    content.append("## Resumen general\n")
    content.append(tbl_metrics(results_dict))
    content.append("\n## Por régimen (trending / lateral)\n")
    content.append(tbl_regime(results_dict))
    content.append("\n## Por sesión (EU/US)\n")
    content.append(tbl_session(results_dict))
    content.append("\n> Archivos de este run: `trades.csv`, `equity.csv`, `metrics.json`.\n")

    md = "\n".join(content).strip() + "\n"
    md_path.write_text(md, encoding="utf-8")
    logger.info(f"📝 Reporte del run escrito en {md_path.as_posix()}")
    return md_path


def _append_global_markdown(run_md_path: Path, global_md_path: Path) -> None:
    """
    Inserta el contenido del run al final del reporte global (creándolo si no existe).
    Se separa cada run con una regla horizontal.
    """
    run_txt = run_md_path.read_text(encoding="utf-8")
    sep = "\n\n---\n\n"
    if global_md_path.exists():
        prev = global_md_path.read_text(encoding="utf-8")
        global_md_path.write_text(prev + sep + run_txt, encoding="utf-8")
    else:
        header = "# Backtesting REPORT (incremental)\n\n"
        global_md_path.write_text(header + run_txt, encoding="utf-8")
    logger.info(f"📚 Reporte incremental actualizado: {global_md_path.as_posix()}")


# --------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ejecutor de backtesting unificado")
    p.add_argument("--data-source", choices=["csv", "api"], default="csv")
    p.add_argument("--csv-dir", type=str, default=None, help="Directorio con CSV (uno por EPIC)")
    p.add_argument("--from", dest="date_from", type=str, default=None, help="Fecha inicio (YYYY-MM-DD)")
    p.add_argument("--to", dest="date_to", type=str, default=None, help="Fecha fin (YYYY-MM-DD)")
    p.add_argument("--initial-capital", type=float, default=10_000.0, help="Capital inicial en EUR")
    return p.parse_args()


def main():
    args = parse_args()

    # 1) Cargar datos
    data = load_historical_data_flexible(
        source=args.data_source,
        csv_dir=args.csv_dir,
        date_from=args.date_from,
        date_to=args.date_to,
    )

    # 2) Ejecutar motor
    engine = BacktestEngine(initial_capital=args.initial_capital)
    results = engine.run(
        historical_data=data,
        start_date=args.date_from,
        end_date=args.date_to,
    )

    # 3) Exportar resultados mínimos requeridos
    #    (cada export devuelve la ruta escrita, y fija un directorio de run consistente)
    run_dir = Path(export_results_to_csv(results, filename="trades.csv")).parent
    export_equity_to_csv(results, filename="equity.csv", report_dir=run_dir)  # NUEVO
    metrics_path = export_summary_to_json(results, filename="metrics.json", report_dir=run_dir)

    # 4) Escribir/actualizar reportes Markdown
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics_dict = json.load(f)

    run_md_path = _write_run_markdown(metrics_dict, run_dir)
    global_md_path = Path("reports") / "backtest_REPORT.md"
    _append_global_markdown(run_md_path, global_md_path)

    # 5) Log final resumido
    logger.info(
        "✅ Backtest finalizado | Carpeta: %s | Trades: %s | PF: %.2f | WinRate: %.2f%% | MaxDD: %.2f%%",
        run_dir.name,
        metrics_dict["trades"]["total"],
        metrics_dict["trades"]["profit_factor"],
        metrics_dict["trades"]["win_rate"],
        metrics_dict["risk"]["max_drawdown"],
    )


if __name__ == "__main__":
    main()
