import re
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from models.product import Product
from models.watch_item import WatchItem
from utils.filtering import matches_watch_item
from utils.http import create_session
from utils.units import (
    parse_base_price,
    unit_price_from_quantity,
)


LIDL_BASE_URL = "https://www.lidl.ro"
LIDL_SEARCH_API = f"{LIDL_BASE_URL}/q/api/search"
OFFERS_PAGE_SIZE = 48
OFFERS_MAX_PAGES = 3


LIDL_PRICE_URL = (
    "https://www.lidl.ro/explore/assets/"
    "webPriceData/ro/preturiZilniceLidl.xlsb"
)

LIDL_PRICES_PAGE = (
    "https://www.lidl.ro/c/preturile-la-zi/s10019622"
)

TEMP_FOLDER = Path("data/temp")
TEMP_FILE = TEMP_FOLDER / "preturiZilniceLidl.xlsb"

SHEET_NAME = "EPEL"

REQUIRED_COLUMNS = {
    "Denumire comerciala",
    "Gramaj",
    "Categorie",
    "Pret vanzare",
}


def download_lidl_price_file() -> Path:
    TEMP_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Downloading Lidl daily price file...")

    response = requests.get(
        LIDL_PRICE_URL,
        timeout=60,
    )

    response.raise_for_status()

    TEMP_FILE.write_bytes(
        response.content
    )

    print(
        f"Lidl file downloaded: {TEMP_FILE}"
    )

    return TEMP_FILE


def parse_lidl_price(
    value: object,
) -> float | None:
    if value is None:
        return None

    if isinstance(
        value,
        (int, float),
    ):
        return float(value)

    text = (
        str(value)
        .lower()
        .replace("lei", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )

    try:
        return float(text)
    except ValueError:
        return None


def normalize_weight_text(
    weight_text: object,
) -> str:
    if weight_text is None:
        return ""

    return (
        str(weight_text)
        .lower()
        .replace(",", ".")
        .replace(" ", "")
        .strip()
    )


def calculate_unit_price(
    package_price: float,
    weight_text: object,
) -> tuple[float | None, str | None]:
    normalized = normalize_weight_text(
        weight_text
    )

    if not normalized:
        return None, None

    if normalized in {
        "perkg",
        "kg",
        "1kg",
        "1.0kg",
    }:
        return package_price, "kg"

    if normalized in {
        "perl",
        "1l",
        "1.0l",
    }:
        return package_price, "l"

    multipack_match = re.fullmatch(
        r"(\d+)x(\d+(?:\.\d+)?)(kg|g|l|ml)",
        normalized,
    )

    if multipack_match:
        item_count = int(
            multipack_match.group(1)
        )

        item_size = float(
            multipack_match.group(2)
        )

        source_unit = multipack_match.group(3)

        total_size = item_count * item_size

        if total_size <= 0:
            return None, None

        if source_unit == "kg":
            return (
                round(
                    package_price / total_size,
                    2,
                ),
                "kg",
            )

        if source_unit == "g":
            kilograms = total_size / 1000

            return (
                round(
                    package_price / kilograms,
                    2,
                ),
                "kg",
            )

        if source_unit == "l":
            return (
                round(
                    package_price / total_size,
                    2,
                ),
                "l",
            )

        if source_unit == "ml":
            liters = total_size / 1000

            return (
                round(
                    package_price / liters,
                    2,
                ),
                "l",
            )

    single_size_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)(kg|g|l|ml)",
        normalized,
    )

    if not single_size_match:
        return None, None

    size = float(
        single_size_match.group(1)
    )

    source_unit = single_size_match.group(2)

    if size <= 0:
        return None, None

    if source_unit == "kg":
        return (
            round(
                package_price / size,
                2,
            ),
            "kg",
        )

    if source_unit == "g":
        kilograms = size / 1000

        return (
            round(
                package_price / kilograms,
                2,
            ),
            "kg",
        )

    if source_unit == "l":
        return (
            round(
                package_price / size,
                2,
            ),
            "l",
        )

    if source_unit == "ml":
        liters = size / 1000

        return (
            round(
                package_price / liters,
                2,
            ),
            "l",
        )

    return None, None


