from models.product import Product


def compare_prices(
    previous_products: list[Product],
    current_products: list[Product],
) -> None:
    previous_by_name = {
        product.name: product
        for product in previous_products
    }

    print()
    print("=" * 60)
    print("PRICE CHANGES")
    print("=" * 60)

    changes_found = False

    for current_product in current_products:
        previous_product = previous_by_name.get(
            current_product.name
        )

        if previous_product is None:
            continue

        price_difference = (
            current_product.price
            - previous_product.price
        )

        if abs(price_difference) < 0.01:
            continue

        changes_found = True

        percentage_change = (
            price_difference
            / previous_product.price
        ) * 100

        print()
        print(current_product.name)

        if price_difference < 0:
            print("Price dropped")
        else:
            print("Price increased")

        print(
            f"Previous: "
            f"{previous_product.price:.2f} lei"
        )
        print(
            f"Current: "
            f"{current_product.price:.2f} lei"
        )
        print(
            f"Difference: "
            f"{price_difference:+.2f} lei"
        )
        print(
            f"Change: "
            f"{percentage_change:+.1f}%"
        )

    if not changes_found:
        print()
        print("No price changes found.")