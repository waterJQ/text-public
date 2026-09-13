"""Notify IndexNow of explicitly public URLs after a successful Pages deployment."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

from publish import PUBLIC, SLUGS


def notify():
    key = Path(__file__).with_name("indexnow-key.txt").read_text("utf-8").strip()
    if len(key) != 32 or any(char not in "0123456789abcdef" for char in key):
        raise ValueError("Invalid site verification key")
    key_url = PUBLIC + "indexnow-key.txt"
    with urlopen(key_url, timeout=30) as response:
        if response.status != 200 or response.read(128).decode("utf-8").strip() != key:
            raise RuntimeError("Published verification file differs from local key")
    urls = [PUBLIC + "contents.html"]
    for slug in SLUGS:
        urls.extend([PUBLIC + slug + "/", PUBLIC + slug + ".txt"])
    payload = {"host": "text-public.jc5726.com", "key": key,
               "keyLocation": key_url, "urlList": urls}
    request = Request("https://api.indexnow.org/indexnow", data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    with urlopen(request, timeout=30) as response:
        if response.status not in (200, 202):
            raise RuntimeError("Index notification was not accepted")
        print(json.dumps({"status": response.status, "submitted": len(urls),
                          "indexingConfirmed": False, "codexAccessConfirmed": False}))


if __name__ == "__main__":
    notify()
