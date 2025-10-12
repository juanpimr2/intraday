# tests/test_dashboard_buttons_endpoints.py
import os
from io import BytesIO
from datetime import datetime, timezone

import pytest

import dashboard.app as appmod
from dashboard.app import app as flask_app


# --------------------------
# Stubs / Fakes para tests
# --------------------------

class _FakeAPI:
    def authenticate(self):
        return True

    def get_account_info(self):
        return {
            "balance": {"balance": 10000.0, "available": 9700.0}
        }

    def get_positions(self):
        return [{
            "market": {"epic": "DE40", "instrumentName": "DAX"},
            "position": {
                "direction": "BUY",
                "size": 1.0,
                "level": 16000.0,
                "currency": "EUR",
                "createdDate": "2025-10-01T10:00:00Z",
                "stopLevel": 15840.0,
                "profitLevel": 16080.0,
                "dealId": "D-1"
            }
        }]

    # para backtest: no lo usaremos porque se mockea BacktestEngine, pero lo dejamos por si se invoca
    def get_market_data(self, asset, timeframe, max_values=100):
        return {"prices": [{"snapshotTime": "2025-09-01T10:00:00Z", "closePrice": 1.0}]}


class _FakeAnalytics:
    def __init__(self, tmpdir):
        self.tmpdir = tmpdir

    # Historial de trades
    def get_recent_trades(self, limit=50):
        return [{
            "epic": "DE40",
            "direction": "BUY",
            "entry_price": 16000.0,
            "exit_price": 16050.0,
            "pnl": 50.0,
            "pnl_percent": 0.5,
            "close_reason": "TAKE_PROFIT"
        }]

    def get_trades_by_session(self, session_id):
        return [{
            "epic": "DE40",
            "direction": "SELL",
            "entry_price": 16100.0,
            "exit_price": 16020.0,
            "pnl": 80.0,
            "pnl_percent": 0.5,
            "close_reason": "TAKE_PROFIT"
        }]

    # Stats
    def get_global_stats(self):
        return {"total_trades": 10, "win_rate": 60.0, "total_pnl": 123.45, "profit_factor": 1.5}

    def get_trade_analysis(self, session_id):
        return {"total_trades": 3, "win_rate": 66.7, "total_pnl": 80.0, "profit_factor": 2.0}

    # Sesiones
    def get_sessions_summary(self, limit=20):
        return [{"session_id": 1, "from": "2025-09-01", "to": "2025-09-02"}]

    def get_session_info(self, session_id):
        return {"session_id": session_id, "from": "2025-09-01", "to": "2025-09-02"}

    def get_signals_by_session(self, session_id):
        return [{"epic": "DE40", "signal": "BUY", "confidence": 0.7}]

    # Señales recientes
    def get_recent_signals(self, limit=20):
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return [{"epic": "DE40", "signal": "BUY", "confidence": 0.75, "price": 16010.0, "timestamp": now}]

    # Exportaciones usadas por botones
    def export_trades(self, session_id=None, format="csv"):
        suf = "csv" if format == "csv" else "xlsx"
        path = self.tmpdir / f"export_session_{session_id or 'all'}.{suf}"
        path.write_bytes(b"epic,direction,pnl\nDE40,BUY,50\n")
        return str(path)

    def export_all_trades(self, format="csv"):
        suf = "csv" if format == "csv" else "xlsx"
        path = self.tmpdir / f"export_all.{suf}"
        path.write_bytes(b"epic,direction,pnl\nDE40,BUY,50\n")
        return str(path)

    def export_full_report(self, session_id, format="excel"):
        path = self.tmpdir / f"full_report_session_{session_id}.xlsx"
        path.write_bytes(b"fake-binary-xlsx")
        return str(path)

    # Equity (para futuros tests de /api/equity/export si quisieras)
    def get_equity_series(self, limit=10000):
        return [{"ts_utc": "2025-09-01T10:00:00Z", "equity": 10000.0, "cash": 9700.0, "open_positions": 1}]


class _FakeBotState:
    def __init__(self):
        self.running = False
        self.manual_override = False
        self.last_command = None

    def start(self):
        self.running = True
        self.manual_override = False
        self.last_command = "START"

    def stop(self):
        self.running = False
        self.manual_override = True
        self.last_command = "STOP"

    def get_status(self):
        return {
            "running": self.running, 
            "manual_override": self.manual_override, 
            "last_command": self.last_command,
            "last_heartbeat": None
        }
    
    def is_running(self):
        return self.running


