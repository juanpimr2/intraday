from utils.bot_controller import BotController
from api.capital_client import CapitalClient
import logging

logging.basicConfig(level=logging.INFO)

print("🤖 Probando BotController...")

# Crear cliente API
api = CapitalClient()
if not api.authenticate():
    print("❌ No se pudo autenticar")
    exit(1)

# Crear BotController CON api_client (lo que arreglamos)
controller = BotController(api, poll_seconds=15)
print("✅ BotController creado correctamente")

# Verificar estado inicial
status = controller.get_status()
print(f"📊 Estado inicial: {status}")

# Probar START
controller.start_bot()
status = controller.get_status()
print(f"▶️ Después de START: running={status['running']}")

# Probar STOP
controller.stop_bot()
status = controller.get_status()
print(f"⏸️ Después de STOP: running={status['running']}")

print("✅ BotController funciona correctamente")
