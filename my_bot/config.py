import os
from environs import Env

env = Env()
env.read_env()

# Bot va Admin sozlamalari
BOT_TOKEN = env.str("BOT_TOKEN", "8681564120:AAFvoXZ_tGilmuLHensnMu66twbBfFbFlh4")
ADMIN_ID = env.int("ADMIN_ID", 8052376816)  # O'z Telegram ID raqamingizni yozing
CHANNEL_ID = env.str("CHANNEL_ID", "@usatslayt")  # Majburiy obuna kanali

# Render uchun Webhook sozlamalari
WEBHOOK_HOST = env.str("WEBHOOK_HOST", "https://sizning-app-nomingiz.onrender.com")
WEBHOOK_PATH = f"/bot/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.environ.get("PORT", 8080))
