from pathlib import Path

import pandas as pd
import requests


LIDL_PRICE_URL = (
    "https://www.lidl.ro/explore/assets/"
    "webPriceData/ro/preturiZilniceLidl.xlsb"
)

TEMP_FOLDER = Path("data/temp")
TEMP_FILE = TEMP_FOLDER / "preturiZilniceLidl.xlsb"


def download_lidl_file() -> Path:
    TEMP_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    response = requests.get(
        LIDL_PRICE_URL,
        timeout=60,
    )

    response.raise_for_status()

    TEMP_FILE.write_bytes(
        response.content
    )

    return TEMP_FILE


file_path = download_lidl_file()

try:
    excel_file = pd.ExcelFile(
        file_path,
        engine="pyxlsb",
    )

    print("Sheets:")
    print(excel_file.sheet_names)
    print()

    for sheet_name in excel_file.sheet_names:
        print("=" * 70)
        print(f"Sheet: {sheet_name}")
        print("=" * 70)

        dataframe = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            engine="pyxlsb",
        )

        print("Columns:")
        print(dataframe.columns.tolist())
        print()

        print("First 10 rows:")
        print(
            dataframe.head(10).to_string(
                index=False,
            )
        )
        print()

finally:
    file_path.unlink(
        missing_ok=True
    )

    print()
    print("Temporary Lidl file deleted.")