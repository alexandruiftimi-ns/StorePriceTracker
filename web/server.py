import threading
import traceback
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from services.recommend import build_report
from services.scanner import run_scan
from utils import catalog


STATIC_FOLDER = Path(__file__).parent / "static"

app = Flask(__name__, static_folder=None)


# ============================================================
# BACKGROUND SEARCH JOB
# ============================================================
# Only one market search runs at a time; the page polls
# /api/search/status for progress.

_job_lock = threading.Lock()
_job = {
    "running": False,
    "done": 0,
    "total": 0,
    "message": "",
    "error": None,
}


def _set_job(**changes) -> None:
    with _job_lock:
        _job.update(changes)


def _send_telegram(report: dict) -> None:
    from utils.telegram import (
        build_shopping_report_message,
        send_message,
    )

    send_message(build_shopping_report_message(report))


def _run_search_job(watch_items, settings) -> None:
    try:
        result = run_scan(
            watch_items,
            settings,
            progress=lambda done, total, message: _set_job(
                done=done,
                total=total,
                message=message,
            ),
        )

        report = build_report(
            watch_items,
            result.products,
            settings["enabled_stores"],
            result.errors,
        )

        catalog.save_last_search(report)

        if settings.get("send_to_telegram"):
            try:
                _send_telegram(report)
            except Exception as error:
                report["errors"]["Telegram"] = str(error)
                catalog.save_last_search(report)

        _set_job(running=False, message="Done")

    except Exception as error:
        traceback.print_exc()
        _set_job(running=False, error=str(error), message="Failed")


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


# ============================================================
# PAGES
# ============================================================


@app.get("/")
def index():
    return send_from_directory(STATIC_FOLDER, "index.html")


@app.get("/static/<path:file_name>")
def static_files(file_name: str):
    return send_from_directory(STATIC_FOLDER, file_name)


# ============================================================
# PRODUCTS AND SHOPPING LIST
# ============================================================


@app.get("/api/products")
def list_products():
    return jsonify(catalog.load_products())


@app.post("/api/products")
def create_product():
    try:
        product = catalog.create_product(request.get_json() or {})
    except ValueError as error:
        return _error(str(error))

    return jsonify(product), 201


@app.put("/api/products/<product_id>")
def update_product(product_id: str):
    try:
        product = catalog.update_product(
            product_id,
            request.get_json() or {},
        )
    except ValueError as error:
        return _error(str(error))
    except KeyError:
        return _error("Product not found.", 404)

    return jsonify(product)


@app.delete("/api/products/<product_id>")
def delete_product(product_id: str):
    try:
        catalog.delete_product(product_id)
    except KeyError:
        return _error("Product not found.", 404)

    return "", 204


@app.post("/api/shopping-list")
def set_shopping_list():
    """
    Body: {"ids": [...], "in_list": true|false}
    """
    payload = request.get_json() or {}

    products = catalog.set_in_shopping_list(
        payload.get("ids") or [],
        bool(payload.get("in_list")),
    )

    return jsonify(products)


@app.post("/api/products/preview")
def preview_product():
    """
    Searches the stores for one product before saving it, so
    the filters can be checked and tuned.
    """
    try:
        fields = catalog.validate_product(request.get_json() or {})
    except ValueError as error:
        return _error(str(error))

    watch_item = catalog.to_watch_item(
        {**fields, "id": "preview"}
    )

    settings = catalog.load_settings()
    result = run_scan([watch_item], settings)

    report = build_report(
        [watch_item],
        result.products,
        settings["enabled_stores"],
        result.errors,
    )

    return jsonify(report)


# ============================================================
# MARKET SEARCH
# ============================================================


