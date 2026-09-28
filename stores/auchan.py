import re
from urllib.parse import quote

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from models.product import Product
from models.watch_item import WatchItem
from utils.filtering import matches_watch_item
from utils.http import create_session
from utils.units import unit_price_from_quantity


AUCHAN_BASE_URL = "https://www.auchan.ro"

AUCHAN_SEARCH_API = (
    f"{AUCHAN_BASE_URL}/api/io/_v/api/"
    "intelligent-search/product_search/"
)

API_PAGE_SIZE = 50
API_MAX_PAGES = 4

PRODUCT_SELECTOR = "article.vtex-product-summary-2-x-element"

SHOW_MORE_SELECTOR = (
    ".vtex-search-result-3-x-buttonShowMore--fetchMore button"
)

UNIT_PRICE_SELECTORS = [
    ".auchan-store-theme-4-x-pricePerKgValue",
    "[class*='pricePerKgValue']",
    "[class*='pricePerUnit']",
]


def parse_price(price_text: str) -> float | None:
    match = re.search(
        r"(\d+(?:[.,]\d{1,2})?)",
        price_text.replace(" ", ""),
    )

    if match is None:
        return None

    normalized_price = (
        match.group(1)
        .replace(",", ".")
    )

    try:
        return float(normalized_price)
    except ValueError:
        return None


def parse_unit(unit_price_text: str) -> str | None:
    normalized_text = (
        unit_price_text
        .lower()
        .replace(" ", "")
    )

    if "lei/kg" in normalized_text:
        return "kg"

    if "lei/l" in normalized_text:
        return "l"

    if "lei/buc" in normalized_text:
        return "piece"

    return None


def extract_unit_price_text(product) -> str:
    """
    First try known CSS selectors.

    If Auchan uses another structure for a particular card,
    search the full card text for values such as:
    44,78 lei/kg
    7,99 lei/l
    """
    for selector in UNIT_PRICE_SELECTORS:
        locator = product.locator(selector).first

        if locator.count() > 0:
            text = " ".join(
                locator.inner_text().split()
            )

            if parse_unit(text) is not None:
                return text

    product_text = " ".join(
        product.inner_text().split()
    )

    unit_price_match = re.search(
        r"\d+(?:[.,]\d{1,2})?\s*lei\s*/\s*"
        r"(?:kg|l|buc)",
        product_text,
        flags=re.IGNORECASE,
    )

    if unit_price_match:
        return unit_price_match.group(0)

    return ""


def load_all_products(page: Page) -> None:
    products = page.locator(PRODUCT_SELECTOR)
    show_more_button = page.locator(
        SHOW_MORE_SELECTOR
    )

    while True:
        page.mouse.wheel(0, 2500)
        page.wait_for_timeout(800)

        if show_more_button.count() == 0:
            break

        if not show_more_button.is_visible():
            break

        product_count_before = products.count()

        try:
            show_more_button.scroll_into_view_if_needed()
            show_more_button.click(
                timeout=10000,
            )

        except PlaywrightTimeoutError:
            print(
                "Could not click 'Arată mai mult'."
            )
            break

        try:
            page.wait_for_function(
                """
                ([selector, previousCount]) => {
                    return document
                        .querySelectorAll(selector)
                        .length > previousCount;
                }
                """,
                arg=[
                    PRODUCT_SELECTOR,
                    product_count_before,
                ],
                timeout=15000,
            )

        except PlaywrightTimeoutError:
            page.wait_for_timeout(1500)

        product_count_after = products.count()

        print(
            "Loaded more products: "
            f"{product_count_before} -> "
            f"{product_count_after}"
        )

        if product_count_after <= product_count_before:
            break

        found_unavailable = False

        for index in range(
            product_count_before,
            product_count_after,
        ):
            new_product = products.nth(index)

            unavailable_text = new_product.locator(
                ".vtex-product-availability-0-x-"
                "unavailableText"
            )

            product_text = (
                new_product
                .inner_text()
                .lower()
            )

            if (
                unavailable_text.count() > 0
                or "indisponibil" in product_text
            ):
                found_unavailable = True
                break

        if found_unavailable:
            print(
                "Unavailable products reached. "
                "Stopping further loading."
            )
            break


