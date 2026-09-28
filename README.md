# Stores Price Tracker

Compares grocery prices at **Auchan, Lidl and Kaufland** (Romania) for the
products you buy regularly and tells you where to shop today.

## Workflow

1. **My products**: add the products you buy (name, Romanian search term, filters).
2. When you run out of something, **tap its card**. It goes to the shopping list.
3. **Shopping list → 🔍 Search markets** searches all three stores and shows:
   - **Best market today**: the store with the most useful promotions on your list
   - **Second best**: the store that is cheapest (per kg/l) for the most items
   - a **shopping plan** splitting the list between those two stores
   - per product: the cheapest price per kg/l in each store, promotions, links
4. Tap **✓ bought** to remove items from the list.

## Setup

Requires Python 3.10 or newer.

```
git clone <this repo>
cd "Stores Price Tracker"

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

Optional: `playwright install chromium` is only needed for the old
browser-based Auchan scraper (`search_auchan`), which the app no longer
uses by default.

### Set your location

The default location is **central Bucharest** (Piața Unirii). Kaufland
prices come from the Kaufland nearest to that location, so set your own:

1. Start the app and open **Settings**.
2. Press **📍 Use my current location** and allow the browser's location
   prompt. You can also type coordinates copied from Google Maps
   (right-click a place → click the coordinates to copy them).
3. Press **Save settings**.

Until you do, the Shopping list page shows a reminder.

## Run

```
python app.py            # web app, opens http://127.0.0.1:5000
python main.py           # CLI scan of all products (+ Telegram, history)
python main.py --list    # CLI scan of the shopping list only
```

## Telegram notifications (optional)

The app works without Telegram. To get results on your phone, create
**your own** bot. Each user needs their own bot token and chat id, and no
token is included in this repository.

1. **Create a bot.** In Telegram, open a chat with
   [@BotFather](https://t.me/BotFather), send `/newbot`, and follow the
   prompts (a display name, then a username ending in `bot`). BotFather
   replies with a token like `123456789:AAH...`. This is your
   `TELEGRAM_BOT_TOKEN`.
2. **Create your `.env` file.** Copy `.env.example` to `.env` and paste
   the token:
   ```
   TELEGRAM_BOT_TOKEN=123456789:AAH...
   TELEGRAM_CHAT_ID=
   ```
3. **Find your chat id.** Open a chat with your new bot and send it any
   message (e.g. `hi`). Then run:
   ```
   python get_chat_id.py
   ```
   In the output, find `"chat": {"id": 123456789, ...}`. That number is
   your `TELEGRAM_CHAT_ID`; add it to `.env`. If the output shows
   `"result": []`, send the bot another message and run the script again.
4. **Test it:** `python test_telegram.py` should send you a message.
5. **Turn it on:** `python main.py` sends automatically when `.env` is
   filled in. For the web app, tick **Settings → Also send search results
   to Telegram**.

**Keep your token secret.** Anyone with it can control your bot. `.env` is
listed in `.gitignore`, so it is never committed. If a token ever leaks,
send `/revoke` to BotFather to get a new one.

## Data sources

| Store    | Regular prices                                             | Promotions                                  |
|----------|------------------------------------------------------------|---------------------------------------------|
| Auchan   | auchan.ro search API                                       | same (list price vs. price)                 |
| Lidl     | daily price file `preturiZilniceLidl.xlsb`                 | lidl.ro search API (incl. Lidl Plus)        |
| Kaufland | monitorulpreturilor.info, nearest store to your location   | kaufland.ro weekly offers (incl. Kaufland Card) |

Kaufland has no online shop, so loose fruit and vegetables only show up
when they are in the weekly offers.

Prices can differ between stores of the same chain. Kaufland prices come
from the store nearest to you; Lidl and Auchan prices are the chain's
published prices, which some individual stores deviate from.

## Tuning a product

Store names differ ("Piept de pui" vs "PIEPT PUI DEZOSAT"), so each product has:

- **Must contain**: comma separated. `|` means alternatives: `piept de pui|piept pui`.
- **Exclude**: words that reject a product (`sunca, nuggets`).
- **Name must start with…**: for fresh produce ("Banane", not "Iaurt cu banane").

A word after "cu" / "aromă de" / "gust de" is treated as an ingredient and not matched.
Use **Test search** in the editor, or **✕ not this** in the results, to tune filters.

## Files

- `data/products.json`: your products and shopping list (seeded from `watchlist.py`)
- `data/settings.json`: location, stores, options
- `data/last_search.json`: latest search results
- `history/<store>/`: per-store snapshots written by `main.py`
- `.env`: your Telegram token and chat id (create from `.env.example`)

`data/`, `history/` and `.env` are personal and excluded from git.
