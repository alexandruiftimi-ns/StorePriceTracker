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

### Set your location and Lidl stores

The default location is **central Bucharest** (Piața Unirii). Set your own
so the app uses the stores near you:

1. Start the app and open **Settings**.
2. Press **📍 Use my current location** and allow the browser's location
   prompt. You can also type coordinates copied from Google Maps
   (right-click a place → click the coordinates to copy them).
3. Press **🔍 Find Lidl stores near my location** and tick the Lidl stores
   you shop at. Each one shows its address and distance.
4. Press **Save settings**.

Until you set a location, the Shopping list page shows a reminder.

## Run

```
python app.py            # web app, opens http://127.0.0.1:5000
python main.py           # CLI scan of all products (+ Telegram, history)
python main.py --list    # CLI scan of the shopping list only
```

## Telegram notifications (optional, free)

The app works without Telegram. To get your results on your phone, you
create **your own** Telegram bot (free, about 2 minutes). No token is
included in this repository.

Everything is done in the app, under **Settings → 📨 Telegram
notifications**, which walks you through these steps:

1. **Create your bot.** In Telegram, open
   [@BotFather](https://t.me/BotFather), send `/newbot`, choose a name and
   a username ending in `bot`. BotFather replies with a token like
   `123456789:AAH...`.
2. **Paste the token** in Settings and press **Check token**. The app
   shows your bot's link.
3. **Message your bot.** Open it in Telegram, press **Start** or send any
   message.
4. **Press Find my chat ID.** The app fills in your chat ID.
5. **Press Send test message** and check Telegram.
6. **Tick "Send my search results to Telegram"** and press **Save
   settings**.

The token and chat ID are stored only on your computer, in
`data/settings.json` (excluded from git). The page never displays a saved
token again, only its last 4 characters. **Remove saved Telegram details**
at the bottom of the section deletes them.

**Keep your token secret:** anyone with it can control your bot. If it
leaks, send `/revoke` to @BotFather and paste the new token in Settings.

<details>
<summary>Alternative: a <code>.env</code> file (for <code>main.py</code> on a server)</summary>

Copy `.env.example` to `.env` and fill in `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`. `python get_chat_id.py` prints your chat ID after you
message the bot. Values entered in Settings take priority over `.env`.

</details>

## Data sources

| Store    | Regular prices                                             | Promotions                                  |
|----------|------------------------------------------------------------|---------------------------------------------|
| Auchan   | auchan.ro search API                                       | same (list price vs. price)                 |
| Lidl     | your chosen stores via monitorulpreturilor.info; national `preturiZilniceLidl.xlsb` if none chosen | per-store promotions (monitor) + lidl.ro offers incl. Lidl Plus |
| Kaufland | monitorulpreturilor.info, nearest store to your location   | kaufland.ro weekly offers (incl. Kaufland Card) |

Kaufland has no online shop, so loose fruit and vegetables only show up
when they are in the weekly offers.

Prices and promotions can differ between stores of the same chain, so
every result shows 📍 which store(s) it applies to:

- **Lidl**: each of your chosen stores' own prices. When several of them
  have the same price they share one row (e.g. "Lidl Rahova (2.6 km),
  Lidl Doina (2.6 km)"); a store with a different price or promotion
  gets its own row. Offers from lidl.ro apply to all stores.
- **Kaufland**: the nearest store (name and distance); weekly-flyer offers
  apply to all stores.
- **Auchan**: auchan.ro online prices.

## Tuning a product

Store names differ ("Piept de pui" vs "PIEPT PUI DEZOSAT"), so each product has:

- **Must contain**: comma separated. `|` means alternatives: `piept de pui|piept pui`.
- **Exclude**: words that reject a product (`sunca, nuggets`).
- **Name must start with…**: for fresh produce ("Banane", not "Iaurt cu banane").

A word after "cu" / "aromă de" / "gust de" is treated as an ingredient and not matched.
Use **Test search** in the editor, or **✕ not this** in the results, to tune filters.

## Files

- `data/products.json`: your products and shopping list (seeded from `watchlist.py`)
- `data/settings.json`: location, chosen Lidl stores, options, Telegram token and chat ID
- `data/last_search.json`: latest search results
- `history/<store>/`: per-store snapshots written by `main.py`
- `.env` (optional): Telegram token and chat ID for command-line use

`data/`, `history/` and `.env` are personal and excluded from git.
