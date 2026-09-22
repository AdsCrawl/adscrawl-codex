#!/usr/bin/env python3
"""Dependency-free one-shot AdsCrawl client for the Codex plugin."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DEFAULT_API = "https://api.adscrawl.net"


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
    key = os.environ.get("ADSCRAWL_API_KEY", "").strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("Set ADSCRAWL_API_KEY to a valid API key")
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
        headers={"Content-Type": "application/json", "X-API-Key": key, "User-Agent": "adscrawl-codex/0.1.3"},
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
