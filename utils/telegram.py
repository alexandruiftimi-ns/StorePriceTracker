import os

import requests
from dotenv import load_dotenv

from models.product import Product
from utils.changes import ProductChanges


load_dotenv()

TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_MESSAGE_LIMIT = 4000


def get_credentials() -> tuple[str, str]:
    """
    The token and chat id entered in the app's Settings, or
    TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from .env.
    """
    from utils.catalog import load_settings

    settings = load_settings()

    token = (
        settings.get("telegram_bot_token")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    )
    chat_id = (
        settings.get("telegram_chat_id")
        or os.getenv("TELEGRAM_CHAT_ID")
        or ""
    )

    return token.strip(), str(chat_id).strip()


def is_configured() -> bool:
    return all(get_credentials())


def call_api(token: str, method: str, **payload) -> dict:
    """
    Errors carry Telegram's description only: the request URL
    contains the token and must not end up in logs or the UI.
    """
    if not token:
        raise RuntimeError("No Telegram bot token set.")

    try:
        response = requests.post(
            f"{TELEGRAM_API}/bot{token}/{method}",
            json=payload,
            timeout=30,
        )
        data = response.json()

    except (requests.RequestException, ValueError):
        raise RuntimeError("Could not reach Telegram.") from None

    if not data.get("ok"):
        description = data.get("description") or "unknown error"

        if response.status_code == 401:
            description = "the bot token is not valid"

        raise RuntimeError(f"Telegram: {description}")

    return data["result"]


def get_bot_info(token: str) -> dict:
    return call_api(token, "getMe")


def find_chats(token: str) -> list[dict]:
    """
    Chats that recently messaged the bot, newest first.
    """
    try:
        updates = call_api(token, "getUpdates")

    except RuntimeError as error:
        # getUpdates is refused while a webhook is set.
        if "webhook" not in str(error).lower():
            raise

        call_api(token, "deleteWebhook")
        updates = call_api(token, "getUpdates")

    chats: dict[str, dict] = {}

    for update in reversed(updates):
        message = (
            update.get("message")
            or update.get("edited_message")
            or update.get("channel_post")
            or update.get("my_chat_member")
            or {}
        )
        chat = message.get("chat")

        if not chat:
            continue

        name = (
            chat.get("title")
            or " ".join(
                part
                for part in (chat.get("first_name"), chat.get("last_name"))
                if part
            )
            or chat.get("username")
            or "Chat"
        )

        chats.setdefault(
            str(chat["id"]),
            {"id": str(chat["id"]), "name": name, "type": chat.get("type")},
        )

    return list(chats.values())


def send_message(
    message: str,
    token: str | None = None,
    chat_id: str | None = None,
) -> None:
    saved_token, saved_chat_id = get_credentials()
    token = token or saved_token
    chat_id = chat_id or saved_chat_id

    if not token or not chat_id:
        raise RuntimeError(
            "Telegram is not set up: add your bot token and chat id "
            "in Settings."
        )

    for message_part in split_message(message):
        call_api(
            token,
            "sendMessage",
            chat_id=chat_id,
            text=message_part,
            disable_web_page_preview=True,
        )


def split_message(message: str) -> list[str]:
    if len(message) <= TELEGRAM_MESSAGE_LIMIT:
        return [message]

    parts: list[str] = []
    current_part: list[str] = []
    current_length = 0

    for line in message.splitlines():
        line_length = len(line) + 1

        if (
            current_part
            and current_length + line_length
            > TELEGRAM_MESSAGE_LIMIT
        ):
            parts.append("\n".join(current_part))
            current_part = []
            current_length = 0

        current_part.append(line)
        current_length += line_length

    if current_part:
        parts.append("\n".join(current_part))

    return parts


def build_deals_message(
    deals_by_store: dict[str, list[Product]],
) -> str:
    lines = [
        "🛒 Grocery deals",
        "",
    ]

    total_promotions = 0

    for store_name, products in deals_by_store.items():
        lines.append(f"🏪 {store_name.upper()}")
        lines.append("")

        for index, product in enumerate(
            products,
            start=1,
        ):
            total_promotions += 1

            lines.append(f"{index}. {product.name}")
            lines.append(
                f"Package price: {product.price:.2f} lei"
            )

            if (
                product.unit_price is not None
                and product.unit is not None
            ):
                lines.append(
                    f"Unit price: "
                    f"{product.unit_price:.2f} "
                    f"lei/{product.unit}"
                )

            if product.old_price is not None:
                lines.append(
                    f"Old price: "
                    f"{product.old_price:.2f} lei"
                )

            if product.discount_percent is not None:
                lines.append(
                    f"Discount: "
                    f"{product.discount_percent:.1f}%"
                )

            lines.append("")

        lines.append("")

    lines.append(
        f"Total promotions: {total_promotions}"
    )

    return "\n".join(lines)


