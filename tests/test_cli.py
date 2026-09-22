"""Exercise request construction, outputs, and secret-safe failures."""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


SCRIPT = Path(__file__).resolve().parents[1] / "plugins/adscrawl/scripts/adscrawl.py"
SPEC = importlib.util.spec_from_file_location("adscrawl_plugin_cli", SCRIPT)
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)
PNG = b"\x89PNG\r\n\x1a\n" + b"fake png body"


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def read(self):
        return self.payload


class Opener:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.request = None

    def open(self, request, timeout):
        self.request = request
        if self.error:
            raise self.error
        return Response(self.payload)


class CLITests(unittest.TestCase):
    def run_cli(self, argv, opener, key="test-secret"):
        env = {"ADSCRAWL_API_KEY": key, "ADSCRAWL_BASE_URL": "http://127.0.0.1:8123"}
        if key is None:
            env.pop("ADSCRAWL_API_KEY")
        with patch.dict(os.environ, env, clear=True), patch.object(cli, "build_opener", return_value=opener):
            cli.run(cli.parser().parse_args(argv))

    def test_render_and_screenshot_request_shapes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "page.md"
            opener = Opener(b"# Rendered heading\n")
            self.run_cli(["render", "--url", "https://example.com/", "--country", "US", "--output", str(output)], opener)
            self.assertEqual(output.read_bytes(), b"# Rendered heading\n")
            body = json.loads(opener.request.data)
            self.assertEqual(opener.request.full_url, "http://127.0.0.1:8123/html")
            self.assertEqual((body["contentMode"], body["countryCode"]), ("markdown", "US"))
            self.assertEqual(opener.request.get_header("X-api-key"), "test-secret")

            output = Path(temp_dir) / "page.png"
            opener = Opener(PNG)
            self.run_cli(["screenshot", "--url", "https://example.com/", "--viewport-only", "--output", str(output)], opener)
            self.assertEqual(output.read_bytes(), PNG)
            body = json.loads(opener.request.data)
            self.assertEqual(opener.request.full_url, "http://127.0.0.1:8123/screenshot")
            self.assertEqual(body["viewport"], {"width": 1440, "height": 900})
            self.assertFalse(body["fullPage"])

    def test_missing_key_and_error_body_redaction(self):
        with self.assertRaisesRegex(ValueError, "ADSCRAWL_API_KEY"):
            self.run_cli(["render", "--url", "https://example.com/"], Opener(), key=None)
        error = HTTPError("http://127.0.0.1:8123/html", 422, "Unprocessable", {}, io.BytesIO(b"request rejected: test-secret"))
        with self.assertRaises(RuntimeError) as raised:
            self.run_cli(["render", "--url", "https://example.com/error"], Opener(error=error))
        self.assertIn("HTTP 422", str(raised.exception))
        self.assertNotIn("test-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
