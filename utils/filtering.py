import re
import unicodedata

from models.watch_item import WatchItem


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)

    without_accents = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    without_accents = without_accents.lower()

    # Treat punctuation and hyphens as spaces.
    without_accents = re.sub(
        r"[^a-z0-9]+",
        " ",
        without_accents,
    )

    return re.sub(
        r"\s+",
        " ",
        without_accents,
    ).strip()


def contains_text(
    product_name: str,
    search_text: str,
) -> bool:
    normalized_name = normalize_text(product_name)
    normalized_search = normalize_text(search_text)

    pattern = (
        r"(?:^|\s)"
        + re.escape(normalized_search)
        + r"(?:$|\s)"
    )

    return re.search(pattern, normalized_name) is not None


# In Romanian product names, a word after these is an
# ingredient or flavor, not the product itself:
# "Iaurt cu banane", "Popcorn cu aroma de cascaval".
INGREDIENT_MARKERS = (
    "cu",
    "aroma de",
    "aroma",
    "gust de",
    "gust",
)


def contains_as_product(
    product_name: str,
    search_text: str,
) -> bool:
    normalized_name = normalize_text(product_name)
    normalized_search = normalize_text(search_text)

    if not normalized_search:
        return False

    pattern = (
        r"(?:^|\s)"
        + re.escape(normalized_search)
        + r"(?=$|\s)"
    )

    for match in re.finditer(pattern, normalized_name):
        text_before = normalized_name[:match.start()].strip()

        if not any(
            text_before == marker
            or text_before.endswith(f" {marker}")
            for marker in INGREDIENT_MARKERS
        ):
            return True

    return False


def contains_any_alternative(
    product_name: str,
    required_word: str,
) -> bool:
    """
    A required word may list alternatives separated by "|",
    because stores abbreviate differently:
    "piept de pui|piept pui".
    """
    return any(
        contains_as_product(
            product_name,
            alternative,
        )
        for alternative in required_word.split("|")
        if alternative.strip()
    )


def starts_with_any_alternative(
    product_name: str,
    required_word: str,
) -> bool:
    """
    One short leading word is allowed before the match, for
    labels such as "Bio mere verzi" or Kaufland's "Klc ...".
    """
    words = normalize_text(product_name).split()

    candidates = [" ".join(words)]

    if words and len(words[0]) <= 3:
        candidates.append(" ".join(words[1:]))

    for alternative in required_word.split("|"):
        normalized_alternative = normalize_text(alternative)

        if not normalized_alternative:
            continue

        for candidate in candidates:
            if (
                candidate == normalized_alternative
                or candidate.startswith(f"{normalized_alternative} ")
            ):
                return True

    return False


def matches_watch_item(
    product_name: str,
    watch_item: WatchItem,
) -> tuple[bool, str]:
    if (
        getattr(watch_item, "match_start", False)
        and watch_item.required_words
        and not starts_with_any_alternative(
            product_name,
            watch_item.required_words[0],
        )
    ):
        return (
            False,
            "Does not start with: "
            f"{watch_item.required_words[0]}",
        )

    missing_required_words = [
        required_word
        for required_word in watch_item.required_words
        if not contains_any_alternative(
            product_name,
            required_word,
        )
    ]

    if missing_required_words:
        missing_text = ", ".join(
            missing_required_words
        )

        return (
            False,
            f"Missing required text: {missing_text}",
        )

    for excluded_word in watch_item.excluded_words:
        if contains_text(
            product_name,
            excluded_word,
        ):
            return (
                False,
                f"Contains excluded text: {excluded_word}",
            )

    return True, "Accepted"