def build_changes_message(
    changes: ProductChanges,
) -> str:
    lines = [
        "🛒 Grocery price update",
        "",
    ]

    if changes.new_promotions:
        lines.append("🆕 NEW PROMOTIONS")
        lines.append("")

        for product in changes.new_promotions:
            lines.append(f"• {product.name}")
            lines.append(f"  🏪 {product.store}")
            lines.append(
                f"  Package: {product.price:.2f} lei"
            )

            if (
                product.unit_price is not None
                and product.unit is not None
            ):
                lines.append(
                    f"  Unit: "
                    f"{product.unit_price:.2f} "
                    f"lei/{product.unit}"
                )

            if product.discount_percent is not None:
                lines.append(
                    f"  Discount: "
                    f"{product.discount_percent:.1f}%"
                )

            lines.append("")

    if changes.price_drops:
        lines.append("📉 PRICE DROPS")
        lines.append("")

        for previous, current in changes.price_drops:
            difference = (
                previous.price
                - current.price
            )

            lines.append(f"• {current.name}")
            lines.append(f"  🏪 {current.store}")
            lines.append(
                f"  {previous.price:.2f} → "
                f"{current.price:.2f} lei"
            )
            lines.append(
                f"  Difference: "
                f"-{difference:.2f} lei"
            )
            lines.append("")

    if changes.price_increases:
        lines.append("📈 PRICE INCREASES")
        lines.append("")

        for previous, current in changes.price_increases:
            difference = (
                current.price
                - previous.price
            )

            lines.append(f"• {current.name}")
            lines.append(f"  🏪 {current.store}")
            lines.append(
                f"  {previous.price:.2f} → "
                f"{current.price:.2f} lei"
            )
            lines.append(
                f"  Difference: "
                f"+{difference:.2f} lei"
            )
            lines.append("")

    if changes.ended_promotions:
        lines.append("❌ PROMOTIONS ENDED")
        lines.append("")

        for product in changes.ended_promotions:
            lines.append(f"• {product.name}")
            lines.append(f"  🏪 {product.store}")
            lines.append("")

    if changes.new_products:
        lines.append("➕ NEW PRODUCTS FOUND")
        lines.append("")

        for product in changes.new_products:
            lines.append(f"• {product.name}")
            lines.append(f"  🏪 {product.store}")
            lines.append(
                f"  Price: {product.price:.2f} lei"
            )
            lines.append("")

    if changes.missing_products:
        lines.append("➖ PRODUCTS NO LONGER FOUND")
        lines.append("")

        for product in changes.missing_products:
            lines.append(f"• {product.name}")
            lines.append(f"  🏪 {product.store}")
            lines.append("")

    total_changes = (
        len(changes.new_products)
        + len(changes.missing_products)
        + len(changes.new_promotions)
        + len(changes.ended_promotions)
        + len(changes.price_drops)
        + len(changes.price_increases)
    )

    lines.append(
        f"Total changes: {total_changes}"
    )

    return "\n".join(lines)

def build_best_prices_message(
    best_products_by_label: dict[str, list[Product]],
) -> str:
    lines = [
        "🏆 Best prices by product",
        "",
    ]

    for watch_label, ranked_products in (
        best_products_by_label.items()
    ):
        lines.append(f"🛒 {watch_label}")
        lines.append("")

        for rank, product in enumerate(
            ranked_products,
            start=1,
        ):
            medal = {
                1: "🥇",
                2: "🥈",
                3: "🥉",
            }.get(rank, f"{rank}.")

            lines.append(
                f"{medal} {product.store}"
            )
            lines.append(
                f"{product.name}"
            )

            if (
                product.unit_price is not None
                and product.unit is not None
            ):
                lines.append(
                    f"{product.unit_price:.2f} "
                    f"lei/{product.unit}"
                )
            else:
                lines.append(
                    f"{product.price:.2f} lei/package"
                )

            if product.on_sale:
                if product.discount_percent is not None:
                    lines.append(
                        f"Promotion: "
                        f"-{product.discount_percent:.1f}%"
                    )
                else:
                    lines.append("Promotion: Yes")
            else:
                lines.append("Promotion: No")

            lines.append("")

        lines.append("")

    return "\n".join(lines)

def build_shopping_report_message(
    report: dict,
) -> str:
    lines = [
        "🛒 Shopping list — where to buy today",
        "",
    ]

    recommendation = report.get("recommendation") or {}

    for title, key in (
        ("🏆 Best market", "best"),
        ("🥈 Second best", "second"),
    ):
        entry = recommendation.get(key)

        if entry:
            lines.append(f"{title}: {entry['store']}")
            lines.append(entry["reason"])
            lines.append("")

    for item in report.get("items", []):
        best = item.get("best")

        lines.append(f"• {item['label']}")

        if best is None:
            lines.append("  Not found")
            continue

        unit = item.get("compare_unit")
        price_text = (
            f"{best['comparison_price']:.2f} lei/{unit}"
            if unit
            else f"{best['price']:.2f} lei"
        )

        lines.append(f"  {best['store']}: {price_text}")
        lines.append(f"  {best['name']}")

        if best.get("branch"):
            lines.append(f"  📍 {best['branch']}")

        if best.get("on_sale"):
            promo = best.get("promo_label") or "Promotion"

            if best.get("loyalty_card"):
                promo += f" with {best['loyalty_card']}"

            lines.append(f"  🔥 {promo}")

    return "\n".join(lines)
