import re
import unicodedata
from dataclasses import dataclass, field

from models.product import Product


@dataclass
class ProductChanges:
    new_products: list[Product] = field(default_factory=list)
    missing_products: list[Product] = field(default_factory=list)

    new_promotions: list[Product] = field(default_factory=list)
    ended_promotions: list[Product] = field(default_factory=list)

    price_drops: list[tuple[Product, Product]] = field(
        default_factory=list
    )

    price_increases: list[tuple[Product, Product]] = field(
        default_factory=list
    )

    def has_changes(self) -> bool:
        return any(
            [
                self.new_products,
                self.missing_products,
                self.new_promotions,
                self.ended_promotions,
                self.price_drops,
                self.price_increases,
            ]
        )


def normalize_product_name(name: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        name,
    )

    without_accents = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized_name = without_accents.lower()

    normalized_name = re.sub(
        r"[^a-z0-9]+",
        " ",
        normalized_name,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized_name,
    ).strip()


def product_key(
    product: Product,
) -> tuple[str, str]:
    return (
        product.store.lower(),
        normalize_product_name(product.name),
    )


def detect_product_changes(
    previous_products: list[Product],
    current_products: list[Product],
) -> ProductChanges:
    changes = ProductChanges()

    previous_by_key = {
        product_key(product): product
        for product in previous_products
    }

    current_by_key = {
        product_key(product): product
        for product in current_products
    }

    for key, current_product in current_by_key.items():
        previous_product = previous_by_key.get(key)

        if previous_product is None:
            changes.new_products.append(
                current_product
            )

            if current_product.on_sale:
                changes.new_promotions.append(
                    current_product
                )

            continue

        price_difference = (
            current_product.price
            - previous_product.price
        )

        if price_difference < -0.01:
            changes.price_drops.append(
                (
                    previous_product,
                    current_product,
                )
            )

        elif price_difference > 0.01:
            changes.price_increases.append(
                (
                    previous_product,
                    current_product,
                )
            )

        if (
            not previous_product.on_sale
            and current_product.on_sale
        ):
            changes.new_promotions.append(
                current_product
            )

        elif (
            previous_product.on_sale
            and not current_product.on_sale
        ):
            changes.ended_promotions.append(
                current_product
            )

    for key, previous_product in previous_by_key.items():
        if key not in current_by_key:
            changes.missing_products.append(
                previous_product
            )

            if previous_product.on_sale:
                changes.ended_promotions.append(
                    previous_product
                )

    return changes