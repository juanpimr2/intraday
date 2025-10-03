import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv('POSTGRES_HOST', 'localhost'),
    port=int(os.getenv('POSTGRES_PORT', 5432)),
    database=os.getenv('POSTGRES_DB', 'trading_bot'),
    user=os.getenv('POSTGRES_USER', 'trader'),
    password=os.getenv('POSTGRES_PASSWORD', 'secure_password_123')
)

cursor = conn.cursor()
cursor.execute("DELETE FROM schema_migrations WHERE version = 'v002_analytics_views'")
conn.commit()
cursor.close()
conn.close()

print("✅ v002 borrada de schema_migrations")