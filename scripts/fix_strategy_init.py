filepath = "trading/trading_bot.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Arreglar la línea de inicialización de strategy
content = content.replace(
    "self.strategy = IntradayStrategy(self.config)",
    "self.strategy = IntradayStrategy()"
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ IntradayStrategy inicialización corregida")
