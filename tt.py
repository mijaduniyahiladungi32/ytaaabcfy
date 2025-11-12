import requests

# Target URL
url = "https://profamouslife.com/premium.php?player%3Dmobile&live=ptvpk"

# Custom headers
headers = {
    "Referer": "https://streamcrichd.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
}

# Send GET request
response = requests.get(url, headers=headers, timeout=15)

# Save response to a file
with open("Response_body.txt", "w", encoding="utf-8") as f:
    f.write(response.text)

print("Response saved to Response_body.txt")
