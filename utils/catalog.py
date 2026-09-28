import json
import threading
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from models.watch_item import WatchItem


DATA_FOLDER = Path("data")
PRODUCTS_FILE = DATA_FOLDER / "products.json"
SETTINGS_FILE = DATA_FOLDER / "settings.json"
LAST_SEARCH_FILE = DATA_FOLDER / "last_search.json"

STORES = ["Auchan", "Lidl", "Kaufland"]

DEFAULT_SETTINGS = {
    # Central Bucharest (Piața Unirii). Used to pick the nearest
    # Kaufland; users set their own from Settings.
    "latitude": 44.4268,
    "longitude": 26.1025,
    "kaufland_radius_km": 5,
    "include_loyalty_prices": True,
    "enabled_stores": list(STORES),
    "send_to_telegram": False,
}

_lock = threading.RLock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_json(path: Path, default):
    if not path.exists():
        return default

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data) -> None:
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    temporary_path.replace(path)


def _clean_words(words) -> list[str]:
    if isinstance(words, str):
        words = words.split(",")

    return [
        word.strip()
        for word in words or []
        if word and word.strip()
    ]


# ============================================================
# PRODUCTS
# ============================================================


def _seed_products() -> list[dict]:
    from watchlist import WATCHLIST

    return [
        {
            **asdict(item),
            "id": uuid.uuid4().hex[:10],
            "in_shopping_list": False,
            "added_to_list_at": None,
            "created_at": _now(),
        }
        for item in WATCHLIST
    ]


def load_products() -> list[dict]:
    with _lock:
        data = _read_json(PRODUCTS_FILE, None)

        if data is None:
            data = {"products": _seed_products()}
            _write_json(PRODUCTS_FILE, data)

        return data["products"]


def _save_products(products: list[dict]) -> None:
    _write_json(PRODUCTS_FILE, {"products": products})


def validate_product(payload: dict) -> dict:
    label = (payload.get("label") or "").strip()

    if not label:
        raise ValueError("Product name is required.")

    search_term = (payload.get("search_term") or "").strip()

    if not search_term:
        search_term = label

    required_words = _clean_words(payload.get("required_words"))

    if not required_words:
        # Default: the product name must contain the search.
        required_words = [search_term]

    return {
        "label": label,
        "category": (payload.get("category") or "Other").strip(),
        "search_term": search_term,
        "required_words": required_words,
        "excluded_words": _clean_words(
            payload.get("excluded_words")
        ),
        "match_start": bool(payload.get("match_start")),
    }


def create_product(payload: dict) -> dict:
    product = {
        **validate_product(payload),
        "id": uuid.uuid4().hex[:10],
        "in_shopping_list": bool(payload.get("in_shopping_list")),
        "added_to_list_at": None,
        "created_at": _now(),
    }

    if product["in_shopping_list"]:
        product["added_to_list_at"] = _now()

    with _lock:
        products = load_products()
        products.append(product)
        _save_products(products)

    return product


def update_product(product_id: str, payload: dict) -> dict:
    with _lock:
        products = load_products()
        for product in products:
            if product["id"] != product_id:
                continue

            product.update(validate_product({**product, **payload}))
            _save_products(products)

            return product

    raise KeyError(product_id)


def delete_product(product_id: str) -> None:
    with _lock:
        products = load_products()
        remaining = [
            product
            for product in products
            if product["id"] != product_id
        ]

        if len(remaining) == len(products):
            raise KeyError(product_id)

        _save_products(remaining)


def set_in_shopping_list(
    product_ids: list[str],
    in_list: bool,
) -> list[dict]:
    with _lock:
        products = load_products()
        wanted = set(product_ids)
        for product in products:
            if product["id"] not in wanted:
                continue

            if in_list and not product["in_shopping_list"]:
                product["added_to_list_at"] = _now()

            if not in_list:
                product["added_to_list_at"] = None

            product["in_shopping_list"] = in_list

        _save_products(products)

    return products


def to_watch_item(product: dict) -> WatchItem:
    return WatchItem(
        id=product["id"],
        category=product["category"],
        label=product["label"],
        search_term=product["search_term"],
        required_words=product["required_words"],
        excluded_words=product.get("excluded_words", []),
        match_start=product.get("match_start", False),
    )


def shopping_list_items() -> list[WatchItem]:
    return [
        to_watch_item(product)
        for product in load_products()
        if product["in_shopping_list"]
    ]


# ============================================================
# SETTINGS AND LAST SEARCH
# ============================================================


def load_settings() -> dict:
    with _lock:
        stored = _read_json(SETTINGS_FILE, {})

    return {**DEFAULT_SETTINGS, **stored}


def save_settings(payload: dict) -> dict:
    settings = load_settings()

    for key in DEFAULT_SETTINGS:
        if key in payload:
            settings[key] = payload[key]

    settings["latitude"] = float(settings["latitude"])
    settings["longitude"] = float(settings["longitude"])
    settings["kaufland_radius_km"] = float(
        settings["kaufland_radius_km"]
    )
    settings["enabled_stores"] = [
        store
        for store in STORES
        if store in settings["enabled_stores"]
    ]

    with _lock:
        _write_json(SETTINGS_FILE, settings)

    return settings


def load_last_search() -> dict | None:
    with _lock:
        return _read_json(LAST_SEARCH_FILE, None)


def save_last_search(report: dict) -> None:
    with _lock:
        _write_json(LAST_SEARCH_FILE, report)
