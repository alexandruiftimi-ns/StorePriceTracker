from stores.lidl import search_lidl
from watchlist import WATCHLIST


chicken_watch_item = next(
    item
    for item in WATCHLIST
    if item.label == "Chicken breast"
)

products = search_lidl(
    watch_item=chicken_watch_item,
    validation_mode=True,
)

products.sort(
    key=lambda product: (
        product.unit_price
        if product.unit_price is not None
        else float("inf")
    )
)

print()
print(
    f"Matching Lidl products: "
    f"{len(products)}"
)
print()

for product in products:
    print(product.name)
    print(
        f"Package price: "
        f"{product.price:.2f} lei"
    )

    if (
        product.unit_price is not None
        and product.unit is not None
    ):
        print(
            f"Unit price: "
            f"{product.unit_price:.2f} "
            f"lei/{product.unit}"
        )

    print()