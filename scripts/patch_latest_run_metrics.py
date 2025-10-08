import json
import math
import pathlib
import pandas as pd

# Usa config para point_value y costes
try:
    from config import Config
except Exception:
    class _Dummy: pass
    Config=_Dummy()
    Config.POINT_VALUE_DEFAULT=1.0
    Config.SPREAD_IN_POINTS_DEFAULT=0.0
    Config.COMMISSION_PER_TRADE=0.0
    Config.COST_OVERRIDES={"GOLD":{"point_value":10.0,"spread_points":0.3,"commission":0.8}}

def point_value_for(epic:str)->float:
    ov=getattr(Config,"COST_OVERRIDES",{}) or {}
    x=ov.get(str(epic),{})
    return float(x.get("point_value", getattr(Config,"POINT_VALUE_DEFAULT",1.0)))

def costs_for(epic:str, units:float)->float:
    ov=getattr(Config,"COST_OVERRIDES",{}) or {}
    x=ov.get(str(epic),{})
    spread_pts = float(x.get("spread_points", getattr(Config,"SPREAD_IN_POINTS_DEFAULT",0.0)))
    commission = float(x.get("commission", getattr(Config,"COMMISSION_PER_TRADE",0.0)))
    # coste aprox (spread unidireccional + comisión fija)
    return commission + spread_pts * point_value_for(epic) * float(units)

def side_col(df):
    for c in ("side","direction","Side","Direction"):
        if c in df.columns: return c
    raise KeyError("No se encontró columna 'side/direction'")

def price_cols(df):
    for a,b in (("entry_price","exit_price"),("entry","exit"),("price_entry","price_exit")):
        if a in df.columns and b in df.columns:
            return a,b
    raise KeyError("No se encontraron columnas de precios (entry/exit)")

def units_col(df):
    for c in ("units","size_units","size"):
        if c in df.columns: return c
    raise KeyError("No se encontró columna 'units/size'")

def safe_pf(vals):
    profits = vals[vals>0].sum()
    losses  = -vals[vals<0].sum()
    return (float("inf") if losses==0 else float(profits/losses), float(profits), float(losses))

def clamp_series(s, cap=1e7):
    s = s.copy()
    s[(s.abs()>cap)] = pd.NA
    return s

# --- cargar último run
run = sorted(pathlib.Path("reports").glob("run_*"))[-1]
trades_path = run/"trades.csv"
df = pd.read_csv(trades_path)

# columnas básicas
c_side = side_col(df)
c_e, c_x = price_cols(df)
c_u = units_col(df)
c_epic = "epic" if "epic" in df.columns else None

# signo por lado
sign = df[c_side].astype(str).str.upper().map(lambda x: 1.0 if x.startswith("B") else -1.0)

# point_value por fila
if c_epic:
    pv = df[c_epic].map(point_value_for).astype(float)
else:
    pv = pd.Series([getattr(Config,"POINT_VALUE_DEFAULT",1.0)]*len(df))

# pnl estimado (sin costes)
delta = (df[c_x].astype(float) - df[c_e].astype(float)) * sign
units = df[c_u].astype(float)
pnl_est = delta * units * pv

# costes aproximados por trade
if c_epic:
    cost = df.apply(lambda r: costs_for(r[c_epic], float(r[c_u])), axis=1).astype(float)
else:
    cost = pd.Series([0.0]*len(df))

# PnL reparado (resta coste con el mismo signo del trade; coste siempre reduce)
pnl_patched = pnl_est - cost

# proteger contra outliers absurdos
pnl_patched = clamp_series(pnl_patched, cap=1e6).fillna(0.0)

# escribir trades_patched.csv
df_out = df.copy()
df_out["pnl_patched"] = pnl_patched
df_out.to_csv(run/"trades_patched.csv", index=False)

# PFs
pf_global, prof_g, loss_g = safe_pf(pnl_patched)
lines = [f"PF global (patched): {pf_global:.2f} | profits={prof_g:.2f} | losses={loss_g:.2f}"]

# por régimen
if "regime" in df_out.columns:
    for k,g in df_out.groupby("regime"):
        pfk, pk, lk = safe_pf(g["pnl_patched"])
        lines.append(f"PF regime {k}: {pfk:.2f} | profits={pk:.2f} | losses={lk:.2f}")

# por sesión
if "session" in df_out.columns:
    for k,g in df_out.groupby("session"):
        pfk, pk, lk = safe_pf(g["pnl_patched"])
        lines.append(f"PF session {k}: {pfk:.2f} | profits={pk:.2f} | losses={lk:.2f}")

# actualizar metrics_patched.json (no tocamos el original)
metrics_path = run/"metrics.json"
try:
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
except Exception:
    metrics = {}

metrics.setdefault("patched", {})
metrics["patched"]["pnl_field"] = "pnl_patched"
metrics["patched"]["profit_factor"] = pf_global
metrics["patched"]["profits"] = prof_g
metrics["patched"]["losses"] = loss_g

# por régimen
if "regime" in df_out.columns:
    reg = {}
    for k,g in df_out.groupby("regime"):
        pfk, pk, lk = safe_pf(g["pnl_patched"])
        reg[k] = {"profit_factor": float(pfk), "profits": float(pk), "losses": float(lk)}
    metrics["patched"]["by_regime"] = reg

# por sesión
if "session" in df_out.columns:
    ses = {}
    for k,g in df_out.groupby("session"):
        pfk, pk, lk = safe_pf(g["pnl_patched"])
        ses[k] = {"profit_factor": float(pfk), "profits": float(pk), "losses": float(lk)}
    metrics["patched"]["by_session"] = ses

(run/"metrics_patched.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"[OK] Escrito: {run/'trades_patched.csv'}")
print(f"[OK] Escrito: {run/'metrics_patched.json'}")
print(*lines, sep="\n")
