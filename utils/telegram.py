import os

import requests
from dotenv import load_dotenv

from models.product import Product
from utils.changes import ProductChanges


load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TELEGRAM_MESSAGE_LIMIT = 4000


def send_message(message: str) -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing from .env"
        )

    if not CHAT_ID:
        raise RuntimeError(
            "TELEGRAM_CHAT_ID is missing from .env"
        )

    message_parts = split_message(message)

    for message_part in message_parts:
        url = (
            f"https://api.telegram.org/"
            f"bot{BOT_TOKEN}/sendMessage"
        )

        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": message_part,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )

        response.raise_for_status()


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

        if best.get("on_sale"):
            promo = best.get("promo_label") or "Promotion"

            if best.get("loyalty_card"):
                promo += f" with {best['loyalty_card']}"

            lines.append(f"  🔥 {promo}")

    return "\n".join(lines)
