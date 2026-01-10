from playwright.sync_api import sync_playwright
import time

URL = "https://beesports.io/live-tv"

def extract_m3u8_with_headers():
    results = []

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
            if ".m3u8" in url:
                headers = request.headers

                results.append({
                    "url": url,
                    "referer": headers.get("referer", ""),
                    "origin": headers.get("origin", ""),
                    "user_agent": headers.get("user-agent", "")
                })

        page.on("request", on_request)

        print("[*] Opening page...")
        page.goto(URL, wait_until="domcontentloaded")

        print("[*] Waiting 20 seconds...")
        time.sleep(20)

        browser.close()

    return results


if __name__ == "__main__":
    data = extract_m3u8_with_headers()

    if not data:
        print("❌ No m3u8 found")
    else:
        print("\n🎯 Extracted m3u8 with headers:\n")
        for i, item in enumerate(data, 1):
            print(f"#{i}")
            print("URL       :", item["url"])
            print("Referer   :", item["referer"])
            print("Origin    :", item["origin"])
            print("User-Agent:", item["user_agent"])
            print("-" * 60)
