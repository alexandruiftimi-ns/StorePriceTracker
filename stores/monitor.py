import math
import re

from models.product import Product
from models.watch_item import WatchItem
from utils.filtering import matches_watch_item
from utils.http import create_session
from utils.units import parse_quantity, unit_price_from_quantity


# Monitorul Prețurilor (monitorulpreturilor.info) is the
# government price monitor that Romanian retailers report their
# shelf prices to daily, per store. Its API only returns stores
# together with prices for given catalog products.

MONITOR_API = "https://monitorulpreturilor.info/pmonsvc/Retail"
MONITOR_URL = "https://monitorulpreturilor.info/"
BATCH_SIZE = 100
MAX_CATALOG_IDS = 400

NETWORK_IDS = {
    "Kaufland": "KAUFLAND",
    "Lidl": "4055329000008",
}

# Everyday products almost every store stocks. Used to list the
# stores near a location, since the API cannot list stores alone.
STORE_PROBE_TERMS = ["lapte", "paine", "oua", "banane", "unt", "iaurt"]
STORE_PROBE_IDS_PER_TERM = 50

_probe_ids_cache: list[str] = []


def distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    radius = 6371.0
    phi_a = math.radians(latitude_a)
    phi_b = math.radians(latitude_b)
    delta_phi = math.radians(latitude_b - latitude_a)
    delta_lambda = math.radians(longitude_b - longitude_a)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2) ** 2
    )

    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def store_label(chain: str, raw_name: str) -> str:
    """
    "Bucuresti/Intrarea Tarcau" -> "Lidl Intrarea Tarcau".
    """
    name = raw_name.split("/")[-1].strip() or raw_name.strip()

    if name.lower().startswith(chain.lower()):
        return name

    return f"{chain} {name}"


def clean_name(raw_name: str) -> str:
    """
    "BUC_Piept de pui dezosat -" -> "Piept de pui dezosat".
    """
    name = " ".join(raw_name.split())
    name = re.sub(r"^[A-Z]{2,4}_", "", name)

    return name.strip(" -")


