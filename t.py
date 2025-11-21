# scrape_network_play_click_iframe.py
# Playwright-based network capture + try clicking play inside iframe + handle popups/ad-blocking
# Usage:
#   pip install playwright
#   playwright install
#   python scrape_network_play_click_iframe.py

import json
import base64
import time
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlayTimeout

TARGET_URL = "https://www.bilibili.tv/en/video/4795275155346944"
OUTPUT_REQ = Path("request.json")
OUTPUT_RES = Path("response.json")

# Add ad / tracker patterns you want to block
AD_BLOCK_PATTERNS = [
    "doubleclick.net",
    "googlesyndication.com",
    "adservice.google.com",
    "ads-twitter.com",
    "adroll.com",
    "adsystem.com",
    "casalemedia.com",
    "adsafeprotected.com",
    "facebook.com/tr",
    "quantserve.com",
    "amazon-adsystem.com",
    # add more if needed
]

def is_ad_url(url: str):
    for pat in AD_BLOCK_PATTERNS:
        if pat in url:
            return True
    return False

def try_click_play_in_frame(page):
    """
    Tries multiple strategies to click 'play' inside an iframe:
    1) Wait for iframe, get its content_frame and try common play selectors
    2) Use frame_locator if needed
    3) If selectors fail, click center of iframe (mouse) as fallback
    """
    print("Trying to locate iframe...")
    try:
        # wait for an iframe to appear
        iframe_element = page.wait_for_selector("iframe", timeout=8000)
    except PlayTimeout:
        print("No iframe found within timeout.")
        return False

    # get content frame
    frame = iframe_element.content_frame()
    if frame is None:
        print("iframe has no accessible content_frame (maybe cross-origin).")
        # fallback: click center of iframe element on the main page
        box = iframe_element.bounding_box()
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            print(f"Clicking center of iframe at ({cx},{cy})")
            page.mouse.click(cx, cy)
            return True
        return False

    print("Got iframe frame — trying play selectors inside that frame...")

    # list of candidate selectors commonly used by video players
    candidate_selectors = [
        "button.play",
        "button.play-button",
        ".vjs-big-play-button",
        "button[aria-label='Play']",
        "button[title='Play']",
        ".play-btn",
        ".jw-controlbar .jw-icon-play",
        ".plyr__control--overlaid" ,
        ".mejs-overlay-play",
        "video"  # as fallback we can try to click the video element itself
    ]

    for sel in candidate_selectors:
        try:
            # wait briefly for the selector inside frame
            handle = frame.query_selector(sel)
            if handle:
                print(f"Found selector in iframe: {sel} — attempting click()")
                try:
                    handle.click(timeout=4000, force=True)
                except Exception as e:
                    # try using frame.mouse if element.click fails
                    try:
                        box = handle.bounding_box()
                        if box:
                            fx = box["x"] + box["width"] / 2
                            fy = box["y"] + box["height"] / 2
                            frame.mouse.click(fx, fy)
                        else:
                            raise
                    except Exception as e2:
                        print(f"Failed to click via handle and mouse for {sel}: {e2}")
                time.sleep(1.0)
                return True
        except Exception as e:
            print(f"Error querying/clicking selector {sel}: {e}")

    # fallback: click the center of the video element or center of iframe
    try:
        video_el = frame.query_selector("video")
        if video_el:
            box = video_el.bounding_box()
            if box:
                fx = box["x"] + box["width"] / 2
                fy = box["y"] + box["height"] / 2
                print(f"Clicking center of <video> at ({fx},{fy}) inside frame")
                frame.mouse.click(fx, fy)
                return True
    except Exception as e:
        print("video element click fallback failed:", e)

    # final fallback: click the center of iframe element in parent page
    try:
        box = iframe_element.bounding_box()
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            print(f"Final fallback: clicking center of iframe on parent page at ({cx},{cy})")
            page.mouse.click(cx, cy)
            return True
    except Exception as e:
        print("Final iframe center click failed:", e)

    return False


