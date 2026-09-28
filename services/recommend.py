from collections import Counter
from dataclasses import asdict
from datetime import datetime

from models.product import Product
from models.watch_item import WatchItem


PRODUCTS_SHOWN_PER_ITEM = 20

SUSPECT_PRICE_RATIO = 0.4


def _compare_unit(products: list[Product]) -> str | None:
    """
    Items are compared per kg or per liter when the stores
    report it; otherwise by package price.
    """
    units = Counter(
        product.unit
        for product in products
        if product.unit in {"kg", "l"}
        and product.unit_price is not None
    )

    if not units:
        return None

    return units.most_common(1)[0][0]


def _comparison_price(
    product: Product,
    compare_unit: str | None,
) -> float | None:
    if compare_unit is None:
        return product.price

    if product.unit == compare_unit and product.unit_price is not None:
        return product.unit_price

    return None


def _rank(
    products: list[Product],
    compare_unit: str | None,
) -> list[Product]:
    def key(product: Product):
        price = _comparison_price(product, compare_unit)

        return (
            price is None,
            price if price is not None else product.price,
        )

    return sorted(products, key=key)


def _to_dict(
    product: Product | None,
    compare_unit: str | None,
) -> dict | None:
    if product is None:
        return None

    return {
        **asdict(product),
        "comparison_price": _comparison_price(product, compare_unit),
    }


def _suspect_prices(
    products: list[Product],
    compare_unit: str | None,
) -> set[int]:
    """
    Flags unit prices far below the cheapest price at every
    other store. These are usually size parsing mistakes, e.g.
    "10X150G" priced per single tub, and must not win.
    """
    cheapest_by_store: dict[str, float] = {}

    for product in products:
        price = _comparison_price(product, compare_unit)

        if price is not None:
            cheapest_by_store[product.store] = min(
                price,
                cheapest_by_store.get(product.store, price),
            )

    suspects = set()

    for product in products:
        price = _comparison_price(product, compare_unit)

        other_prices = [
            store_price
            for store, store_price in cheapest_by_store.items()
            if store != product.store
        ]

        if (
            price is not None
            and other_prices
            and price < min(other_prices) * SUSPECT_PRICE_RATIO
        ):
            suspects.add(id(product))

    return suspects


def _analyse_item(
    item: WatchItem,
    products: list[Product],
    stores: list[str],
) -> dict:
    compare_unit = _compare_unit(products)
    ranked = _rank(products, compare_unit)
    suspects = _suspect_prices(products, compare_unit)

    comparable = [
        product
        for product in ranked
        if _comparison_price(product, compare_unit) is not None
        and id(product) not in suspects
    ]

    best = comparable[0] if comparable else None

    promos = [product for product in comparable if product.on_sale]
    best_promo = promos[0] if promos else None

    per_store = {}

    for store in stores:
        store_products = [
            product
            for product in comparable
            if product.store == store
        ]
        store_promos = [
            product
            for product in store_products
            if product.on_sale
        ]

        per_store[store] = {
            "count": sum(
                1 for product in products if product.store == store
            ),
            "best": _to_dict(
                store_products[0] if store_products else None,
                compare_unit,
            ),
            "promo": _to_dict(
                store_promos[0] if store_promos else None,
                compare_unit,
            ),
        }

    return {
        "id": item.id,
        "label": item.label,
        "category": item.category,
        "search_term": item.search_term,
        "compare_unit": compare_unit,
        "found": len(products),
        "best": _to_dict(best, compare_unit),
        "best_promo": _to_dict(best_promo, compare_unit),
        "cheapest_store": best.store if best else None,
        "per_store": per_store,
        "products": [
            {
                **_to_dict(product, compare_unit),
                "suspect_price": id(product) in suspects,
            }
            for product in ranked[:PRODUCTS_SHOWN_PER_ITEM]
        ],
    }


