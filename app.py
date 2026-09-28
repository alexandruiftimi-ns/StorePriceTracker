"""
Starts the web app: python app.py
Then open http://127.0.0.1:5000 (opened automatically).
"""

import os
import sys
import threading
import webbrowser

# Product names contain Romanian characters; the Windows
# console would otherwise fail printing them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Relative data paths (data/, history/) resolve from here.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from web.server import app  # noqa: E402


HOST = "127.0.0.1"
PORT = int(os.getenv("PORT", "5000"))


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"

    print(f"Stores Price Tracker running at {url}")
    print("Press Ctrl+C to stop.")

    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, webbrowser.open, args=[url]).start()

    app.run(host=HOST, port=PORT, debug=False, threaded=True)