class _FakeBacktestEngine:
    def __init__(self, initial_capital=10000.0):
        self.initial_capital = initial_capital

    def run(self, historical_data):
        # Devolver dict (el endpoint espera .get(...))
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.initial_capital + 100.0,
            "total_return": 100.0,
            "total_return_percent": 1.0,
            "total_trades": 3,
            "winning_trades": 2,
            "losing_trades": 1,
            "win_rate": 66.7,
            "avg_win": 20.0,
            "avg_loss": -10.0,
            "profit_factor": 2.0,
            "max_drawdown": 0.5,
            "equity_curve": [],
            "trades_detail": []
        }


# --------------------------
# Fixtures
# --------------------------

@pytest.fixture(autouse=True)
def _patch_dependencies(tmp_path, monkeypatch):
    """
    Parchea dependencias del dashboard para pruebas:
    - API de Capital (auth, account, positions)
    - Analytics (historial, stats, exportaciones, señales)
    - BotController (arranque/paro)
    - BacktestEngine (resultado sintético)
    """
    fake_api = _FakeAPI()
    fake_analytics = _FakeAnalytics(tmp_path)
    fake_bot_state = _FakeBotState()

    # get_api_client / get_analytics / get_bot_controller → stubs
    monkeypatch.setattr(appmod, "get_api_client", lambda: fake_api)
    monkeypatch.setattr(appmod, "get_analytics", lambda: fake_analytics)
    monkeypatch.setattr(appmod, "get_bot_controller", lambda: fake_bot_state)

    # BacktestEngine → stub
    monkeypatch.setattr(appmod, "BacktestEngine", _FakeBacktestEngine)

    yield


@pytest.fixture
def client():
    return flask_app.test_client()


# --------------------------
# Tests BOTONES / ENDPOINTS
# --------------------------

def test_button_start_stop_endpoints(client):
    # start
    res = client.post("/api/bot/start")
    assert res.status_code == 200
    data = res.get_json()
    assert data.get("success") is True

    # stop
    res = client.post("/api/bot/stop")
    assert res.status_code == 200
    data = res.get_json()
    assert data.get("success") is True


def test_exports_buttons_csv_excel(client):
    # CSV (sin session_id → export_all_trades)
    res = client.get("/api/trades/export/csv")
    assert res.status_code == 200
    # Content-Disposition attachment esperado
    disp = res.headers.get("Content-Disposition", "")
    assert "attachment" in disp
    assert ".csv" in disp

    # Excel
    res = client.get("/api/trades/export/excel")
    assert res.status_code == 200
    disp = res.headers.get("Content-Disposition", "")
    assert "attachment" in disp
    assert ".excel" in disp or ".xlsx" in disp  # nombre incluye extensión pedida por endpoint


def test_full_report_button(client):
    res = client.get("/api/report/full?session_id=123")
    assert res.status_code == 200
    disp = res.headers.get("Content-Disposition", "")
    assert "attachment" in disp
    assert ".xlsx" in disp


def test_backtest_button(client):
    payload = {"days": 10, "initial_capital": 10000.0}
    res = client.post("/api/backtest/run", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert "results" in data
    r = data["results"]
    # keys que muestra el frontend
    for k in ("final_capital", "total_return", "total_return_percent", "win_rate", "total_trades"):
        assert k in r


def test_trades_history_and_stats_buttons(client):
    # Historial
    res = client.get("/api/trades/history?limit=10")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data.get("trades"), list)
    assert data.get("count") >= 1

    # Stats
    res = client.get("/api/trades/stats")
    assert res.status_code == 200
    stats = res.get_json().get("stats", {})
    for k in ("total_trades", "win_rate", "total_pnl", "profit_factor"):
        assert k in stats


def test_refresh_endpoints_used_by_dashboard(client):
    # account
    res = client.get("/api/account")
    assert res.status_code == 200
    acc = res.get_json()
    for k in ("balance", "available", "margin_used", "margin_percent"):
        assert k in acc

    # positions
    res = client.get("/api/positions")
    assert res.status_code == 200
    pos = res.get_json()
    assert isinstance(pos.get("positions"), list)
    assert isinstance(pos.get("count"), int)

    # config
    res = client.get("/api/config")
    assert res.status_code == 200
    cfg = res.get_json()
    for k in ("assets", "max_positions", "target_percent", "max_risk", "timeframe", "trading_hours"):
        assert k in cfg

    # status
    res = client.get("/api/status")
    assert res.status_code == 200
    st = res.get_json()
    for k in ("status", "running", "is_trading_hours"):
        assert k in st


def test_recent_signals_button(client):
    res = client.get("/api/signals/recent?limit=20")
    assert res.status_code == 200
    data = res.get_json()
    assert isinstance(data.get("signals"), list)
    assert data.get("count") >= 1
