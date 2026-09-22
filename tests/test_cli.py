"""Exercise request construction, outputs, and secret-safe failures."""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError


SCRIPT = Path(__file__).resolve().parents[1] / "plugins/adscrawl/scripts/adscrawl.py"
SPEC = importlib.util.spec_from_file_location("adscrawl_plugin_cli", SCRIPT)
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)
PNG = b"\x89PNG\r\n\x1a\n" + b"fake png body"


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.payload = payload
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def read(self, _size=None):
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


class SequenceOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return next(self.responses)


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

    def test_browser_approval_saves_key_without_printing_secrets(self):
        claim = {
            "ok": True,
            "data": {
                "claim_token": "private-claim",
                "claim": {
                    "verification_uri_complete": "https://app.adscrawl.net/dashboard/keys?agent_setup=1&agent_code=ABCD-EFGH",
                    "expires_in": 600,
                    "interval": 5,
                },
            },
        }
        pending = {"code": "authorization_pending"}
        approved = {"ok": True, "data": {"api_key": "private-api-key"}}
        opener = SequenceOpener([
            Response(json.dumps(claim).encode(), status=201),
            Response(json.dumps(pending).encode(), status=400),
            Response(json.dumps(approved).encode()),
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials = Path(temp_dir) / "codex.env"
            output = io.StringIO()
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(cli, "credential_path", return_value=credentials),
                patch.object(cli, "build_opener", return_value=opener),
                patch.object(cli.time, "sleep"),
                redirect_stdout(output),
            ):
                cli.run(cli.parser().parse_args(["auth", "--email", "user@example.com", "--project-name", "My project"]))
                self.assertEqual(cli.api_key(), "private-api-key")
            self.assertEqual(credentials.read_text(), "ADSCRAWL_API_KEY=private-api-key\n")
            if os.name != "nt":
                self.assertEqual(credentials.stat().st_mode & 0o777, 0o600)
            self.assertIn("https://app.adscrawl.net/dashboard/keys?agent_setup=1&agent_code=ABCD-EFGH", output.getvalue())
            self.assertNotIn("private-claim", output.getvalue())
            self.assertNotIn("private-api-key", output.getvalue())
            self.assertEqual([request.full_url for request in opener.requests], [
                "https://api.adscrawl.net/auth/agent/identity",
                "https://api.adscrawl.net/auth/agent/token",
                "https://api.adscrawl.net/auth/agent/token",
            ])
            self.assertEqual(json.loads(opener.requests[0].data), {
                "type": "service_auth", "login_hint": "user@example.com", "api_key_name": "My project"
            })
            self.assertEqual(json.loads(opener.requests[1].data), {"claim_token": "private-claim"})

    def test_auth_reuses_existing_environment_key(self):
        with patch.dict(os.environ, {"ADSCRAWL_API_KEY": "existing-key"}, clear=True), patch.object(cli, "build_opener") as opener:
            with redirect_stdout(io.StringIO()) as output:
                cli.run(cli.parser().parse_args(["auth"]))
            opener.assert_not_called()
            self.assertIn("already connected", output.getvalue())

    def test_denied_authorization_does_not_save_key(self):
        claim = {
            "ok": True,
            "data": {
                "claim_token": "private-claim",
                "claim": {
                    "verification_uri_complete": "https://app.adscrawl.net/dashboard/keys?agent_code=ABCD-EFGH",
                    "expires_in": 600,
                    "interval": 5,
                },
            },
        }
        opener = SequenceOpener([
            Response(json.dumps(claim).encode(), status=201),
            Response(json.dumps({"code": "access_denied"}).encode(), status=409),
        ])
        with tempfile.TemporaryDirectory() as temp_dir:
            credentials = Path(temp_dir) / "codex.env"
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(cli, "credential_path", return_value=credentials),
                patch.object(cli, "build_opener", return_value=opener),
                patch.object(cli.time, "sleep"),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaisesRegex(RuntimeError, "denied"):
                    cli.run(cli.parser().parse_args(["auth", "--email", "user@example.com", "--project-name", "My project"]))
            self.assertFalse(credentials.exists())


if __name__ == "__main__":
    unittest.main()