def search_auchan(
    page: Page,
    watch_item: WatchItem,
    validation_mode: bool = False,
) -> list[Product]:
    encoded_term = quote(
        watch_item.search_term
    )

    search_url = (
        f"https://www.auchan.ro/{encoded_term}"
        f"?_q={encoded_term}"
        f"&map=ft"
        f"&order=OrderByBestDiscountDESC"
    )

    results: list[Product] = []

    accepted_count = 0
    rejected_count = 0
    rejection_reasons: dict[str, int] = {}

    print(
        "Searching Auchan for: "
        f"{watch_item.search_term}"
    )

    page.goto(
        search_url,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    try:
        page.wait_for_load_state(
            "networkidle",
            timeout=30000,
        )

    except PlaywrightTimeoutError:
        print(
            "Page stayed busy, continuing anyway..."
        )

    try:
        page.wait_for_selector(
            PRODUCT_SELECTOR,
            timeout=30000,
        )

    except PlaywrightTimeoutError:
        print(
            "No Auchan products were found."
        )
        return results

    load_all_products(page)

    products = page.locator(PRODUCT_SELECTOR)
    product_count = products.count()

    print(
        f"Total products loaded: {product_count}"
    )

    for index in range(product_count):
        product = products.nth(index)

        name_locator = product.locator(
            ".vtex-product-summary-2-x-"
            "productBrand"
        ).first

        price_locator = product.locator(
            ".vtex-product-price-1-x-"
            "currencyContainer"
        ).first

        old_price_locator = product.locator(
            ".vtex-product-price-1-x-listPrice"
        ).first

        link_locator = product.locator(
            "a[href]"
        ).first

        if name_locator.count() == 0:
            continue

        product_name = (
            name_locator
            .inner_text()
            .strip()
        )

        is_match, reason = matches_watch_item(
            product_name=product_name,
            watch_item=watch_item,
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

            if validation_mode:
                print(
                    f"Rejected: {product_name}"
                )
                print(
                    f"Reason: {reason}"
                )
                print()

            continue

        accepted_count += 1

        if validation_mode:
            print(
                f"Accepted: {product_name}"
            )

        price_text = (
            " ".join(
                price_locator
                .inner_text()
                .split()
            )
            if price_locator.count() > 0
            else ""
        )

        product_price = parse_price(
            price_text
        )

        if product_price is None:
            continue

        old_price_text = (
            " ".join(
                old_price_locator
                .inner_text()
                .split()
            )
            if old_price_locator.count() > 0
            else ""
        )

        old_price = parse_price(
            old_price_text
        )

        unit_price_text = (
            extract_unit_price_text(
                product
            )
        )

        unit_price = parse_price(
            unit_price_text
        )

        unit = parse_unit(
            unit_price_text
        )

        on_sale = (
            old_price is not None
            and old_price > product_price
        )

        discount_percent = None

        if on_sale:
            discount_percent = round(
                (
                    (
                        old_price
                        - product_price
                    )
                    / old_price
                )
                * 100,
                1,
            )

        product_url = None

        if link_locator.count() > 0:
            product_url = (
                link_locator
                .get_attribute("href")
            )

        if (
            product_url
            and product_url.startswith("/")
        ):
            product_url = (
                "https://www.auchan.ro"
                f"{product_url}"
            )

        if not product_url:
            product_url = search_url

        # This must be outside the product_url fallback.
        results.append(
            Product(
                name=product_name,
                price=product_price,
                store="Auchan",
                url=product_url,
                watch_label=watch_item.label,
                unit_price=unit_price,
                unit=unit,
                old_price=old_price,
                discount_percent=(
                    discount_percent
                ),
                on_sale=on_sale,
            )
        )

    if validation_mode:
        print()
        print("-" * 60)
        print(
            "Validation summary: "
            f"{watch_item.label}"
        )
        print("-" * 60)
        print(
            "Products inspected: "
            f"{accepted_count + rejected_count}"
        )
        print(
            f"Accepted: {accepted_count}"
        )
        print(
            f"Rejected: {rejected_count}"
        )

        if rejection_reasons:
            print()
            print("Rejection reasons:")

            sorted_reasons = sorted(
                rejection_reasons.items(),
                key=lambda item: item[1],
                reverse=True,
            )

            for reason, count in sorted_reasons:
                print(
                    f"- {reason}: {count}"
                )

        print()

    return results

# ============================================================
# JSON API SEARCH
# ============================================================
# Auchan runs on VTEX, whose search API returns the same data
# as the web page without opening a browser. search_auchan()
# above remains as a fallback if the API stops working.


def _parse_api_product(
    raw_product: dict,
    watch_item: WatchItem,
) -> Product | None:
    items = raw_product.get("items") or []

    if not items:
        return None

    item = items[0]
    sellers = item.get("sellers") or []

    if not sellers:
        return None

    offer = sellers[0].get("commertialOffer") or {}

    price = offer.get("Price")
    list_price = offer.get("ListPrice")

    if not price or offer.get("AvailableQuantity", 0) <= 0:
        return None

    product_name = raw_product.get("productName", "").strip()
    measurement_unit = (item.get("measurementUnit") or "").lower()
    multiplier = item.get("unitMultiplier") or 1

    if measurement_unit in {"kg", "l"}:
        # Sold by weight: Price is already lei/kg and the
        # package costs Price x unitMultiplier.
        unit_price = round(price, 2)
        unit = measurement_unit
        package_price = round(price * multiplier, 2)
        old_package_price = (
            round(list_price * multiplier, 2)
            if list_price
            else None
        )
        package = f"~{multiplier:g} {measurement_unit}"

    else:
        package_price = round(price, 2)
        old_package_price = list_price
        unit_price, unit = unit_price_from_quantity(
            package_price,
            product_name,
        )
        package = None

    on_sale = (
        old_package_price is not None
        and old_package_price > package_price + 0.009
    )

    discount_percent = None

    if on_sale:
        discount_percent = round(
            (old_package_price - package_price)
            / old_package_price
            * 100,
            1,
        )

    link = raw_product.get("link") or ""

    return Product(
        name=product_name,
        price=package_price,
        store="Auchan",
        url=(
            f"{AUCHAN_BASE_URL}{link}"
            if link.startswith("/")
            else link or AUCHAN_BASE_URL
        ),
        watch_label=watch_item.label,
        watch_id=watch_item.id or None,
        unit_price=unit_price,
        unit=unit,
        old_price=old_package_price if on_sale else None,
        discount_percent=discount_percent,
        on_sale=on_sale,
        promo_label=(
            f"-{discount_percent:.0f}%"
            if on_sale
            else None
        ),
        package=package,
        source="auchan.ro",
    )


def search_auchan_api(
    watch_item: WatchItem,
    session=None,
) -> list[Product]:
    session = session or create_session()

    results: list[Product] = []
    seen_names: set[str] = set()

    for page_number in range(1, API_MAX_PAGES + 1):
        response = session.get(
            AUCHAN_SEARCH_API,
            params={
                "query": watch_item.search_term,
                "count": API_PAGE_SIZE,
                "page": page_number,
                "locale": "ro-RO",
            },
            timeout=30,
        )

        response.raise_for_status()

        raw_products = response.json().get("products") or []

        for raw_product in raw_products:
            product_name = raw_product.get("productName", "")

            if product_name in seen_names:
                continue

            seen_names.add(product_name)

            is_match, _ = matches_watch_item(
                product_name=product_name,
                watch_item=watch_item,
            )

            if not is_match:
                continue

            product = _parse_api_product(
                raw_product,
                watch_item,
            )

            if product is not None:
                results.append(product)

        if len(raw_products) < API_PAGE_SIZE:
            break

    return results
