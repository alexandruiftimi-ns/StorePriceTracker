"""
Prints the chat ids that recently messaged your bot.

The web app does the same with Settings → Telegram → "Find my
chat ID"; this script is for setups that use .env instead.
Send your bot a message first, then run: python get_chat_id.py
"""

from utils.telegram import find_chats, get_credentials


token, _ = get_credentials()

if not token:
    raise SystemExit(
        "No bot token found. Add it in the app's Settings, "
        "or set TELEGRAM_BOT_TOKEN in .env."
    )

chats = find_chats(token)

if not chats:
    print(
        "No messages found. Open your bot in Telegram, send it "
        "any message, then run this again."
    )

for chat in chats:
    print(f"{chat['id']}  {chat['name']} ({chat['type']})")
