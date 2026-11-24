
import os
import json
import time
import hashlib
from urllib.parse import urlparse, unquote

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

URL = "https://nzp.gay/"
OUTPUT = "nzp_complete"

os.makedirs(OUTPUT, exist_ok=True)

options = Options()
options.set_capability(
    "goog:loggingPrefs",
    {"performance": "ALL"}
)

driver = webdriver.Chrome(options=options)

print("[*] Opening NZ: Portable...")
driver.execute_cdp_cmd("Network.enable", {})

driver.get(URL)

print("\n[!] Browser opened.")
print("[!] Click 'Click To Begin' and let the game load.")
input("[!] Once you're finished loading the game, press ENTER here...")

print("[*] Collecting browser network requests...")

# Collect all network requests recorded by Chrome
logs = driver.get_log("performance")

urls = {}

for entry in logs:
    try:
        message = json.loads(entry["message"])["message"]

        if message["method"] != "Network.requestWillBeSent":
            continue

        params = message["params"]
        request = params["request"]

        if request["method"] != "GET":
            continue

        resource_type = params.get("type", "Other")

        if resource_type not in (
            "Document", "Script", "Stylesheet",
            "Image", "Font", "Media",
            "XHR", "Fetch", "Other"
        ):
            continue

        url = request["url"]

        if url.startswith(("http://", "https://")):
            urls[url] = resource_type

    except Exception:
        pass

print(f"[*] Found {len(urls)} unique resources.")

# Transfer browser cookies into requests
session = requests.Session()

for cookie in driver.get_cookies():
    session.cookies.set(
        cookie["name"],
        cookie["value"],
        domain=cookie.get("domain"),
        path=cookie.get("path", "/")
    )

session.headers.update({
    "User-Agent": driver.execute_script(
        "return navigator.userAgent"
    ),
    "Referer": URL
})

driver.quit()

# Download discovered resources
for index, (url, resource_type) in enumerate(urls.items(), 1):
    try:
        parsed = urlparse(url)

        relative = unquote(parsed.path).lstrip("/")

        if not relative or relative.endswith("/"):
            relative += "index"

        if parsed.query:
            digest = hashlib.sha256(
                parsed.query.encode()
            ).hexdigest()[:10]

            name, ext = os.path.splitext(relative)
            relative = f"{name}_{digest}{ext}"

        destination = os.path.join(
            OUTPUT,
            parsed.netloc,
            relative
        )

        os.makedirs(os.path.dirname(destination), exist_ok=True)

        if os.path.exists(destination):
            continue

        response = session.get(
            url,
            timeout=30
        )

        response.raise_for_status()

        with open(destination, "wb") as file:
            file.write(response.content)

        print(
            f"[{index}/{len(urls)}] "
            f"{resource_type}: {relative} "
            f"({len(response.content):,} bytes)"
        )

    except Exception as error:
        print(f"[FAILED] {url}: {error}")

print("\n[+] Download finished!")
print(f"[+] Files saved in: {OUTPUT}")
