import re
import time

from bs4 import BeautifulSoup

from models.product import Product
from models.watch_item import WatchItem
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

MONITOR_API = "https://monitorulpreturilor.info/pmonsvc/Retail"
KAUFLAND_NETWORK_ID = "KAUFLAND"
MONITOR_BATCH_SIZE = 100
MONITOR_MAX_CATALOG_IDS = 400

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
            )
        )

    return results


# ============================================================
# REGULAR PRICES (Monitorul Prețurilor)
# ============================================================


def _find_catalog_ids(
    session,
    watch_item: WatchItem,
) -> list[str]:
    response = session.get(
        f"{MONITOR_API}/GetCatalogProductsByNameNetwork",
        params={"prodname": watch_item.search_term},
        timeout=30,
    )

    response.raise_for_status()

    catalog = response.json().get("Items") or []

    matching_ids = [
        entry["id"]
        for entry in catalog
        if matches_watch_item(
            product_name=entry.get("name", ""),
            watch_item=watch_item,
        )[0]
    ]

    return matching_ids[:MONITOR_MAX_CATALOG_IDS]


def search_kaufland_prices(
    watch_item: WatchItem,
    latitude: float,
    longitude: float,
    radius_km: float = 5,
    session=None,
) -> list[Product]:
    session = session or create_session()

    catalog_ids = _find_catalog_ids(session, watch_item)

    # Nearest store offering each catalog product.
    best_by_catalog_id: dict[str, tuple[float, dict, str]] = {}

    for start in range(0, len(catalog_ids), MONITOR_BATCH_SIZE):
        batch = catalog_ids[start:start + MONITOR_BATCH_SIZE]

        response = session.get(
            f"{MONITOR_API}/GetStoresForProductsByLatLon",
            params={
                "lat": latitude,
                "lon": longitude,
                "buffer": int(radius_km * 1000),
                "csvprodids": ",".join(batch),
                "csvnetworkids": KAUFLAND_NETWORK_ID,
            },
            timeout=60,
        )

        response.raise_for_status()

        for store in response.json().get("Items") or []:
            distance = store.get("distance") or 0
            store_name = store.get("name") or "Kaufland"

            for raw in store.get("Products") or []:
                if not raw.get("price"):
                    continue

                catalog_id = (raw.get("catprod") or {}).get("id")
                current = best_by_catalog_id.get(catalog_id)

                if current is None or distance < current[0]:
                    best_by_catalog_id[catalog_id] = (
                        distance,
                        raw,
                        store_name,
                    )

    results: list[Product] = []

    for distance, raw, store_name in best_by_catalog_id.values():
        product_name = " ".join(raw.get("name", "").split())

        # Catalog names can differ from the store label, so
        # confirm the match on the label too.
        if not matches_watch_item(
            product_name=product_name,
            watch_item=watch_item,
        )[0]:
            continue

        price = float(raw["price"])
        sale_unit = (raw.get("unit") or "").upper()

        if sale_unit == "KG":
            unit_price, unit = round(price, 2), "kg"
            package = "per kg"

        elif sale_unit == "L":
            unit_price, unit = round(price, 2), "l"
            package = "per l"

        else:
            unit_price, unit = unit_price_from_quantity(
                price,
                product_name,
            )
            package = None

        is_promo = bool(raw.get("promo"))

        results.append(
            Product(
                name=product_name.title(),
                price=price,
                store="Kaufland",
                url=(
                    "https://monitorulpreturilor.info/"
                ),
                watch_label=watch_item.label,
                watch_id=watch_item.id or None,
                unit_price=unit_price,
                unit=unit,
                on_sale=is_promo,
                promo_label="Promoție" if is_promo else None,
                package=package,
                source=(
                    f"{store_name} ({distance:.1f} km), "
                    f"price date {raw.get('pricedate', '?')}"
                ),
            )
        )

    return results