def _store_summary(store: str, items: list[dict]) -> dict:
    found = cheapest_wins = promo_items = promo_wins = 0
    discounts: list[float] = []
    price_ratios: list[float] = []

    for item in items:
        entry = item["per_store"][store]
        best = item["best"]

        if entry["best"] is None:
            continue

        found += 1

        if best and best["store"] == store:
            cheapest_wins += 1

            if best["on_sale"]:
                promo_wins += 1

        if entry["promo"] is not None:
            promo_items += 1

            if entry["promo"]["discount_percent"]:
                discounts.append(entry["promo"]["discount_percent"])

        if best and best["comparison_price"]:
            price_ratios.append(
                entry["best"]["comparison_price"]
                / best["comparison_price"]
            )

    return {
        "store": store,
        "found": found,
        "cheapest_wins": cheapest_wins,
        "promo_items": promo_items,
        "promo_wins": promo_wins,
        "total_discount": round(sum(discounts), 1),
        "average_discount": (
            round(sum(discounts) / len(discounts), 1)
            if discounts
            else None
        ),
        # 1.00 = always the cheapest; 1.15 = 15% above the
        # cheapest store on average.
        "price_index": (
            round(sum(price_ratios) / len(price_ratios), 3)
            if price_ratios
            else None
        ),
    }


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _recommend(
    summaries: list[dict],
    item_count: int,
) -> dict:
    candidates = [summary for summary in summaries if summary["found"]]

    if not candidates:
        return {"best": None, "second": None}

    def price_key(summary: dict):
        return (
            summary["cheapest_wins"],
            summary["found"],
            -(summary["price_index"] or 99),
        )

    any_promotions = any(summary["promo_items"] for summary in candidates)

    if any_promotions:
        best = max(
            candidates,
            key=lambda summary: (
                summary["promo_wins"],
                summary["promo_items"],
                summary["total_discount"],
                *price_key(summary),
            ),
        )

        parts = [
            f"{_plural(best['promo_items'], 'item')} of your "
            f"{item_count} on promotion"
        ]

        if best["promo_wins"]:
            parts.append(
                f"{best['promo_wins']} of those "
                f"{'is' if best['promo_wins'] == 1 else 'are'} "
                f"the lowest price anywhere"
            )

        if best["average_discount"]:
            parts.append(f"average discount {best['average_discount']:.0f}%")

        best_reason = "; ".join(parts) + "."

    else:
        best = max(candidates, key=price_key)
        best_reason = (
            "No promotions found for your list today, so this is "
            f"the cheapest store for {best['cheapest_wins']} of "
            f"your {item_count} items."
        )

    others = [summary for summary in candidates if summary is not best]

    second = None

    if others:
        second_summary = max(others, key=price_key)
        second_reason = (
            f"Cheapest price per kg/l for "
            f"{_plural(second_summary['cheapest_wins'], 'item')} "
            f"of your {item_count}"
        )

        if second_summary["price_index"]:
            above = (second_summary["price_index"] - 1) * 100
            second_reason += (
                f"; on average {above:.0f}% above the lowest price"
                if above >= 0.5
                else "; it matches the lowest price on average"
            )

        second = {
            "store": second_summary["store"],
            "reason": second_reason + ".",
        }

    return {
        "best": {"store": best["store"], "reason": best_reason},
        "second": second,
    }


def _shopping_plan(
    items: list[dict],
    recommendation: dict,
) -> dict[str, list[dict]]:
    """
    Splits the list between the two recommended stores: each
    item goes to whichever of the two is cheaper for it.
    Items neither store has go to their cheapest store.
    """
    chosen = [
        entry["store"]
        for entry in (recommendation["best"], recommendation["second"])
        if entry
    ]

    plan: dict[str, list[dict]] = {}

    for item in items:
        options = [
            item["per_store"][store]["best"]
            for store in chosen
            if item["per_store"][store]["best"] is not None
        ]

        if options:
            pick = min(options, key=lambda product: product["comparison_price"])

        elif item["best"] is not None:
            pick = item["best"]

        else:
            plan.setdefault("Not found", []).append(
                {"label": item["label"], "product": None}
            )
            continue

        best = item["best"]

        plan.setdefault(pick["store"], []).append(
            {
                "label": item["label"],
                "product": pick,
                # Worth knowing when a third store is cheaper.
                "cheaper_elsewhere": (
                    best
                    if best is not None
                    and best["store"] != pick["store"]
                    and best["comparison_price"] < pick["comparison_price"]
                    else None
                ),
            }
        )

    return plan


def build_report(
    watch_items: list[WatchItem],
    products: list[Product],
    stores: list[str],
    errors: dict[str, str] | None = None,
) -> dict:
    items = [
        _analyse_item(
            item,
            [
                product
                for product in products
                if product.watch_id == item.id
                or (not product.watch_id and product.watch_label == item.label)
            ],
            stores,
        )
        for item in watch_items
    ]

    summaries = [_store_summary(store, items) for store in stores]
    recommendation = _recommend(summaries, len(items))

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stores": stores,
        "items": items,
        "store_summaries": summaries,
        "recommendation": recommendation,
        "plan": _shopping_plan(items, recommendation),
        "errors": errors or {},
    }
