from playwright.sync_api import sync_playwright
import time
import requests

URL = "https://beesports.io/live-tv"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

def is_valid_m3u8(url, referer):
    try:
        headers = {
            "User-Agent": UA,
            "Referer": referer,
            "Origin": referer.rstrip("/"),
            "Accept": "*/*"
        }

        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and "#EXTM3U" in r.text[:100]:
            return True
    except:
        pass
    return False


def extract_real_streams():
    found = set()
    verified = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(user_agent=UA)
        page = context.new_page()

        def on_request(req):
            url = req.url
            if ".m3u8" in url:
                found.add(url)

        def on_response(res):
            if ".m3u8" in res.url:
                found.add(res.url)

        page.on("request", on_request)
        page.on("response", on_response)

        print("[*] Opening page...")
        page.goto(URL, wait_until="networkidle")

        print("[*] Waiting 20 seconds (player + retries)...")
        time.sleep(20)

        browser.close()

    print(f"[*] Detected {len(found)} candidate m3u8 URLs")

    for m3u8 in found:
        if is_valid_m3u8(m3u8, URL):
            verified.append(m3u8)

    return verified


if __name__ == "__main__":
    streams = extract_real_streams()

    if not streams:
        print("❌ No playable m3u8 found")
    else:
        print("\n🎯 VERIFIED PLAYABLE STREAMS:\n")
        for i, s in enumerate(streams, 1):
            print(f"{i}. {s}")