def read_lidl_dataframe(
    file_path: Path,
) -> pd.DataFrame:
    with pd.ExcelFile(
        file_path,
        engine="pyxlsb",
    ) as excel_file:
        dataframe = pd.read_excel(
            excel_file,
            sheet_name=SHEET_NAME,
        )

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    missing_columns = (
        REQUIRED_COLUMNS
        - set(dataframe.columns)
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        raise RuntimeError(
            "Lidl file is missing columns: "
            f"{missing_text}"
        )

    return dataframe


def load_lidl_dataframe() -> pd.DataFrame:
    file_path = download_lidl_price_file()

    try:
        return read_lidl_dataframe(
            file_path
        )

    finally:
        file_path.unlink(
            missing_ok=True
        )

        print(
            "Temporary Lidl file deleted."
        )


_daily_cache: dict[date, pd.DataFrame] = {}


def load_lidl_dataframe_cached() -> pd.DataFrame:
    """
    The file only changes once a day, so reuse it for every
    search made on the same day.
    """
    today = date.today()

    if today not in _daily_cache:
        _daily_cache.clear()
        _daily_cache[today] = load_lidl_dataframe()

    return _daily_cache[today]


def search_lidl(
    dataframe: pd.DataFrame,
    watch_item: WatchItem,
    validation_mode: bool = False,
) -> list[Product]:
    results: list[Product] = []

    accepted_count = 0
    rejected_count = 0
    rejection_reasons: dict[str, int] = {}

    print(
        f"Searching Lidl for: "
        f"{watch_item.search_term}"
    )

    for _, row in dataframe.iterrows():
        raw_name = row[
            "Denumire comerciala"
        ]

        if pd.isna(raw_name):
            continue

        # Names in the file start with "- ".
        product_name = str(
            raw_name
        ).strip().lstrip("-").strip()

        is_match, reason = (
            matches_watch_item(
                product_name=product_name,
                watch_item=watch_item,
            )
        )

        if not is_match:
            rejected_count += 1

            rejection_reasons[reason] = (
                rejection_reasons.get(
                    reason,
                    0,
                )
                + 1
            )

            continue

        product_price = parse_lidl_price(
            row["Pret vanzare"]
        )

        if product_price is None:
            continue

        weight_text = row["Gramaj"]

        unit_price, unit = (
            calculate_unit_price(
                package_price=product_price,
                weight_text=weight_text,
            )
        )

        accepted_count += 1

        if validation_mode:
            print(
                f"Accepted: {product_name}"
            )
            print(
                f"Weight: {weight_text}"
            )
            print(
                f"Price: {product_price:.2f} lei"
            )

            if (
                unit_price is not None
                and unit is not None
            ):
                print(
                    f"Unit price: "
                    f"{unit_price:.2f} lei/{unit}"
                )

            print()

        results.append(
            Product(
                name=product_name,
                price=product_price,
                store="Lidl",
                url=LIDL_PRICES_PAGE,
                watch_label=watch_item.label,
                watch_id=watch_item.id or None,
                unit_price=unit_price,
                unit=unit,
                old_price=None,
                discount_percent=None,
                on_sale=False,
                package=(
                    str(weight_text)
                    if not pd.isna(weight_text)
                    else None
                ),
                source="Lidl daily prices",
                branch="All Lidl stores (national price list)",
            )
        )

    if validation_mode:
        print()
        print("-" * 60)
        print(
            f"Lidl validation summary: "
            f"{watch_item.label}"
        )
        print("-" * 60)
        print(
            f"Accepted: {accepted_count}"
        )
        print(
            f"Rejected: {rejected_count}"
        )

        if rejection_reasons:
            print()
            print("Top rejection reasons:")

            sorted_reasons = sorted(
                rejection_reasons.items(),
                key=lambda item: item[1],
                reverse=True,
            )

            for reason, count in (
                sorted_reasons[:10]
            ):
                print(
                    f"- {reason}: {count}"
                )

        print()

    return results

# ============================================================
# CURRENT OFFERS (lidl.ro search API)
# ============================================================
# The daily price file only lists regular prices. Promotions,
# including Lidl Plus prices, come from the website search.


def _offer_unit_price(
    price: float,
    *texts: object,
) -> tuple[float | None, str | None]:
    for text in texts:
        unit_price, unit = parse_base_price(text)

        if unit_price is not None:
            return unit_price, unit

    for text in texts:
        unit_price, unit = unit_price_from_quantity(price, text)

        if unit_price is not None:
            return unit_price, unit

    return None, None


def _parse_offer(
    data: dict,
    watch_item: WatchItem,
) -> Product | None:
    product_name = (
        data.get("fullTitle")
        or data.get("title")
        or ""
    ).strip()

    price_info = data.get("price") or {}
    lidl_plus = (data.get("lidlPlus") or [None])[0]

    loyalty_card = None
    promo_label = None
    old_price = None

    if lidl_plus and (lidl_plus.get("price") or {}).get("price"):
        # Lidl Plus offer: the card price is the deal and the
        # "Fără Lidl Plus 21,49 lei" text is the normal price.
        plus_price = lidl_plus["price"]
        price = float(plus_price["price"])
        packaging = (plus_price.get("packaging") or {}).get("text")
        base_text = (plus_price.get("basePrice") or {}).get("text")
        loyalty_card = "Lidl Plus"
        promo_label = lidl_plus.get("highlightText") or "Lidl Plus"

        without_card = re.search(
            r"(\d+(?:[.,]\d+)?)\s*lei",
            base_text or "",
        )

        if without_card:
            old_price = float(
                without_card.group(1).replace(",", ".")
            )

        base_text = None

    elif price_info.get("price"):
        price = float(price_info["price"])
        packaging = (price_info.get("packaging") or {}).get("text")
        base_text = (price_info.get("basePrice") or {}).get("text")
        discount = price_info.get("discount") or {}

        old_price = (
            price_info.get("oldPrice")
            or discount.get("deletedPrice")
        )

        if discount.get("percentageDiscount"):
            promo_label = f"-{discount['percentageDiscount']}%"

    else:
        # Listed on the site but not on offer this week.
        return None

    unit_price, unit = _offer_unit_price(
        price,
        base_text,
        packaging,
        product_name,
    )

    on_sale = (
        old_price is not None
        and float(old_price) > price
    ) or loyalty_card is not None

    discount_percent = None

    if old_price is not None and float(old_price) > price:
        discount_percent = round(
            (float(old_price) - price) / float(old_price) * 100,
            1,
        )

    if on_sale and promo_label is None:
        promo_label = (
            f"-{discount_percent:.0f}%"
            if discount_percent
            else "Offer"
        )

    canonical_url = data.get("canonicalUrl") or ""

    return Product(
        name=product_name,
        price=price,
        store="Lidl",
        url=(
            f"{LIDL_BASE_URL}{canonical_url}"
            if canonical_url.startswith("/")
            else LIDL_BASE_URL
        ),
        watch_label=watch_item.label,
        watch_id=watch_item.id or None,
        unit_price=unit_price,
        unit=unit,
        old_price=float(old_price) if on_sale and old_price else None,
        discount_percent=discount_percent,
        on_sale=on_sale,
        promo_label=promo_label,
        loyalty_card=loyalty_card,
        package=packaging,
        source="lidl.ro offers",
        branch="All Lidl stores (lidl.ro offer)",
    )


def search_lidl_offers(
    watch_item: WatchItem,
    session=None,
) -> list[Product]:
    session = session or create_session()
    results: list[Product] = []

    for page_index in range(OFFERS_MAX_PAGES):
        response = session.get(
            LIDL_SEARCH_API,
            params={
                "q": watch_item.search_term,
                "assortment": "RO",
                "locale": "ro_RO",
                "version": "v2.0.0",
                "fetchsize": OFFERS_PAGE_SIZE,
                "offset": page_index * OFFERS_PAGE_SIZE,
            },
            headers={"Accept": "*/*"},
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()
        items = payload.get("items") or []

        for item in items:
            data = (item.get("gridbox") or {}).get("data") or {}
            product_name = data.get("fullTitle") or data.get("title")

            if not product_name:
                continue

            is_match, _ = matches_watch_item(
                product_name=product_name,
                watch_item=watch_item,
            )

            if not is_match:
                continue

            product = _parse_offer(data, watch_item)

            if product is not None:
                results.append(product)

        fetched = (page_index + 1) * OFFERS_PAGE_SIZE

        if not items or fetched >= payload.get("numFound", 0):
            break

    return results
