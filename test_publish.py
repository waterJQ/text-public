import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from publish import publish, fetch_source, SOURCE, MAX_BYTES


class PublicationTests(unittest.TestCase):
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
