from models.watch_item import WatchItem


# Starter products. They are copied into data/products.json the
# first time the app runs; after that, add and edit products
# from the web UI instead of here.
#
# required_words: every entry must appear in the product name.
# Use "|" for alternatives, since stores abbreviate names
# differently ("piept de pui|piept pui").
# excluded_words: any of these rejects the product.

WATCHLIST = [

    # ==========================
    # MEAT
    # ==========================

    WatchItem(
        category="Meat",
        label="Chicken breast",
        search_term="piept de pui",
        required_words=[
            "piept de pui|piept pui",
        ],
        excluded_words=[
            "șuncă",
            "sunca",
            "crenvurști",
            "crenvursti",
            "crenwursti",
            "cremwursti",
            "parizer",
            "afumat",
            "mazăre",
            "mazare",
            "nuggets",
            "snitel",
            "șnițel",
            "pastrama",
            "pastramă",
            "gujoane",
            "pane",
            "salata",
            "salată",
            "conserva",
            "conservă",
            "gatit",
            "gătit",
            "preparat",
            "carne tocata",
            "carne tocată",
            "medalion",
            "popcorn",
            "wrap",
            "cordon bleu",
            "jambon",
            "specialitate",
            "crispy",
            "gulas",
            "rulada",
        ],
    ),

    WatchItem(
        category="Meat",
        label="Ground beef",
        search_term="carne tocata vita",
        required_words=[
            "carne tocata|carne tocată|tocatura|tocătură",
            "vita|vită",
        ],
        excluded_words=[
            "porc",
            "burger",
            "chiftele",
        ],
    ),

    # ==========================
    # DAIRY
    # ==========================

    WatchItem(
        category="Dairy",
        label="Lactose-free milk",
        search_term="lapte fara lactoza",
        required_words=[
            "lapte",
            "fara lactoza|fără lactoză|zero lactoza|zero lactoză",
        ],
        excluded_words=[
            "praf",
            "bautura vegetala",
            "băutură vegetală",
        ],
    ),

    WatchItem(
        category="Dairy",
        label="Kefir",
        search_term="kefir",
        required_words=[
            "kefir",
        ],
    ),

    WatchItem(
        category="Dairy",
        label="Cream Cheese",
        search_term="crema de branza",
        required_words=[
            "crema|cremă",
            "branza|brânză",
        ],
    ),

    WatchItem(
        category="Dairy",
        label="Mozzarella",
        search_term="mozzarella",
        required_words=[
            "mozzarella",
        ],
    ),

    WatchItem(
        category="Dairy",
        label="Cheese Block",
        search_term="cascaval",
        required_words=[
            "cascaval|cașcaval",
        ],
        excluded_words=[
            "felii",
            "feliat",
            "ras",
            "răzuit",
            "snack",
            "saratele",
            "sărățele",
            "popcorn",
            "chips",
            "covrigei",
            "biscuiti",
            "biscuiți",
            "pufuleti",
            "pufuleți",
            "pizza",
            "topita",
            "topită",
            "sos",
            "afumat",
            "specialitate",
            "sunca",
            "șuncă",
        ],
    ),

    WatchItem(
        category="Dairy",
        label="Cheese Slices",
        search_term="cascaval felii",
        required_words=[
            "cascaval|cașcaval",
            "felii|feliat",
        ],
        excluded_words=[
            "topita",
            "topită",
            "snack",
            "sandvis",
            "sandviș",
        ],
    ),

    # ==========================
    # FRUITS & VEGETABLES
    # ==========================

    WatchItem(
        category="Fruit & Vegetables",
        label="Bananas",
        search_term="banane",
        match_start=True,
        required_words=[
            "banane",
        ],
        excluded_words=[
            "chips",
            "piure",
            "nectar",
            "iaurt",
            "bautura",
            "băutură",
            "baton",
            "biscuiti",
            "biscuiți",
            "inghetata",
            "înghețată",
            "smoothie",
            "suc",
            "prajitura",
            "prăjitură",
        ],
    ),

    WatchItem(
        category="Fruit & Vegetables",
        label="Apples",
        search_term="mere",
        match_start=True,
        required_words=[
            "mere",
        ],
        excluded_words=[
            "suc",
            "piure",
            "oțet",
            "otet",
            "cidru",
            "iaurt",
            "baton",
            "biscuiti",
            "biscuiți",
            "chips",
            "compot",
            "gem",
            "placinta",
            "plăcintă",
            "strudel",
            "nectar",
            "bautura",
            "băutură",
        ],
    ),

    WatchItem(
        category="Fruit & Vegetables",
        label="Salad Mix",
        search_term="mix salata",
        required_words=[
            "salata|salată",
        ],
        excluded_words=[
            "sos",
            "conservă",
            "conserva",
            "murată",
            "murata",
            "condimente",
            "seminte",
            "semințe",
            "rasnita",
            "râșniță",
            "germeni",
            "cartofi",
            "icre",
            "boeuf",
            "vinete",
            "ciuperci",
            "ton",
            "pui",
            "oua",
            "ouă",
            "dressing",
            "morcovi",
            "varza",
            "varză",
            "castraveti",
            "castraveți",
            "sfecla",
            "sfeclă",
            "carne",
            "peste",
            "pește",
            "orez",
            "paste",
            "coleslaw",
        ],
    ),

    # ==========================
    # DRINKS
    # ==========================

    WatchItem(
        category="Drinks",
        label="Coffee Beans",
        search_term="cafea boabe",
        required_words=[
            "cafea",
            "boabe",
        ],
        excluded_words=[
            "capsule",
            "macinata",
            "măcinată",
            "solubila",
            "solubilă",
        ],
    ),

    WatchItem(
        category="Drinks",
        label="Cola Zero",
        search_term="cola zero",
        required_words=[
            "cola",
            "zero",
        ],
        excluded_words=[
            "jeleuri",
            "bomboane",
            "acadea",
            "inghetata",
            "înghețată",
            "biscuiti",
            "biscuiți",
            "fanta",
            "sprite",
            "schweppes",
        ],
    ),

    # ==========================
    # PANTRY
    # ==========================

    WatchItem(
        category="Pantry",
        label="Flour",
        search_term="faina",
        required_words=[
            "faina|făină",
        ],
        excluded_words=[
            "malai",
            "mălai",
            "gris",
            "griș",
            "paine",
            "pâine",
            "sita",
            "lipii",
            "tortilla",
            "biscuiti",
            "biscuiți",
            "covrigei",
            "sticksuri",
            "grisine",
            "fidea",
            "maia",
            "momeala",
            "momeală",
            "prajita",
            "prăjită",
        ],
    ),
]
