import re
import time

from bs4 import BeautifulSoup

from models.product import Product
from models.watch_item import WatchItem
from stores.monitor import search_nearest_store
from utils.filtering import matches_watch_item
from utils.http import create_session
from utils.units import (
    parse_base_price,
    unit_price_from_quantity,
)


# Kaufland Romania has no online shop, so prices come from two
# public sources:
# - regular shelf prices per store: Monitorul Prețurilor, the
#   government price monitor retailers must report to daily;
# - promotions: the weekly offers page on kaufland.ro.

OFFERS_URL = (
    "https://www.kaufland.ro/oferte/"
    "prezentare-generala-oferte.html?kloffer-week=current"
)
OFFERS_CACHE_SECONDS = 60 * 60

_offers_cache: dict[str, object] = {
    "loaded_at": 0.0,
    "offers": [],
}


def _parse_number(text: str | None) -> float | None:
    if not text:
        return None

    match = re.search(r"\d+(?:[.,]\d+)?", text.replace(" ", ""))

    if match is None:
        return None

    return float(match.group(0).replace(",", "."))


def _tile_text(tile, selector: str) -> str:
    element = tile.select_one(selector)

    if element is None:
        return ""

    return " ".join(element.get_text(" ").split())


# ============================================================
# WEEKLY OFFERS
# ============================================================


# "La doar" ("only ...") carries no information as a label.
UNINFORMATIVE_LABELS = {"la doar", "doar", ""}


def _promo_label(offer: dict) -> str:
    for text in (offer["discount_text"], offer["eye_catcher"]):
        if " ".join(text.split()).lower() not in UNINFORMATIVE_LABELS:
            return text

    return "Weekly offer"


# ============================================================
# PARSING
# ============================================================


def parse_offers_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    offers: list[dict] = []
    seen: set[tuple[str, float]] = set()

    for tile in soup.select(".k-product-tile"):
        title = _tile_text(tile, ".k-product-tile__title")
        subtitle = _tile_text(tile, ".k-product-tile__subtitle")
        name = f"{title} {subtitle}".strip()

        price_tag = tile.select_one(".k-price-tag")

        if not name or price_tag is None:
            continue

        price = _parse_number(
            _tile_text(price_tag, ".k-price-tag__price")
        )

        if price is None:
            continue

        key = (name.lower(), price)

        if key in seen:
            continue

        seen.add(key)

        old_price = _parse_number(
            _tile_text(price_tag, ".k-price-tag__old-price")
        )

        offers.append(
            {
                "name": name,
                "price": price,
                "old_price": old_price,
                "discount_text": _tile_text(
                    price_tag,
                    ".k-price-tag__discount",
                ),
                "package": _tile_text(
                    tile,
                    ".k-product-tile__unit-price",
                ),
                "base_price": _tile_text(
                    tile,
                    ".k-product-tile__base-price",
                ),
                "eye_catcher": _tile_text(
                    tile,
                    ".k-product-tile__eye-catcher",
                ),
                "card_only": "k-price-tag--xtra"
                in (price_tag.get("class") or []),
            }
        )

    return offers


def load_kaufland_offers(session=None) -> list[dict]:
    now = time.time()

    if now - _offers_cache["loaded_at"] < OFFERS_CACHE_SECONDS:
        return _offers_cache["offers"]

    session = session or create_session()

    response = session.get(
        OFFERS_URL,
        headers={"Accept": "text/html"},
        timeout=60,
    )

    response.raise_for_status()

    offers = parse_offers_html(response.text)

    _offers_cache["loaded_at"] = now
    _offers_cache["offers"] = offers

    return offers


def search_kaufland_offers(
    watch_item: WatchItem,
    offers: list[dict],
) -> list[Product]:
    results: list[Product] = []

    for offer in offers:
        is_match, _ = matches_watch_item(
            product_name=offer["name"],
            watch_item=watch_item,
        )

        if not is_match:
            continue

        price = offer["price"]
        old_price = offer["old_price"]

        unit_price, unit = parse_base_price(offer["base_price"])

        if unit_price is None:
            unit_price, unit = unit_price_from_quantity(
                price,
                offer["package"] or offer["name"],
            )

        discount_percent = None

        if old_price and old_price > price:
            discount_percent = round(
                (old_price - price) / old_price * 100,
                1,
            )

        loyalty_card = (
            "Kaufland Card" if offer["card_only"] else None
        )

        results.append(
            Product(
                name=offer["name"],
                price=price,
                store="Kaufland",
                url=OFFERS_URL,
                watch_label=watch_item.label,
                watch_id=watch_item.id or None,
                unit_price=unit_price,
                unit=unit,
                old_price=(
                    old_price
                    if discount_percent is not None
                    else None
                ),
                discount_percent=discount_percent,
                on_sale=True,
                promo_label=_promo_label(offer),
                loyalty_card=loyalty_card,
                package=offer["package"] or None,
                source="kaufland.ro weekly offers",
                branch="All Kaufland stores (weekly flyer)",
            )
        )

    return results


# ============================================================
# REGULAR PRICES (Monitorul Prețurilor)
# ============================================================


def search_kaufland_prices(
    watch_item: WatchItem,
    latitude: float,
    longitude: float,
    radius_km: float = 5,
    session=None,
) -> list[Product]:
    return search_nearest_store(
        watch_item,
        chain="Kaufland",
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )
