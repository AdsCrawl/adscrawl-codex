#!/usr/bin/env python3
"""Dependency-free one-shot AdsCrawl client for the Codex plugin."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DEFAULT_API = "https://api.adscrawl.net"
AUTH_API = DEFAULT_API


def credential_path() -> Path:
    return Path.home() / ".config" / "adscrawl" / "codex.env"


def api_key() -> str:
    key = os.environ.get("ADSCRAWL_API_KEY", "").strip()
    if not key:
        path = credential_path()
        if path.exists():
            if path.is_symlink():
                raise ValueError(f"Credential file must not be a symlink: {path}")
            if os.name != "nt" and path.stat().st_mode & 0o077:
                raise ValueError(f"Credential file permissions are too broad: {path}")
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("ADSCRAWL_API_KEY="):
                    key = line.partition("=")[2].strip()
                    break
    if not key or "\n" in key or "\r" in key:
        raise ValueError("Set ADSCRAWL_API_KEY or run `adscrawl.py auth` to connect your account")
    return key


def save_api_key(key: str) -> Path:
    if not key or any(character in key for character in "\r\n"):
        raise RuntimeError("AdsCrawl returned an invalid API key")
    path = credential_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise RuntimeError(f"Credential directory must not be a symlink: {path.parent}")
    if os.name != "nt":
        path.parent.chmod(0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"ADSCRAWL_API_KEY={key}\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def auth_request(endpoint: str, body: dict) -> tuple[int, dict, object]:
    request = Request(
        AUTH_API + endpoint,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "adscrawl-codex/0.1.4"},
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            status = response.status
            headers = response.headers
            raw = response.read(65536)
    except HTTPError as exc:
        status = exc.code
        headers = exc.headers
        raw = exc.read(65536)
    except URLError as exc:
        raise RuntimeError(f"AdsCrawl connection failed: {exc.reason}") from None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError(f"AdsCrawl auth returned invalid JSON (HTTP {status})") from None
    if not isinstance(payload, dict):
        raise RuntimeError(f"AdsCrawl auth returned an invalid response (HTTP {status})")
    return status, payload, headers


def authenticate(args: argparse.Namespace) -> None:
    try:
        api_key()
    except ValueError as exc:
        if credential_path().exists() or credential_path().is_symlink():
            raise
    else:
        print("AdsCrawl is already connected; reusing the existing API key.")
        return

    email = (args.email or input("AdsCrawl account email: ")).strip()
    project = (args.project_name or input("Project name for this key: ")).strip()
    if not email or "@" not in email or any(character.isspace() for character in email):
        raise ValueError("Enter a valid AdsCrawl account email")
    if not project or len(project) > 60:
        raise ValueError("Project name must contain 1–60 characters")

    status, payload, _ = auth_request(
        "/auth/agent/identity",
        {"type": "service_auth", "login_hint": email, "api_key_name": project},
    )
    if status != 201 or payload.get("ok") is not True:
        raise RuntimeError(f"AdsCrawl setup failed (HTTP {status})")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("claim_token"), str):
        raise RuntimeError("AdsCrawl setup returned an invalid claim")
    claim = data.get("claim")
    if not isinstance(claim, dict):
        raise RuntimeError("AdsCrawl setup returned an invalid confirmation link")
    confirmation_url = claim.get("verification_uri_complete") or claim.get("verification_uri")
    if not isinstance(confirmation_url, str):
        raise RuntimeError("AdsCrawl setup returned no confirmation link")
    parsed = urlsplit(confirmation_url)
    if parsed.scheme != "https" or parsed.hostname != "app.adscrawl.net" or parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise RuntimeError("AdsCrawl setup returned an unexpected confirmation link")
    if data["claim_token"] in confirmation_url:
        raise RuntimeError("AdsCrawl setup put a private token in the confirmation link")
    expires_in = claim.get("expires_in")
    interval = claim.get("interval")
    if not isinstance(expires_in, int) or expires_in <= 0 or not isinstance(interval, int):
        raise RuntimeError("AdsCrawl setup returned invalid timing")
    interval = max(5, interval)
    print(f"Open this link and approve the key for {project}:\n{confirmation_url}", flush=True)
    if not claim.get("verification_uri_complete"):
        print(f"Enter setup code: {claim.get('user_code', '')}", flush=True)
    print(f"This setup request expires in {expires_in} seconds. Waiting for your approval...", flush=True)

    deadline = time.monotonic() + expires_in
    while time.monotonic() + interval < deadline:
        time.sleep(interval)
        status, result, headers = auth_request(
            "/auth/agent/token", {"claim_token": data["claim_token"]}
        )
        if status == 200 and result.get("ok") is True:
            result_data = result.get("data")
            if not isinstance(result_data, dict) or not isinstance(result_data.get("api_key"), str):
                raise RuntimeError("AdsCrawl returned no API key")
            path = save_api_key(result_data["api_key"])
            print(f"AdsCrawl connected. API key saved privately at {path}.")
            return
        if status == 400 and result.get("code") == "authorization_pending":
            continue
        if status == 429 and result.get("code") in ("slow_down", "rate_limited"):
            retry_after = headers.get("Retry-After", "") if headers else ""
            try:
                interval = max(interval, int(retry_after))
            except ValueError:
                interval = max(interval, 10)
            continue
        if status == 503 and result.get("code") == "temporarily_unavailable":
            interval = max(interval, 10)
            continue
        if status == 409 and result.get("code") == "access_denied":
            raise RuntimeError("AdsCrawl authorization was denied")
        if status == 410 and result.get("code") == "expired_token":
            raise RuntimeError("AdsCrawl authorization request expired")
        raise RuntimeError(f"AdsCrawl authorization failed (HTTP {status})")
    raise RuntimeError("AdsCrawl authorization request expired")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def http_url(value: str, label: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{label} must be an HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"{label} must not contain credentials or a fragment")
    return value


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Render pages with AdsCrawl")
    commands = root.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth", help="Connect an AdsCrawl account through browser approval")
    auth.add_argument("--email", help="AdsCrawl account email; prompted if omitted")
    auth.add_argument("--project-name", help="Name shown in the authorization dialog; prompted if omitted")
    for name in ("render", "screenshot"):
        command = commands.add_parser(name)
        command.add_argument("--url", required=True)
        command.add_argument("--output", type=Path)
        command.add_argument("--wait-until", choices=("domcontentloaded", "load", "networkidle"))
        command.add_argument("--country", help="Uppercase managed routing country code")
        command.add_argument("--timeout-ms", type=int, default=60000)
    commands.choices["render"].add_argument("--format", choices=("markdown", "html", "article"), default="markdown")
    screenshot = commands.choices["screenshot"]
    screenshot.add_argument("--width", type=int, default=1440)
    screenshot.add_argument("--height", type=int, default=900)
    screenshot.add_argument("--viewport-only", action="store_true")
    return root


def run(args: argparse.Namespace) -> None:
    if args.command == "auth":
        authenticate(args)
        return
    key = api_key()
    target = http_url(args.url, "--url")
    api = http_url(os.environ.get("ADSCRAWL_BASE_URL", DEFAULT_API), "ADSCRAWL_BASE_URL")
    if urlsplit(api).query:
        raise ValueError("ADSCRAWL_BASE_URL must not contain a query")
    if args.timeout_ms <= 0 or args.timeout_ms > 3_600_000:
        raise ValueError("--timeout-ms must be between 1 and 3600000")
    if args.country and (not args.country.isascii() or not args.country.isalpha() or not args.country.isupper()):
        raise ValueError("--country must be uppercase letters")
    if args.command == "screenshot" and (args.width <= 0 or args.height <= 0):
        raise ValueError("viewport dimensions must be positive")
    if args.command == "screenshot" and args.output is None:
        raise ValueError("--output is required for screenshots")

    body = {
        "url": target,
        "waitUntil": args.wait_until or ("load" if args.command == "screenshot" else "domcontentloaded"),
        "timeoutMs": args.timeout_ms,
        "userAgentMode": "random",
        "userAgentOs": "windows",
    }
    if args.country:
        body["countryCode"] = args.country
    if args.command == "render":
        body["contentMode"] = "json" if args.format == "article" else args.format
        endpoint = "/html"
    else:
        body["viewport"] = {"width": args.width, "height": args.height}
        body["fullPage"] = not args.viewport_only
        endpoint = "/screenshot"

    request = Request(
        api.rstrip("/") + endpoint,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": key, "User-Agent": "adscrawl-codex/0.1.4"},
        method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=max(90, args.timeout_ms / 1000 + 15)) as response:
            payload = response.read()
    except HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace").replace(key, "[REDACTED]")
        raise RuntimeError(f"AdsCrawl HTTP {exc.code}: {detail}") from None
    except URLError as exc:
        raise RuntimeError(f"AdsCrawl connection failed: {exc.reason}") from None

    if args.command == "screenshot":
        if not payload.startswith(PNG_SIGNATURE):
            raise RuntimeError("AdsCrawl returned an invalid PNG screenshot")
    elif args.format == "article":
        try:
            article = json.loads(payload)
        except json.JSONDecodeError:
            raise RuntimeError("AdsCrawl returned invalid article JSON") from None
        if not isinstance(article, dict) or not isinstance(article.get("textContent"), str):
            raise RuntimeError("AdsCrawl returned an unexpected article shape")
        payload = (json.dumps(article, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    elif not payload.strip():
        raise RuntimeError("AdsCrawl returned empty page content")

    if args.output:
        args.output.write_bytes(payload)
        print(args.output)
    else:
        sys.stdout.buffer.write(payload)


def main() -> int:
    try:
        run(parser().parse_args())
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"adscrawl: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
