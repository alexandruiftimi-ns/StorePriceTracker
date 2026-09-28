from dataclasses import dataclass


@dataclass
class Product:
    name: str
    price: float
    store: str
    url: str

    # Which watchlist item this belongs to
    watch_label: str

    unit_price: float | None = None
    unit: str | None = None

    old_price: float | None = None
    discount_percent: float | None = None

    on_sale: bool = False

    # Extra details shown in the UI. Defaults keep older
    # history files loadable.
    watch_id: str | None = None
    promo_label: str | None = None
    loyalty_card: str | None = None
    package: str | None = None
    source: str | None = None