@app.post("/api/search")
def start_search():
    watch_items = catalog.shopping_list_items()

    if not watch_items:
        return _error("Your shopping list is empty.")

    settings = catalog.load_settings()

    if not settings["enabled_stores"]:
        return _error("Enable at least one store in Settings.")

    with _job_lock:
        if _job["running"]:
            return _error("A search is already running.", 409)

        _job.update(
            running=True,
            done=0,
            total=0,
            message="Starting…",
            error=None,
        )

    threading.Thread(
        target=_run_search_job,
        args=(watch_items, settings),
        daemon=True,
    ).start()

    return jsonify({"started": True, "items": len(watch_items)}), 202


@app.get("/api/search/status")
def search_status():
    with _job_lock:
        return jsonify(dict(_job))


@app.get("/api/search/latest")
def latest_search():
    return jsonify(catalog.load_last_search())


# ============================================================
# SETTINGS
# ============================================================


def _public_settings(settings: dict) -> dict:
    """
    Settings for the page. The saved bot token is never sent
    back, only whether one is set and its last characters.
    """
    from utils.telegram import get_credentials

    token = settings.get("telegram_bot_token", "")
    effective_token, effective_chat_id = get_credentials()

    return {
        **{key: value for key, value in settings.items() if key != "telegram_bot_token"},
        "telegram_token_saved": bool(token),
        "telegram_token_hint": f"…{token[-4:]}" if token else "",
        "telegram_from_env": bool(effective_token and not token),
        "telegram_configured": bool(effective_token and effective_chat_id),
        "available_stores": catalog.STORES,
        "is_default_location": (
            settings["latitude"] == catalog.DEFAULT_SETTINGS["latitude"]
            and settings["longitude"] == catalog.DEFAULT_SETTINGS["longitude"]
        ),
    }


@app.get("/api/settings")
def get_settings():
    return jsonify(_public_settings(catalog.load_settings()))


@app.put("/api/settings")
def put_settings():
    try:
        settings = catalog.save_settings(request.get_json() or {})
    except (KeyError, TypeError, ValueError) as error:
        return _error(f"Invalid settings: {error}")

    return jsonify(_public_settings(settings))


# ============================================================
# LIDL STORE PICKER
# ============================================================


@app.get("/api/stores/lidl")
def nearby_lidl_stores():
    from stores.monitor import find_stores_near

    try:
        latitude = float(request.args["lat"])
        longitude = float(request.args["lon"])
        radius_km = min(float(request.args.get("radius", 5)), 30)
    except (KeyError, ValueError):
        return _error("lat and lon are required.")

    try:
        stores = find_stores_near("Lidl", latitude, longitude, radius_km)
    except Exception as error:
        return _error(f"Could not load Lidl stores: {error}", 502)

    return jsonify(stores)


# ============================================================
# TELEGRAM SETUP
# ============================================================
# Each endpoint takes the token typed in the form, or falls back
# to the saved one, so the steps can be tried before saving.


def _telegram_token(payload: dict) -> str:
    from utils.telegram import get_credentials

    return (payload.get("token") or "").strip() or get_credentials()[0]


@app.post("/api/telegram/check")
def telegram_check():
    from utils.telegram import get_bot_info

    try:
        bot = get_bot_info(_telegram_token(request.get_json() or {}))
    except RuntimeError as error:
        return _error(str(error))

    return jsonify({"username": bot.get("username"), "name": bot.get("first_name")})


@app.post("/api/telegram/chats")
def telegram_chats():
    from utils.telegram import find_chats

    try:
        chats = find_chats(_telegram_token(request.get_json() or {}))
    except RuntimeError as error:
        return _error(str(error))

    return jsonify(chats)


@app.post("/api/telegram/test")
def telegram_test():
    from utils.telegram import send_message

    payload = request.get_json() or {}

    try:
        send_message(
            "✅ Stores Price Tracker is connected. "
            "Your shopping results will arrive here.",
            token=_telegram_token(payload),
            chat_id=(payload.get("chat_id") or "").strip() or None,
        )
    except RuntimeError as error:
        return _error(str(error))

    return jsonify({"sent": True})
