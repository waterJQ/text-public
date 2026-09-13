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
PUBLIC = "https://text-public.jc5726.com/"
RAW = "https://raw.githubusercontent.com/waterJQ/text-public/main/writing-assistant.md"
MAX_BYTES = 2 * 1024 * 1024
TITLES = {"writing-assistant": "文字內容優化助手", "ui-guidelines": "介面視覺規則", "cae-news-digest": "CAE 新聞統整", "taiwan-arts-event-search": "全台藝文活動搜尋", "yilan-upcoming-events": "宜蘭近期活動"}
SLUGS = ("writing-assistant", "ui-guidelines", "cae-news-digest", "taiwan-arts-event-search", "yilan-upcoming-events")


def publish(content, output, updated=None, available=True, slug="writing-assistant"):
    if slug not in SLUGS:
        raise ValueError("Unknown public document")
    primary = slug == "writing-assistant"
    page_name = "index.html" if primary else slug + ".html"
    manifest_name = "publication.json" if primary else slug + ".publication.json"
    public_url = PUBLIC + slug
    source_url = SOURCE if primary else SOURCE.replace("writing-assistant", slug)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest_path = output / manifest_name
    previous = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}
    stamp = previous.get("publishedAt") if previous.get("sha256") == digest else None
    stamp = stamp or updated or datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d %H:%M")
    heading = re.search(r"^#\s+(.+)$", content, re.M)
    title = heading.group(1).strip() if heading else "文字內容"
    safe_title = html.escape(title)
    safe_content = html.escape(content)
    doc = f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title><meta name="description" content="{safe_title}完整公開內容">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
<link rel="canonical" href="{public_url}"><link rel="alternate" type="text/plain" href="{slug}.txt">
<link rel="stylesheet" href="reader.css"><link rel="icon" href="favicon.svg" type="image/svg+xml"></head>
<body><main><pre>{safe_content}</pre></main></body></html>'''
    doc = doc.replace("</main>", f'<p>發布時間 {stamp}</p></main>')
    links = "\n".join(f"| {TITLES[item]} | [閱讀]({PUBLIC}{item}/) | [純文字]({PUBLIC}{item}.txt) |" for item in SLUGS)
    rows = "".join(f'<tr><td>{TITLES[item]}</td><td><a href="{PUBLIC}{item}/">閱讀</a></td><td><a href="{PUBLIC}{item}.txt">純文字</a></td></tr>' for item in SLUGS)
    catalog = f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>公開閱讀目錄</title><link rel="icon" href="favicon.svg"><link rel="stylesheet" href="reader.css"></head><body><main><h1>公開閱讀目錄</h1><table><thead><tr><th>內容</th><th>閱讀網頁</th><th>純文字</th></tr></thead><tbody>{rows}</tbody></table></main></body></html>'
    files = {
        "contents.html": catalog,
        page_name: doc,
        slug + ".md": content,
        slug + ".txt": content,
        "README.md": f"# 公開閱讀目錄\n\n[網站目錄]({PUBLIC}contents.html)\n\n| 內容 | 網頁 | AI 文字 |\n|---|---|---|\n{links}\n\n發布時間 {stamp}\n\n---\n\n" + content,
        manifest_name: json.dumps({"sha256": digest, "publishedAt": stamp, "verifiedOn": datetime.now(timezone(timedelta(hours=8))).strftime("%Y/%m/%d"), "source": source_url, "available": available}, ensure_ascii=False, indent=2) + "\n",
        "robots.txt": f"User-agent: *\nAllow: /\n\nUser-agent: OAI-SearchBot\nAllow: /\n\nUser-agent: ChatGPT-User\nAllow: /\n\nUser-agent: GPTBot\nDisallow: /\n\nSitemap: {PUBLIC}sitemap.xml\n",
        "sitemap.xml": f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{PUBLIC}</loc></url><url><loc>{PUBLIC}ui-guidelines.html</loc></url></urlset>',
        ".nojekyll": "",
        "favicon.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#eaf5fc"/><path d="M18 16h28M18 28h28M18 40h20M18 52h14" stroke="#111" stroke-width="4"/></svg>',
    }
    if not primary:
        del files["README.md"]
    files["sitemap.xml"] = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>{PUBLIC}{item}</loc></url>" for item in SLUGS) + "</urlset>"
    files[slug + "/index.html"] = doc.replace('href="reader.css"', 'href="../reader.css"').replace('href="favicon.svg"', 'href="../favicon.svg"').replace(f'href="{slug}.txt"', f'href="../{slug}.txt"')
    for name, value in files.items():
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        (output / name).write_text(value, encoding="utf-8", newline="\n")
    return digest


def fetch_source(source=SOURCE):
    request = Request(source, headers={"User-Agent": "text-public-publisher/1.0"})
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
    text = data.decode("utf-8")
    if not text.strip():
        raise RuntimeError("Public source is blank")
    return text, True


def synchronize(output):
    failures = []
    for slug in SLUGS:
        try:
            content, available = fetch_source(SOURCE.replace("writing-assistant", slug))
            publish(content, output, available=available, slug=slug)
        except Exception:
            failures.append(slug)
    if failures:
        raise RuntimeError("Source unavailable; retained previous content: " + ", ".join(failures))


if __name__ == "__main__":
    synchronize(Path(__file__).parent)
