from collections import defaultdict

from models.product import Product


def get_comparison_price(
    product: Product,
) -> float:
    """
    Compare products using their unit price.

    Products without a unit price cannot be compared fairly
    against products priced per kg or per liter, so they are
    pushed to the bottom.
    """
    if product.unit_price is not None:
        return product.unit_price

    return float("inf")


def group_products_by_watch_label(
    products: list[Product],
) -> dict[str, list[Product]]:
    products_by_label: dict[
        str,
        list[Product],
    ] = defaultdict(list)

    for product in products:
        products_by_label[
            product.watch_label
        ].append(product)

    for label_products in products_by_label.values():
        label_products.sort(
            key=get_comparison_price
        )

    return dict(products_by_label)


def get_best_products_by_store(
    products: list[Product],
) -> dict[str, list[Product]]:
    """
    Keep only the cheapest comparable product from each store
    for every watchlist category.
    """
    products_by_label = group_products_by_watch_label(
        products
    )

    best_products: dict[
        str,
        list[Product],
    ] = {}

    for label, label_products in products_by_label.items():
        cheapest_by_store: dict[
            str,
            Product,
        ] = {}

        for product in label_products:
            # Skip products without a usable price/kg or price/l.
            if product.unit_price is None:
                continue

            store_key = product.store.lower()

            existing_product = cheapest_by_store.get(
                store_key
            )

            if existing_product is None:
                cheapest_by_store[
                    store_key
                ] = product
                continue

            if (
                get_comparison_price(product)
                < get_comparison_price(
                    existing_product
                )
            ):
                cheapest_by_store[
                    store_key
                ] = product

        ranked_products = list(
            cheapest_by_store.values()
        )

        ranked_products.sort(
            key=get_comparison_price
        )

        # Only include categories that have at least one
        # fairly comparable product.
        if ranked_products:
            best_products[label] = ranked_products

    return best_products