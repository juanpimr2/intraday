# start_all.py
import threading
import logging
from trading.trading_bot import TradingBot
from dashboard.app import run_dashboard

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_bot_thread():
    """Ejecuta el bot en un thread"""
    bot = TradingBot()
    bot.run()

def run_dashboard_thread():
    """Ejecuta el dashboard en un thread"""
    run_dashboard(port=5000, debug=False)

if __name__ == '__main__':
    print("="*60)
    print("🚀 INICIANDO BOT + DASHBOARD")
    print("="*60)
    
    # Iniciar dashboard en thread separado
    dashboard_thread = threading.Thread(target=run_dashboard_thread, daemon=True)
    dashboard_thread.start()
    
    print("✅ Dashboard iniciado en http://localhost:5000")
    print("🤖 Iniciando bot de trading...")
    print("="*60)
    
    # Ejecutar bot en thread principal
    try:
        run_bot_thread()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo sistema...")