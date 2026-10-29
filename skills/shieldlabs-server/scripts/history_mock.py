#!/usr/bin/env python3
"""A local stand-in for the ShieldLabs History API, for offline tests of a backend.

Usage: python3 history_mock.py [--port 4010] [--host 127.0.0.1] [--rows ROWS.json] [--only-rows] [--contract current|legacy] [--quiet]

Answers domain-scoped identification card reads with the current JSON shape of the History
API: {"data": [rows, newest first], "total": n}, History rows with History field names (score,
created_at, ip, country, score_details, is_* columns). Point a server SDK at it with
SHIELDLABS_API_BASE_URL=http://127.0.0.1:4010 and a placeholder key such as
sec_test0000-test0000-test0000.

- Current rows use identification_id by default; --contract legacy emits request_id instead.
- Without --rows, every request_id lookup finds one trusted identification (Risk Score 0, no
  flags) observed just now, so the freshness check passes.
- ROWS.json maps request IDs to overrides of History row fields, for example
  {"<request id>": {"score": 80, "is_antidetect": true, "minutes_ago": 10}}. "minutes_ago" moves
  created_at into the past. null means "not found" (unverified) for that request ID.
- Lookups by device_id, visitor_id, user_hid, ip, session_id and cookie_id search the rows of
  ROWS.json. --only-rows makes request IDs that are not in ROWS.json "not found" too.

Standard library only. It listens on 127.0.0.1 by default; never expose it to a network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlsplit

LOOKUPS = ("ip", "user_hid", "visitor_id", "request_id", "identification_id", "device_id", "session_id", "cookie_id")
UUID_LOOKUPS = {"visitor_id", "request_id", "identification_id", "device_id", "session_id", "cookie_id"}
PATH_RE = re.compile(r"^/api/v1/domains/([0-9a-fA-F-]{36})/history/identifications/([^/]+)/?$")
TEST_DOMAIN = "11111111-1111-4111-8111-111111111111"
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
IPV4_RE = re.compile(r"^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$")
FLAG_COLUMNS = (
    "is_vpn", "is_tor", "is_proxy", "is_datacenter", "is_abuser", "is_privacy_relay",
    "is_stun_not_checked", "check_incomplete", "is_antidetect", "is_os_mismatch",
    "is_os_not_detected", "is_timezone_mismatch", "is_js_disabled", "is_browser_automation",
    "is_incognito", "is_search_bot",
)
CURRENT_FLAG_COLUMNS = tuple(dict.fromkeys(FLAG_COLUMNS + (
    "is_latency_test", "is_device_spoof", "is_rate_limited", "is_ai_bot", "is_ai_browser",
)))
NAMESPACE = uuid.UUID("6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a")


def history_time(moment: datetime) -> str:
    """created_at as the History API writes it: YYYY-MM-DD HH:MM:SS.mmm in UTC."""
    moment = moment.astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%d %H:%M:%S.") + f"{moment.microsecond // 1000:03d}"


def make_row(request_id: str, overrides: Optional[Dict[str, Any]] = None, contract: str = "current") -> Dict[str, Any]:
    """One History row: a trusted identification observed now, then the overrides."""
    if contract not in ("current", "legacy"):
        raise ValueError("contract must be current or legacy")
    overrides = dict(overrides or {})
    moment = datetime.now(timezone.utc) - timedelta(minutes=float(overrides.pop("minutes_ago", 0)))
    row: Dict[str, Any] = {
        ("identification_id" if contract == "current" else "request_id"): request_id.lower(),
        "session_id": str(uuid.uuid5(NAMESPACE, "session:" + request_id.lower())),
        "cookie_id": "4449bb58-590c-444c-ae1f-d1ddc768dbdd",
        "domain": "example.com",
        "user_hid": "anonymous",
        "device_id": "ac7c303d-971b-41d1-8e25-cd5b46b46aed",
        "visitor_id": "bde0e249-20d8-4544-838c-ed9a0b6d7a36",
        "ip": "203.0.113.24",
        "country": "Germany",
        "os": "Windows",
        "browser": "Chrome",
        "device_type": "desktop",
        "connection_type": "direct",
        "score": 0,
        "score_details": "",
        "created_at": history_time(moment),
        "ver": int(time.time() * 1000),
    }
    row.update({column: False for column in (CURRENT_FLAG_COLUMNS if contract == "current" else FLAG_COLUMNS)})
    row.update(overrides)
    return row


def load_rows(path: Optional[Path], contract: str = "current") -> Dict[str, Optional[Dict[str, Any]]]:
    """Reads ROWS.json: {request_id: overrides or null}."""
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object that maps request IDs to overrides or null")
    rows: Dict[str, Optional[Dict[str, Any]]] = {}
    for request_id, overrides in data.items():
        if not UUID_RE.match(request_id):
            raise ValueError(f"{path}: {request_id!r} is not a request ID (a UUID)")
        if overrides is not None and not isinstance(overrides, dict):
            raise ValueError(f"{path}: the value for {request_id} must be an object or null")
        rows[request_id.lower()] = None if overrides is None else make_row(request_id, overrides, contract=contract)
    return rows


class HistoryMock:
    """The lookup logic, separate from HTTP so that tests can call it directly."""

    def __init__(self, rows: Dict[str, Optional[Dict[str, Any]]], only_rows: bool = False, contract: str = "current") -> None:
        if contract not in ("current", "legacy"):
            raise ValueError("contract must be current or legacy")
        self.rows = rows
        self.contract = contract
        self.only_rows = only_rows

    def search(self, lookup: str, value: str, limit: int, offset: int) -> Tuple[int, Dict[str, Any]]:
        if lookup not in LOOKUPS:
            return 400, {"error": f"unknown lookup type {lookup!r}"}
        if lookup in UUID_LOOKUPS and not UUID_RE.match(value):
            return 500, {"error": f"cannot parse {value!r} as a UUID"}  # legacy fixture helper only
        if lookup == "ip" and not IPV4_RE.match(value):
            return 500, {"error": f"cannot parse {value!r} as an IPv4 address"}
        if lookup in ("request_id", "identification_id"):
            key = value.lower()
            if key in self.rows:
                found = [self.rows[key]] if self.rows[key] is not None else []
            else:
                found = [] if self.only_rows else [make_row(key, contract=self.contract)]
        else:
            def matches(row: Dict[str, Any]) -> bool:  # UUIDs match in any case, the rest exactly
                field = str(row.get(lookup, ""))
                return field.lower() == value.lower() if lookup in UUID_LOOKUPS else field == value

            found = [row for row in self.rows.values() if row is not None and matches(row)]
        rows: List[Dict[str, Any]] = sorted((r for r in found if r is not None), key=lambda r: str(r["created_at"]), reverse=True)
        limit = limit if 1 <= limit <= 100 else 20  # legacy fixture helper only
        offset = max(offset, 0)
        return 200, {"data": rows[offset:offset + limit], "total": len(rows)}


def make_handler(mock: HistoryMock, quiet: bool = False) -> type:
    class Handler(BaseHTTPRequestHandler):
        server_version = "shieldlabs-history-mock"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 (http.server naming)
            if not quiet:
                super().log_message(format, *args)

        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            url = urlsplit(self.path)
            auth = self.headers.get("Authorization", "")
            scheme, _, token = auth.partition(" ")
            if scheme.lower() != "bearer" or not token.strip():
                self.reply(401, {"error": "missing or invalid authorization header"})
                return
            if url.path == "/api/v1/domains":
                self.reply(200, {"domains": [{"id": TEST_DOMAIN, "domain": "example.com"}]})
                return
            if url.path.startswith("/api/v1/history/"):
                self.reply(410, {"error": "endpoint_retired"})
                return
            match = PATH_RE.match(url.path)
            if not match:
                self.reply(404, {"error": "not found"})
                return
            domain, identifier = match.group(1).lower(), unquote(match.group(2))
            if not UUID_RE.fullmatch(domain) or not UUID_RE.fullmatch(identifier):
                self.reply(400, {"error": "invalid_request"})
                return
            status, result = mock.search("identification_id", identifier, 1, 0)
            if status != 200:
                self.reply(status, result)
                return
            if not result["data"]:
                self.reply(404, {"error": "not_found"})
                return
            row = result["data"][0]
            score = row["score"]
            if not 0 <= score <= 100:
                self.reply(429, {"error": "rate_limited"})
                return
            at = str(row["created_at"]).replace(" ", "T") + "Z"
            card = {"type": "identification", "id": identifier.lower(), "domain_id": domain,
                    "domain": row.get("site_domain") or "example.com", "created_at": at,
                    "risk": {"state": "ok", "score": score, "band": "trusted" if score < 30 else "suspicious" if score < 60 else "dangerous", "as_of": at},
                    "signals": {"state": "unavailable", "items": []}, "public_ip": row.get("ip"),
                    "country": row.get("country"), "visitor_id": row.get("visitor_id"), "device_id": row.get("device_id"), "user_hid": row.get("user_hid")}
            self.reply(200, {"data": card})

        def reply(self, status: int, body: Dict[str, Any]) -> None:
            payload = (json.dumps(body) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def to_int(value: str, default: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="A local stand-in for the ShieldLabs History API.")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=4010, help="port to listen on (default 4010)")
    parser.add_argument("--rows", type=Path, help="JSON file that maps request IDs to row overrides or null")
    parser.add_argument("--only-rows", action="store_true", help="request IDs missing from --rows are not found")
    parser.add_argument("--quiet", action="store_true", help="do not log requests")
    parser.add_argument("--contract", choices=("current", "legacy"), default="current",
                        help="wire ID contract (default current: identification_id)")
    args = parser.parse_args(argv[1:])
    try:
        mock = HistoryMock(load_rows(args.rows, contract=args.contract), only_rows=args.only_rows, contract=args.contract)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((args.host, args.port), make_handler(mock, quiet=args.quiet))
    print(f"History API mock on http://{args.host}:{server.server_address[1]}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
