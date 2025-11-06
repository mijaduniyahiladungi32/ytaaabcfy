# scrape_network.py
# Purpose: Load a JS-heavy page with Playwright, capture network requests & responses,
# and save them to request.json and response.json.
# Usage: pip install playwright ; playwright install ; python scrape_network.py

import json
import base64
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

TARGET_URL = "https://vidsrc.to/embed/movie/tt4154796"
OUTPUT_REQ = Path("request.json")
OUTPUT_RES = Path("response.json")

def main():
    requests = []   # list of dicts for requests
    responses = []  # list of dicts for responses

    with sync_playwright() as p:
        # choose browser: 'chromium', 'firefox', 'webkit'
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36",
            # optionally allow large buffers:
            java_script_enabled=True,
            bypass_csp=True
        )

        page = context.new_page()

        # --- Handlers ---
        def on_request(req):
            try:
                r = {
                    "timestamp": time.time(),
                    "id": req._impl_obj._guid if hasattr(req, "_impl_obj") else None,
                    "method": req.method,
                    "url": req.url,
                    "resource_type": req.resource_type,
                    "headers": dict(req.headers),
                    "post_data": None
                }
                try:
                    # may be None
                    pd = req.post_data
                    if pd is not None:
                        # if binary-like, base64 it and note that encoding
                        if isinstance(pd, bytes):
                            r["post_data"] = {"encoding": "base64", "data": base64.b64encode(pd).decode()}
                        else:
                            r["post_data"] = {"encoding": "utf-8", "data": pd}
                except Exception:
                    pass
                requests.append(r)
            except Exception as e:
                print("on_request error:", e)

        def on_response(resp):
            try:
                resp_entry = {
                    "timestamp": time.time(),
                    "url": resp.url,
                    "status": resp.status,
                    "status_text": resp.status_text,
                    "headers": dict(resp.headers),
                    "request": {
                        "method": resp.request.method,
                        "url": resp.request.url,
                    },
                    "body_encoding": None,
                    "body": None
                }
                # Try to get body (may throw for certain types)
                try:
                    body_bytes = resp.body()  # bytes
                    if body_bytes is not None:
                        # For very large responses you may prefer to skip body or truncate
                        # Here we base64 encode to be safe with binary/multimedia
                        if len(body_bytes) > 0:
                            resp_entry["body_encoding"] = "base64"
                            resp_entry["body"] = base64.b64encode(body_bytes).decode()
                except Exception as e:
                    # Some responses may not expose body (e.g., data: URIs, aborted requests)
                    resp_entry["body_error"] = str(e)

                responses.append(resp_entry)
            except Exception as e:
                print("on_response error:", e)

        # attach handlers
        page.on("request", on_request)
        page.on("response", on_response)

        # optional: capture console logs and page errors for debugging
        page.on("console", lambda msg: print(f"[console {msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: print("[pageerror]", exc))

        # Go to the target page
        print("Navigating to", TARGET_URL)
        try:
            page.goto(TARGET_URL, timeout=60000, wait_until="networkidle")
        except Exception as e:
            print("Initial navigation error (continuing):", e)

        # Wait additional time to allow XHR/fetch/video manifests to load
        WAIT_SECONDS_AFTER_LOAD = 8
        print(f"Waiting {WAIT_SECONDS_AFTER_LOAD}s to let background requests finish...")
        time.sleep(WAIT_SECONDS_AFTER_LOAD)

        # Optionally, you can interact with the page (click play, accept cookies) to trigger more requests.
        # Example: try clicking a play button if present (uncomment and adapt):
        # try:
        #     page.click("button.play, .play-button")
        #     time.sleep(5)
        # except Exception:
        #     pass

        # Close browser
        print("Closing browser...")
        browser.close()

    # Save requests and responses
    print(f"Saving {len(requests)} requests -> {OUTPUT_REQ}")
    with OUTPUT_REQ.open("w", encoding="utf-8") as f:
        json.dump(requests, f, ensure_ascii=False, indent=2)

    print(f"Saving {len(responses)} responses -> {OUTPUT_RES}")
    with OUTPUT_RES.open("w", encoding="utf-8") as f:
        json.dump(responses, f, ensure_ascii=False, indent=2)

    print("Done.")

if __name__ == "__main__":
    main()