def _catalog_search(session, term: str) -> list[dict]:
    response = session.get(
        f"{MONITOR_API}/GetCatalogProductsByNameNetwork",
        params={"prodname": term},
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get("Items") or []


def find_catalog_ids(
    session,
    watch_item: WatchItem,
) -> list[str]:
    matching_ids = [
        entry["id"]
        for entry in _catalog_search(session, watch_item.search_term)
        if matches_watch_item(
            product_name=entry.get("name", ""),
            watch_item=watch_item,
        )[0]
    ]

    return matching_ids[:MAX_CATALOG_IDS]


def query_stores(
    session,
    chain: str,
    latitude: float,
    longitude: float,
    radius_km: float,
    catalog_ids: list[str],
) -> list[dict]:
    """
    Returns the chain's stores within the radius, each with the
    prices it reports for the given catalog products.
    """
    stores: dict[str, dict] = {}

    for start in range(0, len(catalog_ids), BATCH_SIZE):
        response = session.get(
            f"{MONITOR_API}/GetStoresForProductsByLatLon",
            params={
                "lat": latitude,
                "lon": longitude,
                "buffer": int(radius_km * 1000),
                "csvprodids": ",".join(catalog_ids[start:start + BATCH_SIZE]),
                "csvnetworkids": NETWORK_IDS[chain],
            },
            timeout=60,
        )

        response.raise_for_status()

        for raw_store in response.json().get("Items") or []:
            address = raw_store.get("addr") or {}
            location = address.get("location") or {}

            store = stores.setdefault(
                str(raw_store["id"]),
                {
                    "id": str(raw_store["id"]),
                    "name": store_label(chain, raw_store.get("name", "")),
                    "address": address.get("addrstring", ""),
                    "latitude": location.get("Lat"),
                    "longitude": location.get("Lon"),
                    "distance_km": raw_store.get("distance"),
                    "products": [],
                },
            )

            store["products"].extend(
                product
                for product in raw_store.get("Products") or []
                if product.get("price")
            )

    return sorted(
        stores.values(),
        key=lambda store: store["distance_km"] or 0,
    )


def find_stores_near(
    chain: str,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[dict]:
    session = create_session()

    if not _probe_ids_cache:
        for term in STORE_PROBE_TERMS:
            _probe_ids_cache.extend(
                entry["id"]
                for entry in _catalog_search(session, term)[:STORE_PROBE_IDS_PER_TERM]
            )

    stores = query_stores(
        session,
        chain,
        latitude,
        longitude,
        radius_km,
        list(dict.fromkeys(_probe_ids_cache)),
    )

    return [
        {key: value for key, value in store.items() if key != "products"}
        for store in stores
    ]


def _to_product(
    raw: dict,
    chain: str,
    watch_item: WatchItem,
    branch: str,
    source: str,
) -> Product:
    product_name = clean_name(raw.get("name", ""))
    price = float(raw["price"])
    sale_unit = (raw.get("unit") or "").strip()
    approximate = sale_unit.lower().startswith("ca.")

    if sale_unit.upper() in {"KG", "L"}:
        unit = sale_unit.lower()
        unit_price = round(price, 2)
        package = f"per {unit}"

    elif approximate:
        # Lidl: "ca. 800g" is a pack of varying weight sold by
        # the kg, so the price is already per kg (or per l).
        _, unit = parse_quantity(sale_unit)
        unit_price = round(price, 2) if unit else None
        package = f"{sale_unit}, price per {unit}" if unit else sale_unit

    else:
        # Lidl reports the package size here ("250g", "0.5l");
        # Kaufland reports "BUC" and puts the size in the name.
        unit_price, unit = unit_price_from_quantity(price, sale_unit)

        if unit_price is None:
            unit_price, unit = unit_price_from_quantity(price, product_name)

        package = sale_unit if unit_price is not None and sale_unit.upper() != "BUC" else None

    is_promo = bool(raw.get("promo"))

    return Product(
        name=product_name if chain == "Lidl" else product_name.title(),
        price=price,
        store=chain,
        url=MONITOR_URL,
        watch_label=watch_item.label,
        watch_id=watch_item.id or None,
        unit_price=unit_price,
        unit=unit,
        on_sale=is_promo,
        promo_label="Promoție" if is_promo else None,
        package=package,
        source=source,
        branch=branch,
    )


def _matching_raw_products(
    store: dict,
    watch_item: WatchItem,
):
    for raw in store["products"]:
        name = raw.get("name", "")

        # Catalog names can differ from the store's label, so
        # confirm the match on the label too.
        if matches_watch_item(product_name=name, watch_item=watch_item)[0]:
            yield raw


def search_nearest_store(
    watch_item: WatchItem,
    chain: str,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[Product]:
    """
    Each product's price at the nearest store that stocks it.
    """
    session = create_session()
    catalog_ids = find_catalog_ids(session, watch_item)

    if not catalog_ids:
        return []

    stores = query_stores(session, chain, latitude, longitude, radius_km, catalog_ids)

    nearest: dict[str, tuple[dict, dict]] = {}

    for store in stores:
        for raw in _matching_raw_products(store, watch_item):
            catalog_id = (raw.get("catprod") or {}).get("id")
            nearest.setdefault(catalog_id, (raw, store))

    return [
        _to_product(
            raw,
            chain,
            watch_item,
            branch=f"{store['name']} · {store['distance_km']:.1f} km",
            source=f"Price monitor, price date {raw.get('pricedate', '?')}",
        )
        for raw, store in nearest.values()
    ]


def search_selected_stores(
    watch_item: WatchItem,
    chain: str,
    latitude: float,
    longitude: float,
    selected_stores: list[dict],
) -> list[Product]:
    """
    Prices at the stores the user shops at. When several stores
    have the same price, they share one result that lists them
    all; stores with a different price or promotion get their own.
    """
    if not selected_stores:
        return []

    session = create_session()
    catalog_ids = find_catalog_ids(session, watch_item)

    if not catalog_ids:
        return []

    distances = {
        str(store["id"]): distance_km(
            latitude,
            longitude,
            store["latitude"],
            store["longitude"],
        )
        for store in selected_stores
    }

    radius_km = max(distances.values()) + 1

    stores = [
        store
        for store in query_stores(session, chain, latitude, longitude, radius_km, catalog_ids)
        if store["id"] in distances
    ]

    grouped: dict[tuple, dict] = {}

    for store in stores:
        for raw in _matching_raw_products(store, watch_item):
            key = (
                (raw.get("catprod") or {}).get("id"),
                raw["price"],
                bool(raw.get("promo")),
            )

            group = grouped.setdefault(key, {"raw": raw, "stores": []})
            group["stores"].append(store)

    products = []

    for group in grouped.values():
        group_stores = sorted(group["stores"], key=lambda s: distances[s["id"]])

        branch = ", ".join(
            f"{store['name']} ({distances[store['id']]:.1f} km)"
            for store in group_stores
        )

        products.append(
            _to_product(
                group["raw"],
                chain,
                watch_item,
                branch=branch,
                source=f"Price monitor, price date {group['raw'].get('pricedate', '?')}",
            )
        )

    return products
