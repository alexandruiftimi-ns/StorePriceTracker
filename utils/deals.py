from collections import defaultdict

from models.product import Product


def group_deals_by_store(
    products: list[Product],
) -> dict[str, list[Product]]:
    deals_by_store: dict[str, list[Product]] = defaultdict(list)

    for product in products:
        if product.on_sale:
            deals_by_store[product.store].append(product)

    for store_products in deals_by_store.values():
        store_products.sort(
            key=lambda product: (
                -(
                    product.discount_percent
                    if product.discount_percent is not None
                    else 0
                ),
                (
                    product.unit_price
                    if product.unit_price is not None
                    else product.price
                ),
            )
        )

    return dict(deals_by_store)