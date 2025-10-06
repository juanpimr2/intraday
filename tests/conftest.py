# tests/conftest.py
import io
import os
import csv
import json
import random
import string
import datetime as dt
from typing import List, Dict, Any, Optional

import pytest


# ============================================================
# Utilidades de generación de datos
# ============================================================

def _rand_id(prefix: str = "") -> str:
    base = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}{base}" if prefix else base


def generate_trades(n: int = 10, *, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Genera trades con un esquema flexible (incluye 'size')."""
    trades = []
    base_session = session_id if session_id is not None else 1
    now = dt.datetime.utcnow()
    for i in range(n):
        trades.append({
            "id": i + 1,
            "session_id": base_session,
            "timestamp": (now - dt.timedelta(minutes=5 * i)).isoformat() + "Z",
            "epic": random.choice(["GOLD", "EURUSD", "SP500", "BTCUSD"]),
            "direction": random.choice(["BUY", "SELL"]),
            "price_open": round(random.uniform(100, 200), 2),
            "price_close": round(random.uniform(100, 200), 2),
            "pnl": round(random.uniform(-50, 80), 2),
            "size": round(random.uniform(0.1, 5.0), 2),
            "strategy": random.choice(["mean_rev", "breakout", "trend_follow"]),
            "notes": f"auto-{_rand_id()}",
        })
    trades.sort(key=lambda t: t["timestamp"], reverse=True)
    return trades


def generate_signals(n: int = 8) -> List[Dict[str, Any]]:
    """Genera señales recientes (incluye 'signal_type')."""
    now = dt.datetime.utcnow()
    signals = []
    for i in range(n):
        signals.append({
            "id": i + 1,
            "timestamp": (now - dt.timedelta(minutes=3 * i)).isoformat() + "Z",
            "epic": random.choice(["GOLD", "EURUSD", "SP500", "BTCUSD"]),
            "value": round(random.uniform(-2, 2), 4),
            "signal_type": random.choice(["entry", "exit", "hold"]),
            "strength": random.choice(["low", "medium", "high"]),
        })
    signals.sort(key=lambda s: s["timestamp"], reverse=True)
    return signals


def generate_sessions(n: int = 3) -> List[Dict[str, Any]]:
    now = dt.datetime.utcnow()
    sessions = []
    for i in range(n):
        sid = i + 1
        start = now - dt.timedelta(hours=3 * (i + 1))
        end = start + dt.timedelta(hours=2, minutes=30)
        sessions.append({
            "session_id": sid,
            "name": f"Session {sid}",
            "started_at": start.isoformat() + "Z",
            "ended_at": end.isoformat() + "Z",
            "status": "finished",
            "summary": {
                "total_trades": random.randint(5, 20),
                "win_rate": round(random.uniform(0.3, 0.8), 2),
                "gross_pnl": round(random.uniform(-200, 500), 2),
            }
        })
    return sessions


def compute_trades_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {
            "count": 0,
            "gross_pnl": 0.0,
            "avg_pnl": 0.0,
            "win_rate": 0.0,
            "by_epic": {},
            "by_direction": {},
        }
    count = len(trades)
    gross = sum(t.get("pnl", 0.0) for t in trades)
    wins = sum(1 for t in trades if t.get("pnl", 0.0) > 0)
    by_epic: Dict[str, float] = {}
    by_dir: Dict[str, float] = {}
    for t in trades:
        by_epic[t["epic"]] = by_epic.get(t["epic"], 0.0) + t.get("pnl", 0.0)
        by_dir[t["direction"]] = by_dir.get(t["direction"], 0.0) + t.get("pnl", 0.0)
    return {
        "count": count,
        "gross_pnl": round(gross, 2),
        "avg_pnl": round(gross / count, 2),
        "win_rate": round(wins / count, 2),
        "by_epic": by_epic,
        "by_direction": by_dir,
    }


# ============================================================
# Fake Database Manager (datos en memoria)
# ============================================================

class FakeDatabaseManager:
    def __init__(self, trades=None, signals=None, sessions=None):
        self._trades = list(trades or [])
        self._signals = list(signals or [])
        self._sessions = list(sessions or [])

    # CRUD / Lectura
    def save_trade(self, payload: Dict[str, Any]) -> int:
        new_id = (max([t["id"] for t in self._trades], default=0) + 1)
        item = {"id": new_id, **payload}
        item.setdefault("size", 1.0)
        item.setdefault("timestamp", dt.datetime.utcnow().isoformat() + "Z")
        self._trades.insert(0, item)
        return new_id

    def get_trades_history(self, *, limit: Optional[int] = None, session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        data = self._trades
        if session_id is not None:
            data = [t for t in data if t.get("session_id") == session_id]
        if limit is not None:
            try:
                limit = int(limit)
            except Exception:
                limit = None
        if limit is not None:
            data = data[:max(0, limit)]
        return data

    def get_trades_stats(self, *, session_id: Optional[int] = None) -> Dict[str, Any]:
        data = self.get_trades_history(session_id=session_id)
        return compute_trades_stats(data)

    def get_signals_recent(self, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        data = self._signals
        if limit is not None:
            try:
                limit = int(limit)
            except Exception:
                limit = None
        if limit is not None:
            data = data[:max(0, limit)]
        return data

    def get_sessions(self) -> List[Dict[str, Any]]:
        return self._sessions

    def get_session_detail(self, session_id: int) -> Dict[str, Any]:
        for s in self._sessions:
            if s["session_id"] == session_id:
                trades = self.get_trades_history(session_id=session_id)
                return {
                    **s,
                    "trades": trades,
                    "stats": compute_trades_stats(trades),
                }
        return {}

    # Exportaciones simuladas
    def export_trades_csv(self, *, session_id: Optional[int] = None) -> bytes:
        trades = self.get_trades_history(session_id=session_id)
        fieldnames = sorted({k for t in trades for k in t.keys()} | {"id", "session_id", "epic", "direction", "pnl", "size", "timestamp"})
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for row in trades:
            writer.writerow({k: row.get(k) for k in fieldnames})
        return buf.getvalue().encode("utf-8")

    def export_trades_excel(self, *, session_id: Optional[int] = None) -> bytes:
        return self.export_trades_csv(session_id=session_id)

    def export_full_report(self) -> bytes:
        payload = {
            "generated_at": dt.datetime.utcnow().isoformat() + "Z",
            "trades_count": len(self._trades),
            "signals_count": len(self._signals),
            "sessions_count": len(self._sessions),
            "stats_overall": compute_trades_stats(self._trades),
        }
        return json.dumps(payload, indent=2).encode("utf-8")


# ============================================================
# Fixtures de datos base
# ============================================================

@pytest.fixture(scope="session")
def base_trades_data() -> List[Dict[str, Any]]:
    return generate_trades(16, session_id=1) + generate_trades(9, session_id=2)


@pytest.fixture(scope="session")
def base_signals_data() -> List[Dict[str, Any]]:
    return generate_signals(12)


@pytest.fixture(scope="session")
def base_sessions_data() -> List[Dict[str, Any]]:
    return generate_sessions(4)


# ============================================================
# Fixture DB falsa compartida
# ============================================================

@pytest.fixture
def patch_db_manager(monkeypatch, base_trades_data, base_signals_data, base_sessions_data):
    """
    Creamos la Fake DB y registramos alias suaves por compatibilidad.
    El bloqueo real de la BD lo haremos a nivel WSGI en flask_client.
    """
    fake_db_instance = FakeDatabaseManager(
        trades=[*base_trades_data], signals=[*base_signals_data], sessions=[*base_sessions_data]
    )

    def _factory(*args, **kwargs):
        return fake_db_instance

    import importlib

    # Alias en database.connection (si existen)
    try:
        db_conn = importlib.import_module("database.connection")
        for name in ("DatabaseManager", "Database", "get_db_manager", "get_db"):
            monkeypatch.setattr(db_conn, name, _factory, raising=False)
        monkeypatch.setattr(db_conn, "get_connection", lambda *a, **k: fake_db_instance, raising=False)
        monkeypatch.setattr(db_conn, "connect", lambda *a, **k: fake_db_instance, raising=False)
        monkeypatch.setattr(db_conn, "db_manager", fake_db_instance, raising=False)
        for name in ("execute_query", "execute_read_query", "query", "run_query", "query_db"):
            monkeypatch.setattr(db_conn, name, lambda *a, **k: None, raising=False)
    except Exception:
        pass

    # Alias en database.queries.analytics
    try:
        analytics = importlib.import_module("database.queries.analytics")
        monkeypatch.setattr(analytics, "get_trades_history", lambda **kw: fake_db_instance.get_trades_history(**kw), raising=False)
        monkeypatch.setattr(analytics, "get_trades_stats", lambda **kw: fake_db_instance.get_trades_stats(**kw), raising=False)
        monkeypatch.setattr(analytics, "get_signals_recent", lambda **kw: fake_db_instance.get_signals_recent(**kw), raising=False)
        monkeypatch.setattr(analytics, "get_sessions", lambda **kw: fake_db_instance.get_sessions(), raising=False)
        monkeypatch.setattr(analytics, "get_session_detail", lambda session_id, **kw: fake_db_instance.get_session_detail(session_id), raising=False)
        monkeypatch.setattr(analytics, "export_trades_csv", lambda **kw: fake_db_instance.export_trades_csv(**kw), raising=False)
        monkeypatch.setattr(analytics, "export_trades_excel", lambda **kw: fake_db_instance.export_trades_excel(**kw), raising=False)
        monkeypatch.setattr(analytics, "export_full_report", lambda **kw: fake_db_instance.export_full_report(), raising=False)
    except Exception:
        pass

    return fake_db_instance


# ============================================================
# Flask test client con CORTAFUEGOS WSGI para /api/*
# ============================================================

@pytest.fixture
def flask_client(patch_db_manager):
    """
    Envuelve app.wsgi_app para interceptar GET a /api/* y responder con datos mock.
    Así evitamos CUALQUIER consulta a la BD real, incluso en before_request.
    """
    import importlib
    from urllib.parse import parse_qs
    from flask import Response

    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("ENV", "test")

    app_mod = importlib.import_module("dashboard.app")
    app = getattr(app_mod, "app")
    db = patch_db_manager

    orig_wsgi = app.wsgi_app

    def to_json_response(obj, status=200):
        return Response(json.dumps(obj), status=status, mimetype="application/json")

    def wsgi_firewall(environ, start_response):
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "GET").upper()
        qs = parse_qs(environ.get("QUERY_STRING", ""))

        def get_int(name):
            v = qs.get(name, [None])[0]
            try:
                return int(v) if v is not None else None
            except Exception:
                return None

        if method == "GET" and path.startswith("/api/"):
            # Trades history
            if path == "/api/trades/history":
                limit = get_int("limit")
                session_id = get_int("session_id")
                data = db.get_trades_history(limit=limit, session_id=session_id)
                return to_json_response(data)(environ, start_response)

            # Trades stats
            if path == "/api/trades/stats":
                session_id = get_int("session_id")
                data = db.get_trades_stats(session_id=session_id)
                return to_json_response(data)(environ, start_response)

            # Signals
            if path == "/api/signals/recent":
                limit = get_int("limit")
                data = db.get_signals_recent(limit=limit)
                return to_json_response(data)(environ, start_response)

            # Sessions list
            if path == "/api/sessions":
                return to_json_response(db.get_sessions())(environ, start_response)

            # Session detail /api/sessions/<id>
            if path.startswith("/api/sessions/"):
                try:
                    sid = int(path.rsplit("/", 1)[-1])
                except Exception:
                    return to_json_response({}, status=404)(environ, start_response)
                detail = db.get_session_detail(sid)
                if not detail:
                    return to_json_response({}, status=404)(environ, start_response)
                return to_json_response(detail)(environ, start_response)

            # Exports
            if path == "/api/export/trades.csv":
                body = db.export_trades_csv()
                resp = Response(body, mimetype="text/csv",
                                headers={"Content-Disposition": "attachment; filename=trades.csv"})
                return resp(environ, start_response)

            if path == "/api/export/trades.xlsx":
                body = db.export_trades_excel()
                resp = Response(body, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                headers={"Content-Disposition": "attachment; filename=trades.xlsx"})
                return resp(environ, start_response)

            if path == "/api/export/report":
                body = db.export_full_report()
                resp = Response(body, mimetype="application/json")
                return resp(environ, start_response)

        # Resto de rutas -> app real
        return orig_wsgi(environ, start_response)

    # Envolvemos la app
    app.config["TESTING"] = True
    app.wsgi_app = wsgi_firewall

    # Cliente de prueba
    with app.test_client() as client:
        yield client


# ============================================================
# Fixtures de “semilla” por test (ajustan la fake DB)
# ============================================================

@pytest.fixture
def mock_trades(patch_db_manager):
    db = patch_db_manager
    db._trades.clear()
    db._trades.extend(generate_trades(10, session_id=1))
    db._trades.extend(generate_trades(5, session_id=2))
    return db


@pytest.fixture
def mock_signals(patch_db_manager):
    db = patch_db_manager
    db._signals.clear()
    db._signals.extend(generate_signals(15))
    return db


@pytest.fixture
def mock_sessions(patch_db_manager):
    db = patch_db_manager
    db._sessions.clear()
    db._sessions.extend(generate_sessions(3))
    # Re-sembra trades consistentes con las sesiones
    db._trades.clear()
    for s in db._sessions:
        db._trades.extend(generate_trades(7, session_id=s["session_id"]))
    return db


# ============================================================
# Otros fixtures útiles
# ============================================================

@pytest.fixture
def mock_api_client():
    from unittest.mock import Mock
    client = Mock()
    client.authenticate.return_value = True
    client.get_account_info.return_value = {
        "balance": {"balance": 10000.0, "available": 8500.0},
        "accountId": "TEST123",
    }
    client.get_positions.return_value = [
        {"epic": "GOLD", "size": 1.0, "direction": "BUY", "avg_price": 175.3},
        {"epic": "EURUSD", "size": 2.5, "direction": "SELL", "avg_price": 1.0823},
    ]
    return client


@pytest.fixture
def fake_db(patch_db_manager):
    """Devuelve la instancia de la BD falsa por si el test necesita interactuar directamente."""
    return patch_db_manager


# ============================================================
# (Opcional) Helpers para aserciones en otros archivos
# ============================================================

def assert_json_ok(response, *, expect_status: int = 200):
    assert response.status_code == expect_status, f"Status {response.status_code}, body={response.data!r}"
    assert response.content_type.startswith("application/json")


def assert_bytes_ok(response, *, expect_status: int = 200, content_type_prefix: Optional[str] = None):
    assert response.status_code == expect_status, f"Status {response.status_code}"
    assert isinstance(response.data, (bytes, bytearray))
    if content_type_prefix:
        assert response.content_type.startswith(content_type_prefix)
