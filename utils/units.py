import re
import unicodedata


# Converts a source unit to (base unit, factor to base unit).
UNIT_FACTORS = {
    "kg": ("kg", 1.0),
    "g": ("kg", 0.001),
    "gr": ("kg", 0.001),
    "l": ("l", 1.0),
    "ml": ("l", 0.001),
    "cl": ("l", 0.01),
}

UNIT_PATTERN = r"(kg|gr|g|ml|cl|l)"
NUMBER_PATTERN = r"(\d+(?:[.,]\d+)?)"


def _to_float(text: str) -> float:
    return float(text.replace(",", "."))


def normalize_quantity_text(text: str) -> str:
    """
    Like normalize_text, but keeps decimal separators
    ("0,75l" -> "0.75l") and multipack markers ("4x100g").
    """
    normalized = unicodedata.normalize("NFKD", text)

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    ).lower()

    normalized = re.sub(r"(\d),(\d)", r"\1.\2", normalized)

    # Dots only survive as decimal separators.
    normalized = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", normalized)
    normalized = re.sub(r"[^a-z0-9.]+", " ", normalized)

    return re.sub(r"\s+", " ", normalized).strip()


def parse_quantity(
    text: object,
) -> tuple[float | None, str | None]:
    """
    Finds the package size in a product name or weight column.

    Returns (amount, unit) where unit is "kg" or "l":
    "650 GR" -> (0.65, "kg"), "4X100G" -> (0.4, "kg"),
    "0,75l" -> (0.75, "l"), "per kg" -> (1.0, "kg").
    """
    if text is None:
        return None, None

    normalized = normalize_quantity_text(str(text))

    multipack = re.search(
        rf"(\d+)\s*x\s*{NUMBER_PATTERN}\s*{UNIT_PATTERN}\b",
        normalized,
    )

    if multipack:
        count = int(multipack.group(1))
        size = _to_float(multipack.group(2))
        base_unit, factor = UNIT_FACTORS[multipack.group(3)]

        return count * size * factor, base_unit

    matches = re.findall(
        rf"{NUMBER_PATTERN}\s*{UNIT_PATTERN}\b",
        normalized,
    )

    if matches:
        # The last size in a name is usually the package size
        # ("Lapte 1.5% 1l" -> 1l, not 1.5).
        size_text, unit_text = matches[-1]
        base_unit, factor = UNIT_FACTORS[unit_text]
        amount = _to_float(size_text) * factor

        if amount > 0:
            return amount, base_unit

    if re.search(r"(?:^|\s)(?:per\s*)?kg(?:$|\s)", normalized):
        return 1.0, "kg"

    if re.search(r"(?:^|\s)per\s*l(?:$|\s)", normalized):
        return 1.0, "l"

    return None, None


def unit_price_from_quantity(
    package_price: float,
    text: object,
) -> tuple[float | None, str | None]:
    amount, unit = parse_quantity(text)

    if amount is None or unit is None or amount <= 0:
        return None, None

    return round(package_price / amount, 2), unit


def parse_base_price(
    text: object,
) -> tuple[float | None, str | None]:
    """
    Reads stated unit prices such as "(=1 kg 31.96)",
    "1 kg = 24,60 lei" or "1 L = 190,53 lei".
    """
    if not text:
        return None, None

    lowered = str(text).lower()

    match = re.search(
        rf"1\s*(kg|l)\s*=?\s*{NUMBER_PATTERN}",
        lowered,
    )

    if match:
        return _to_float(match.group(2)), match.group(1)

    return None, None
