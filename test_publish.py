import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from publish import publish, fetch_source, synchronize, SOURCE, MAX_BYTES


class PublicationTests(unittest.TestCase):
    def test_new_documents_have_independent_aliases_and_withdrawal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for slug in ("cae-news-digest", "taiwan-arts-event-search", "yilan-upcoming-events"):
                content = "# " + slug + "\n完整正文"
                publish(content, root, slug=slug)
                self.assertEqual((root / (slug + ".txt")).read_text("utf-8"), content)
                page = (root / slug / "index.html").read_text("utf-8")
                self.assertIn("https://text-public.jc5726.com/" + slug, page)
                self.assertIn('href="../reader.css"', page)
                self.assertIn("發布時間", page)
                publish("內容已停止公開", root, slug=slug, available=False)
                for name in (slug + ".html", slug + "/index.html", slug + ".txt", slug + ".md"):
                    self.assertNotIn("完整正文", (root / name).read_text("utf-8"))

    def test_text_integrity_and_html_escaping(self):
        content = '# 標題 <script>alert(1)</script>\n內容 & "引號"\n'
        with tempfile.TemporaryDirectory() as folder:
            publish(content, folder, "2026/09/11 22:00")
            root = Path(folder)
            self.assertEqual((root / "writing-assistant.md").read_text("utf-8"), content)
            self.assertEqual((root / "writing-assistant.txt").read_text("utf-8"), content)
            page = (root / "index.html").read_text("utf-8")
            self.assertNotIn("<script>", page)
            self.assertIn("&lt;script&gt;", page)
            before = (root / "publication.json").read_bytes()
            publish(content, folder, "2026/09/12 10:00")
            self.assertEqual((root / "publication.json").read_bytes(), before)
            publish("# 更新後\n新內容", folder, "2026/09/12 10:00")
            self.assertEqual(json.loads((root / "publication.json").read_text("utf-8"))["publishedAt"], "2026/09/12 10:00")

    def test_documents_are_independent_and_plain(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            publish("writing", root)
            before = (root / "publication.json").read_bytes()
            publish("UI <script>bad()</script>", root, slug="ui-guidelines")
            self.assertEqual((root / "writing-assistant.md").read_text("utf-8"), "writing")
            self.assertEqual((root / "publication.json").read_bytes(), before)
            self.assertEqual((root / "ui-guidelines.md").read_text("utf-8"), "UI <script>bad()</script>")
            for name in ["index.html", "ui-guidelines.html"]:
                page = (root / name).read_text("utf-8")
                self.assertNotIn("<nav", page)
                self.assertNotIn("<header", page)
                self.assertNotIn("<script>", page)
            self.assertIn("ui-guidelines.txt", json.loads((root / "ui-guidelines.publication.json").read_text("utf-8"))["source"])

    def test_transient_failure_does_not_prevent_other_withdrawal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            publish("writing", root)
            publish("old UI", root, slug="ui-guidelines")
            with patch("publish.fetch_source", side_effect=[RuntimeError("temporary"), ("withdrawn", False)]):
                with self.assertRaises(RuntimeError):
                    synchronize(root)
            self.assertEqual((root / "writing-assistant.md").read_text("utf-8"), "writing")
            self.assertEqual((root / "ui-guidelines.md").read_text("utf-8"), "withdrawn")
            self.assertFalse(json.loads((root / "ui-guidelines.publication.json").read_text("utf-8"))["available"])

    def test_explicit_withdrawal_replaces_live_content(self):
        headers = Message()
        headers["X-Public-Availability"] = "withdrawn"
        with patch("publish.urlopen", side_effect=HTTPError(SOURCE, 503, "disabled", headers, None)):
            text, available = fetch_source()
        self.assertFalse(available)
        with tempfile.TemporaryDirectory() as folder:
            publish("原內容", folder)
            publish(text, folder, available=available)
            for name in ["index.html", "writing-assistant.md", "writing-assistant.txt", "README.md"]:
                result = (Path(folder) / name).read_text("utf-8")
                self.assertNotIn("原內容", result)
                self.assertIn("內容已停止公開", result)

    def test_transient_error_is_not_treated_as_withdrawal(self):
        with patch("publish.urlopen", side_effect=HTTPError(SOURCE, 503, "unavailable", Message(), None)):
            with self.assertRaises(HTTPError):
                fetch_source()

    def test_rejects_wrong_content_type_oversize_and_invalid_utf8(self):
        for mime, data in [("text/html", b"challenge"), ("text/plain", b"x" * (MAX_BYTES + 1)), ("text/plain", b"\xff")]:
            response = MagicMock()
            response.status = 200
            response.headers.get_content_type.return_value = mime
            response.read.return_value = data
            response.__enter__.return_value = response
            with patch("publish.urlopen", return_value=response):
                with self.assertRaises((RuntimeError, UnicodeDecodeError)):
                    fetch_source()


if __name__ == "__main__":
    unittest.main()
