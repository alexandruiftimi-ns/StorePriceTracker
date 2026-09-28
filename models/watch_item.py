from dataclasses import dataclass, field


@dataclass
class WatchItem:
    category: str
    label: str
    search_term: str
    required_words: list[str]
    excluded_words: list[str] = field(default_factory=list)
    id: str = ""

    # For fresh produce: the name must start with the first
    # required word ("Banane", not "Iaurt ... banane").
    match_start: bool = False