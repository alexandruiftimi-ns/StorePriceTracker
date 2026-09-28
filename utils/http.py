import requests

try:
    # Uses the Windows certificate store, which completes
    # incomplete certificate chains (monitorulpreturilor.info
    # serves one that plain certifi rejects).
    import truststore

    truststore.inject_into_ssl()

except ImportError:
    pass


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0 Safari/537.36"
)


def create_session() -> requests.Session:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, */*",
            "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
        }
    )

    return session