def main():
    requests = []
    responses = []
    popups = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0 Safari/537.36"),
            java_script_enabled=True,
            bypass_csp=True,
            accept_downloads=False
        )

        # capture newly opened pages (popups)
        def on_popup(popup_page):
            print("Popup opened:", popup_page.url)
            popups.append(popup_page)
            # attach handlers to popup to capture its network too
            popup_page.on("request", lambda req: requests.append({
                "timestamp": time.time(),
                "method": req.method,
                "url": req.url,
                "headers": dict(req.headers),
                "resource_type": req.resource_type
            }))
            popup_page.on("response", lambda resp: responses.append({
                "timestamp": time.time(),
                "url": resp.url,
                "status": resp.status,
                "headers": dict(resp.headers),
                "request": {"method": resp.request.method, "url": resp.request.url}
            }))
            # close popup after a short wait to avoid lingering ad pages
            try:
                time.sleep(1.0)
                popup_page.close()
                print("Popup closed.")
            except Exception:
                pass

        # Listen to popup events at the page-level (we'll attach after page creation)
        # Create a new page
        page = context.new_page()
        page.on("popup", on_popup)

        # Global request/response handlers for main page
        def on_request(req):
            try:
                # optionally block ad requests
                if is_ad_url(req.url):
                    # abort ad request to avoid loading ad assets (optional)
                    try:
                        req.abort()
                        print("Aborted ad request:", req.url)
                        return
                    except Exception:
                        pass

                r = {
                    "timestamp": time.time(),
                    "method": req.method,
                    "url": req.url,
                    "resource_type": req.resource_type,
                    "headers": dict(req.headers),
                    "post_data": None
                }
                pd = None
                try:
                    pd = req.post_data
                except Exception:
                    pd = None
                if pd is not None:
                    if isinstance(pd, bytes):
                        r["post_data"] = {"encoding": "base64", "data": base64.b64encode(pd).decode()}
                    else:
                        r["post_data"] = {"encoding": "utf-8", "data": pd}
                requests.append(r)
            except Exception as e:
                print("on_request error:", e)

        def on_response(resp):
            try:
                resp_entry = {
                    "timestamp": time.time(),
                    "url": resp.url,
                    "status": resp.status,
                    "status_text": getattr(resp, "status_text", ""),
                    "headers": dict(resp.headers),
                    "request": {
                        "method": resp.request.method,
                        "url": resp.request.url,
                    },
                    "body_encoding": None,
                    "body": None
                }
                # try to capture body (beware big binaries)
                try:
                    body = resp.body()
                    if body:
                        # limit size to avoid huge JSONs — you can change this threshold
                        MAX_SAVE_BYTES = 2 * 1024 * 1024  # 2 MB
                        if len(body) > MAX_SAVE_BYTES:
                            resp_entry["body_encoding"] = "base64_truncated"
                            resp_entry["body_length"] = len(body)
                            resp_entry["body"] = base64.b64encode(body[:MAX_SAVE_BYTES]).decode()
                        else:
                            resp_entry["body_encoding"] = "base64"
                            resp_entry["body"] = base64.b64encode(body).decode()
                except Exception as e:
                    resp_entry["body_error"] = str(e)
                responses.append(resp_entry)
            except Exception as e:
                print("on_response error:", e)

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("console", lambda msg: print(f"[console {msg.type}] {msg.text}"))
        page.on("pageerror", lambda exc: print("[pageerror]", exc))

        # Optionally route/abort requests matching ad patterns at routing level
        # (This is another way; note req.abort() in on_request may not always work)
        def route_handler(route, request):
            if is_ad_url(request.url):
                try:
                    route.abort()
                    print("Route aborted (ad):", request.url)
                except Exception:
                    route.continue_()
            else:
                route.continue_()

        try:
            page.route("**/*", route_handler)
        except Exception as e:
            print("Could not set global route:", e)

        # Navigate
        print("Navigating to", TARGET_URL)
        try:
            page.goto(TARGET_URL, timeout=200000, wait_until="domcontentloaded")
        except Exception as e:
            print("Navigation error (continuing):", e)

        # small wait for scripts to run
        time.sleep(2)

        # Try to accept cookie banners if any (common selectors)
        cookie_selectors = [
            "button[aria-label='Accept']",
            "button:has-text('Accept')",
            "button:has-text('Agree')",
            ".cookie-consent-accept",
            "#onetrust-accept-btn-handler"
        ]
        for cs in cookie_selectors:
            try:
                el = page.query_selector(cs)
                if el:
                    print("Clicking cookie accept selector:", cs)
                    el.click(timeout=3000, force=True)
                    time.sleep(1)
                    break
            except Exception:
                pass

        # Now attempt to click inside iframe/play the video
        clicked = False
        try:
            clicked = try_click_play_in_frame(page)
            print("Click in iframe result:", clicked)
        except Exception as e:
            print("Exception during iframe click attempt:", e)

        # Wait additional time to let subsequent network calls happen (e.g., manifests, chunks)
        WAIT_SECONDS_AFTER_CLICK = 10
        print(f"Waiting {WAIT_SECONDS_AFTER_CLICK}s after click to capture network activity...")
        time.sleep(WAIT_SECONDS_AFTER_CLICK)

        # Close browser
        print("Closing browser...")
        try:
            browser.close()
        except Exception:
            pass

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
