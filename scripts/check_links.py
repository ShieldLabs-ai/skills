#!/usr/bin/env python3
"""Check the external links in the Markdown files of this repository.

Usage: python3 scripts/check_links.py [repository root] [--timeout SECONDS]

Collects every distinct http(s) URL from Markdown links, autolinks and bare URLs outside code
blocks, then sends a HEAD request to each (a GET when HEAD is refused). A URL fails when it
cannot be reached or answers 404, 410 or 5xx. 401, 403 and 429 are reported as warnings, because
some sites refuse automated requests. Relative links are checked by validate_skills.py.

Exit status: 0 when no URL fails, 1 otherwise. Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_skills import SKIP_DIRS, markdown_lines  # noqa: E402

URL_RE = re.compile(r"https?://[^\s<>()\[\]`'\"]+")
TRAILING = ".,;:!?*_"
SKIP_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "example.com", "example.org", "example.net")
WARN_STATUSES = {401, 403, 405, 429}
USER_AGENT = "shieldlabs-skills-link-check/1.0 (+https://github.com/ShieldLabs-ai/skills)"


def collect(root: Path) -> Dict[str, List[str]]:
    """Maps each URL to the places (file:line) it appears."""
    found: Dict[str, List[str]] = {}
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if not (path.is_file() and path.suffix in (".md", ".mdc")):
            continue
        for number, line in markdown_lines(path.read_text(encoding="utf-8")):
            for match in URL_RE.finditer(line):
                url = match.group(0).rstrip(TRAILING)
                if skip(url):
                    continue
                found.setdefault(url, []).append(f"{path.relative_to(root).as_posix()}:{number}")
    return found


def skip(url: str) -> bool:
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0].lower()
    if any(host == h or host.endswith("." + h) for h in SKIP_HOSTS):
        return True
    return any(ch in url for ch in "{}$<>")


def request(url: str, method: str, timeout: float) -> int:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 (https only)
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def check(url: str, timeout: float) -> Tuple[str, Optional[int], Optional[str]]:
    try:
        status = request(url.split("#")[0], "HEAD", timeout)
        if status in (403, 405, 501):
            status = request(url.split("#")[0], "GET", timeout)
        return url, status, None
    except Exception as exc:  # noqa: BLE001 - report every failure the same way
        return url, None, f"{type(exc).__name__}: {exc}"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv[1:])
    root = Path(args.root)
    urls = collect(root)
    failures: Set[str] = set()
    with ThreadPoolExecutor(max_workers=8) as pool:
        for url, status, error in pool.map(lambda u: check(u, args.timeout), sorted(urls)):
            places = ", ".join(urls[url][:3])
            if error is not None or status is None:
                failures.add(url)
                print(f"FAIL  {url}  ({error})  in {places}")
            elif status in WARN_STATUSES:
                print(f"WARN  {url}  (HTTP {status})  in {places}")
            elif status >= 400:
                failures.add(url)
                print(f"FAIL  {url}  (HTTP {status})  in {places}")
    print(f"\nChecked {len(urls)} external URLs: {len(failures)} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
