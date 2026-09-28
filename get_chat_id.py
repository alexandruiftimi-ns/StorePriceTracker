import os

import requests
from dotenv import load_dotenv


load_dotenv()

bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

if not bot_token:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing from .env"
    )


delete_webhook_url = (
    f"https://api.telegram.org/"
    f"bot{bot_token}/deleteWebhook"
)

delete_response = requests.get(
    delete_webhook_url,
    timeout=20,
)

print("Delete webhook:")
print(delete_response.json())


updates_url = (
    f"https://api.telegram.org/"
    f"bot{bot_token}/getUpdates"
)

updates_response = requests.get(
    updates_url,
    timeout=20,
)

print()
print("Updates:")
print(updates_response.json())