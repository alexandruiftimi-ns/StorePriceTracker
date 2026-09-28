import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from models.product import Product


HISTORY_FOLDER = Path("history")


def get_store_folder(store_name: str) -> Path:
    store_folder = HISTORY_FOLDER / store_name.lower()

    store_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    return store_folder


def save_products(
    products: list[Product],
    store_name: str,
) -> Path:
    store_folder = get_store_folder(store_name)

    timestamp = datetime.now()

    file_name = timestamp.strftime(
        "%Y-%m-%d_%H-%M-%S.json"
    )

    file_path = store_folder / file_name

    data = {
        "created_at": timestamp.isoformat(
            timespec="seconds"
        ),
        "store": store_name,
        "product_count": len(products),
        "products": [
            asdict(product)
            for product in products
        ],
    }

    with file_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4,
        )

    return file_path


def load_products_from_file(
    file_path: Path,
) -> list[Product]:
    try:
        with file_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(
            f"Could not load history file "
            f"{file_path}: {error}"
        )

        return []

    products: list[Product] = []

    for product_data in data.get(
        "products",
        [],
    ):
        try:
            products.append(
                Product(**product_data)
            )

        except TypeError as error:
            print(
                f"Skipped incompatible product "
                f"in {file_path}: {error}"
            )

    return products


def load_latest_products(
    store_name: str,
) -> list[Product]:
    store_folder = get_store_folder(store_name)

    history_files = sorted(
        store_folder.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not history_files:
        return []

    latest_file = history_files[0]

    return load_products_from_file(
        latest_file
    )


def load_latest_products_for_stores(
    store_names: list[str],
) -> dict[str, list[Product]]:
    products_by_store: dict[
        str,
        list[Product],
    ] = {}

    for store_name in store_names:
        products_by_store[store_name] = (
            load_latest_products(
                store_name=store_name,
            )
        )

    return products_by_store