import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from models.product import Product
from models.watch_item import WatchItem
from stores.auchan import search_auchan_api
from stores.kaufland import (
    load_kaufland_offers,
    search_kaufland_offers,
    search_kaufland_prices,
)
from stores.lidl import (
    load_lidl_dataframe_cached,
    search_lidl,
    search_lidl_offers,
)
from utils.http import create_session


ProgressCallback = Callable[[int, int, str], None]

MAX_WORKERS = 6


class ScanResult:
    def __init__(self) -> None:
        self.products: list[Product] = []
        # "Store: what failed" -> error text, shown in the UI.
        self.errors: dict[str, str] = {}
        self._lock = threading.Lock()

    def add(self, products: list[Product]) -> None:
        with self._lock:
            self.products.extend(products)

    def add_error(self, key: str, error: Exception) -> None:
        with self._lock:
            self.errors[key] = f"{type(error).__name__}: {error}"


def _shared_sources(
    enabled_stores: list[str],
    result: ScanResult,
) -> dict:
    """
    Downloads each store-wide file once per scan instead of
    once per product.
    """
    sources: dict = {}

    if "Lidl" in enabled_stores:
        try:
            sources["lidl_dataframe"] = load_lidl_dataframe_cached()
        except Exception as error:
            result.add_error("Lidl: daily price file", error)

    if "Kaufland" in enabled_stores:
        try:
            sources["kaufland_offers"] = load_kaufland_offers()
        except Exception as error:
            result.add_error("Kaufland: weekly offers", error)

    return sources


def _build_tasks(
    watch_items: list[WatchItem],
    settings: dict,
    sources: dict,
) -> list[tuple[str, WatchItem, Callable[[], list[Product]]]]:
    enabled_stores = settings["enabled_stores"]
    tasks = []

    for item in watch_items:
        if "Auchan" in enabled_stores:
            tasks.append(
                (
                    "Auchan",
                    item,
                    lambda item=item: search_auchan_api(
                        item,
                        session=create_session(),
                    ),
                )
            )

        if "Lidl" in enabled_stores:
            if "lidl_dataframe" in sources:
                tasks.append(
                    (
                        "Lidl",
                        item,
                        lambda item=item: search_lidl(
                            dataframe=sources["lidl_dataframe"],
                            watch_item=item,
                        ),
                    )
                )

            tasks.append(
                (
                    "Lidl offers",
                    item,
                    lambda item=item: search_lidl_offers(
                        item,
                        session=create_session(),
                    ),
                )
            )

        if "Kaufland" in enabled_stores:
            tasks.append(
                (
                    "Kaufland",
                    item,
                    lambda item=item: search_kaufland_prices(
                        item,
                        latitude=settings["latitude"],
                        longitude=settings["longitude"],
                        radius_km=settings["kaufland_radius_km"],
                        session=create_session(),
                    ),
                )
            )

            if "kaufland_offers" in sources:
                tasks.append(
                    (
                        "Kaufland offers",
                        item,
                        lambda item=item: search_kaufland_offers(
                            item,
                            sources["kaufland_offers"],
                        ),
                    )
                )

    return tasks


def run_scan(
    watch_items: list[WatchItem],
    settings: dict,
    progress: ProgressCallback | None = None,
) -> ScanResult:
    result = ScanResult()

    def report(done: int, total: int, message: str) -> None:
        if progress is not None:
            progress(done, total, message)

    report(0, 1, "Downloading Lidl daily prices and Kaufland offers…")

    sources = _shared_sources(settings["enabled_stores"], result)
    tasks = _build_tasks(watch_items, settings, sources)
    total = len(tasks)

    report(0, total, "Searching stores…")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(search): (source, item)
            for source, item, search in tasks
        }

        for done, future in enumerate(as_completed(futures), start=1):
            source, item = futures[future]

            try:
                result.add(future.result())

            except Exception as error:
                result.add_error(f"{source}: {item.label}", error)

            report(done, total, f"{source} · {item.label}")

    if not settings.get("include_loyalty_prices", True):
        result.products = [
            product
            for product in result.products
            if not product.loyalty_card
        ]

    return result
