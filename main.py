"""
Command-line scan, e.g. for a scheduled task.

    python main.py          scan every product in data/products.json
    python main.py --list   scan only the shopping list

Prints the comparison, saves per-store history, and sends the
Telegram summaries (deals, best prices, changes since last run).
The web UI (python app.py) is the main way to use the tracker.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from services.recommend import build_report
from services.scanner import run_scan
from utils import catalog
from utils.best_prices import get_best_products_by_store
from utils.changes import detect_product_changes
from utils.deals import group_deals_by_store
from utils.storage import load_latest_products, save_products
from utils.telegram import (
    build_best_prices_message,
    build_changes_message,
    build_deals_message,
    build_shopping_report_message,
    is_configured,
    send_message,
)


def print_report(report: dict) -> None:
    print()
    print("=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)

    for title, key in (("Best market", "best"), ("Second best", "second")):
        entry = report["recommendation"].get(key)

        if entry:
            print(f"{title}: {entry['store']} — {entry['reason']}")

    for item in report["items"]:
        unit = item["compare_unit"]

        print()
        print("#" * 70)
        print(item["label"].upper())
        print("#" * 70)

        for store in report["stores"]:
            product = item["per_store"][store]["best"]

            if product is None:
                print(f"  {store:<9} not found")
                continue

            price = (
                f"{product['comparison_price']:.2f} lei/{unit}"
                if unit
                else f"{product['price']:.2f} lei"
            )
            promo = (
                f"  [{product['promo_label']}]"
                if product["on_sale"]
                else ""
            )
            marker = "★" if item["best"] and item["best"]["store"] == store else " "

            print(f"{marker} {store:<9} {price:<16} {product['name']}{promo}")

    for key, message in report["errors"].items():
        print(f"! {key}: {message}")


def send_telegram(report: dict, products, previous_products) -> None:
    if not is_configured():
        print("Telegram is not set up (Settings in the web app, or .env); skipping.")
        return

    send_message(build_shopping_report_message(report))

    deals_by_store = group_deals_by_store(products)

    if deals_by_store:
        send_message(build_deals_message(deals_by_store))

    best_products = get_best_products_by_store(products)

    if best_products:
        send_message(build_best_prices_message(best_products))

    changes = detect_product_changes(
        previous_products=previous_products,
        current_products=products,
    )

    if changes.has_changes():
        send_message(build_changes_message(changes))

    print("Telegram messages sent.")


def main() -> None:
    only_list = "--list" in sys.argv

    watch_items = (
        catalog.shopping_list_items()
        if only_list
        else [catalog.to_watch_item(p) for p in catalog.load_products()]
    )

    if not watch_items:
        print("Nothing to scan.")
        return

    settings = catalog.load_settings()
    stores = settings["enabled_stores"]

    previous_products = [
        product
        for store in stores
        for product in load_latest_products(store_name=store)
    ]

    result = run_scan(
        watch_items,
        settings,
        progress=lambda done, total, message: print(
            f"[{done}/{total}] {message}"
        ),
    )

    report = build_report(watch_items, result.products, stores, result.errors)

    print_report(report)
    send_telegram(report, result.products, previous_products)

    for store in stores:
        saved_file = save_products(
            products=[p for p in result.products if p.store == store],
            store_name=store,
        )
        print(f"{store} history saved to: {saved_file}")


if __name__ == "__main__":
    main()
