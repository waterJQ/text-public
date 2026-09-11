"""Publish only the designated public document. No credentials or private data."""
import hashlib
import html
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SOURCE = "https://text-public.water5726water5726.workers.dev/writing-assistant.txt"
PUBLIC = "https://waterjq.github.io/text-public/"
RAW = "https://raw.githubusercontent.com/waterJQ/text-public/main/writing-assistant.md"
MAX_BYTES = 2 * 1024 * 1024


def publish(content, output, updated=None, available=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest_path = output / "publication.json"
    previous = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    stamp = previous.get("publishedAt") if previous.get("sha256") == digest else None
    stamp = stamp or updated or datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M")
    heading = re.search(r"^#\s+(.+)$", content, re.M)
    title = heading.group(1).strip() if heading else "文字內容"
    safe_title = html.escape(title)
    safe_content = html.escape(content)
    doc = f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title><meta name="description" content="文字內容優化助手完整公開內容">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
<link rel="canonical" href="{PUBLIC}"><link rel="alternate" type="text/plain" href="writing-assistant.txt">
<link rel="stylesheet" href="reader.css"><link rel="icon" href="favicon.svg" type="image/svg+xml"></head>
<body><nav aria-label="閱讀導覽"><a href="#content">閱讀內容</a><a href="writing-assistant.txt">純文字</a><a href="{RAW}">AI 讀取網址</a></nav>
<main><header><h1>{safe_title}</h1><p>發布時間 {stamp}</p></header><article id="content" aria-label="完整內容"><pre>{safe_content}</pre></article></main></body></html>'''
    files = {
        "index.html": doc,
        "writing-assistant.md": content,
        "writing-assistant.txt": content,
        "README.md": f"# 文字內容公開閱讀\n\n[閱讀網頁]({PUBLIC}) · [AI 純文字網址]({RAW})\n\n發布時間 {stamp}\n\n---\n\n" + content,
        "publication.json": json.dumps({"sha256": digest, "publishedAt": stamp, "source": SOURCE, "available": available}, ensure_ascii=False, indent=2) + "\n",
        "robots.txt": f"User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nDisallow: /\n\nSitemap: {PUBLIC}sitemap.xml\n",
        "sitemap.xml": f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{PUBLIC}</loc></url></urlset>',
        ".nojekyll": "",
        "favicon.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#eaf5fc"/><path d="M18 16h28M18 28h28M18 40h20M18 52h14" stroke="#111" stroke-width="4"/></svg>',
    }
    for name, value in files.items():
        (output / name).write_text(value, encoding="utf-8", newline="\n")
    return digest


def fetch_source():
    request = Request(SOURCE, headers={"User-Agent": "text-public-publisher/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            if response.status != 200 or response.headers.get_content_type() != "text/plain":
                raise RuntimeError("Public source must return plain text and status 200")
            data = response.read(MAX_BYTES + 1)
    except HTTPError as error:
        if error.code in (404, 503) and error.headers.get("X-Public-Availability") == "withdrawn":
            return "# 內容已停止公開\n\n這份內容目前未開放閱讀。\n", False
        raise
    if not data or len(data) > MAX_BYTES:
        raise RuntimeError("Public source is empty or exceeds the size limit")
    return data.decode("utf-8"), True


if __name__ == "__main__":
    content, available = fetch_source()
    print(publish(content, Path(__file__).parent, available=available))
