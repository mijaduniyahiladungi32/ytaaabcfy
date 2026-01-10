from playwright.sync_api import sync_playwright
import time
from urllib.parse import urlparse, parse_qs, unquote

URL = "https://beesports.io/live-tv"

BLOCK_KEYWORDS = [
    "player",
    "embed",
    "snapx",
    "/v3?",
    "?link="
]

def is_pure_m3u8(url: str) -> bool:
    if not url.startswith("http"):
        return False
    if ".m3u8" not in url:
        return False
    for k in BLOCK_KEYWORDS:
        if k in url.lower():
            return False
    return True


def extract_real_m3u8():
    found = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()

        def on_request(request):
            url = request.url

            # ✅ case 1: direct pure m3u8
            if is_pure_m3u8(url):
                found.add(url)

            # ✅ case 2: m3u8 hidden inside ?link=
            if "link=" in url and ".m3u8" in url:
                parsed = parse_qs(urlparse(url).query)
                link = parsed.get("link")
                if link:
                    real = unquote(link[0])
                    if is_pure_m3u8(real):
                        found.add(real)

        page.on("request", on_request)

        print("[*] Opening page...")
        page.goto(URL, wait_until="domcontentloaded")

        print("[*] Waiting 20 seconds...")
        time.sleep(20)

        browser.close()

    return found


if __name__ == "__main__":
    links = extract_real_m3u8()

    if not links:
        print("❌ No PURE m3u8 found")
    else:
        print("\n🎯 PURE STREAM m3u8 ONLY:\n")
        for i, link in enumerate(links, 1):
            print(f"{i}. {link}")
