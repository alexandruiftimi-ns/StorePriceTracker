from playwright.sync_api import sync_playwright


PAGE_URL = "https://www.lidl.ro/c/preturile-la-zi/s10019622"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=False,
    )

    page = browser.new_page()

    page.goto(
        PAGE_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(3000)

    links = page.locator("a")

    print(f"Links found: {links.count()}")
    print()

    for index in range(links.count()):
        link = links.nth(index)

        text = " ".join(
            link.inner_text().split()
        )

        href = link.get_attribute("href")

        if not href:
            continue

        combined = f"{text} {href}".lower()

        if any(
            keyword in combined
            for keyword in [
                "descar",
                ".xlsx",
                ".xlsb",
                ".xls",
                ".csv",
            ]
        ):
            print("Text:", text)
            print("URL:", href)
            print()

    browser.close()