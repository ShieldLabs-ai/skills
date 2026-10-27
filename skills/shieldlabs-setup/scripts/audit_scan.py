#!/usr/bin/env python3
"""Scan a project for common ShieldLabs integration problems (audit mode of shieldlabs-setup).

Usage: python3 audit_scan.py [PROJECT_DIR] [--json] [--strict]

Read-only, offline and heuristic: every finding is a lead to confirm by reading the code, not
proof, and a clean scan does not prove a correct integration. Keys found in files are masked in
the output. Exit status 0, or 1 with --strict when a high-severity finding exists. Standard
library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj", ".next",
    ".nuxt", ".cloudflare", ".output", ".svelte-kit", ".angular", ".turbo", ".vercel", ".venv", "venv", "env",
    "__pycache__", ".tox", ".mypy_cache", ".pytest_cache", "coverage", ".idea", ".vscode", ".gradle",
}
CODE_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro", ".html", ".htm",
            ".ejs", ".hbs", ".erb", ".py", ".go", ".php", ".java", ".kt", ".kts", ".cs", ".cshtml", ".razor", ".rb"}
CONFIG_EXT = {".json", ".yml", ".yaml", ".toml", ".conf", ".xml", ".properties", ".ini"}
MAX_BYTES = 1_000_000
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

CHECKS: Dict[str, Tuple[str, str, str]] = {
    "SL01": ("high", "Server credential in the source",
             "Move it to an environment variable (SHIELDLABS_API_KEY, SHIELDLABS_WEBHOOK_SECRET), rotate it in the analytics dashboard, and keep .env files out of git."),
    "SL02": ("high", "Server key exposed through a public environment prefix",
             "Only the Public Key may use a public prefix (VITE_, NEXT_PUBLIC_, NUXT_PUBLIC_, PUBLIC_). Rename the variable, read it in server code only, and rotate the key."),
    "SL03": ("high", "Server key or server SDK in client-side code",
             "Read verdicts on the server. The browser needs only the Public Key and a browser package (shieldlabs-browser)."),
    "SL04": ("high", "Webhook body may be parsed before its signature is verified",
             "Verify the raw bytes with the SDK's constructEvent before any JSON parsing, and keep global JSON parsers away from the webhook route (shieldlabs-webhooks)."),
    "SL05": ("low", "Hand-written webhook signature check",
             "Use the SDK's constructEvent: constant-time comparison, the full whsec_ secret as the key, several secrets during rotation."),
    "SL06": ("high", "No replay guard next to the verdict read",
             "Claim each request ID once (a unique key or SET NX) and pass the result to the policy helper's replay check (shieldlabs-server)."),
    "SL07": ("medium", "No freshness guard next to the verdict read",
             "Run the SDK policy helper (evaluateIdentification or its equivalent) with a 5-minute freshness window (shieldlabs-server)."),
    "SL08": ("high", "A missing identification may be treated as clean",
             "Treat a missing identification, a missing risk_score or a failed lookup as unverified: step-up, review or refuse (shieldlabs-risk-decisions)."),
    "SL09": ("high", "Email, phone number or username passed as the User HID",
             "Compute the User HID on the server with the SDK userHid helper and pass that (shieldlabs-user-linking)."),
    "SL10": ("medium", "Raw account ID passed as the User HID",
             "Hash the account ID on the server with the SDK userHid helper and pass that (shieldlabs-user-linking)."),
    "SL11": ("medium", "Identification may run on render or on route changes",
             "Call identify() in the handler of the protected action. Use runOnMount only in the component of a protected step, never in a layout (shieldlabs-browser)."),
    "SL12": ("high", "The agent is self-hosted, proxied or bundled",
             "Load the agent only from https://cdn.shieldlabs.ai through a ShieldLabs browser package (shieldlabs-browser)."),
    "SL13": ("medium", "Webhook handler without delivery deduplication",
             "Use the verified event_id and atomic durable enqueue, and answer 2xx promptly (shieldlabs-webhooks)."),
    "SL14": ("medium", "Content Security Policy without the ShieldLabs origins",
             "Add https://cdn.shieldlabs.ai to script-src, and https://rest.shieldlabs.ai wss://rest.shieldlabs.ai https://webrtc.shieldlabs.ai stun:ice.shieldlabs.ai:3478 to connect-src."),
    "SL15": ("high", "Environment file with ShieldLabs keys is committed or not ignored",
             "Add the file to .gitignore, remove it from the repository if it was committed, and rotate the keys in the analytics dashboard."),
    "SL16": ("low", "Code clears all local storage",
             "Remove your own keys instead of calling localStorage.clear(): clearing the agent's cookieID raises the browser automation risk signal."),
    "SL17": ("low", "Management API call on a request path",
             "Cache the domain profile: the Management API allows about 15 calls per minute per IP and then blocks the IP for 10 minutes."),
    "SL18": ("medium", "Request ID kept in browser storage",
             "Never cache or reuse request IDs: run one identification per protected action."),
}

SECRET_RES = [re.compile(r"\bsec_[a-z0-9]{8}-[a-z0-9]{8}-[a-z0-9]{8}\b"), re.compile(r"\bwhsec_[0-9a-f]{32}\b")]
# Key-shaped placeholders that the ShieldLabs docs and test data use: never real keys.
KNOWN_FAKE_SECRETS = {"sec_xxxxxxxx-xxxxxxxx-xxxxxxxx", "sec_test0000-test0000-test0000", "whsec_00112233445566778899aabbccddeeff",
                      "whsec_0123456789abcdef0123456789abcdef"}
PUBLIC_PREFIX_RE = re.compile(r"\b(NEXT_PUBLIC_|VITE_|NUXT_PUBLIC_|PUBLIC_|REACT_APP_|EXPO_PUBLIC_|GATSBY_)SHIELDLABS_(API_KEY|SECRET_KEY|WEBHOOK_SECRET)\b")
SERVER_ONLY_RE = re.compile(r"\b(SHIELDLABS_API_KEY|SHIELDLABS_SECRET_KEY|SHIELDLABS_WEBHOOK_SECRET|USER_HID_SECRET)\b|['\"]@shieldlabs-ai/(node|next/server)['\"]")
USE_CLIENT_RE = re.compile(r"""\A\s*(?://[^\n]*\n\s*|/\*.*?\*/\s*)*['"]use client['"]""", re.S)
INTEGRATION_RE = re.compile(r"@shieldlabs-ai/|from shieldlabs import|import shieldlabs|shieldlabs-go|use ShieldLabs\\|ai\.shieldlabs|using ShieldLabs|cdn\.shieldlabs\.ai|shieldlabs/shieldlabs-php")
WEBHOOK_HEADER_RE = re.compile(r"x-shield-signature", re.I)
WEBHOOK_CALL_RE = re.compile(r"constructEvent(Async)?\s*\(|construct_event\s*\(|ConstructEvent\s*\(|verifySignature(Async)?\s*\(|verify_signature\s*\(|VerifySignature\s*\(|WebhookSignature\.Verify\s*\(|createWebhookHandler\s*\(")
PARSE_FIRST_RE = re.compile(
    r"bodyParser\.json\s*\(|JSON\.parse\s*\(\s*(req|request)\.body|await\s+(req|request)\.json\s*\(|request\.get_json\s*\(|"
    r"request\.json\b|json\.loads\s*\(\s*request\.(body|data)|json_decode\s*\(\s*file_get_contents\s*\(\s*['\"]php://input|"
    r"\$request->(json|all|input)\s*\(|json\.NewDecoder\s*\(\s*r\.Body\s*\)|ReadFromJsonAsync|\[FromBody\]|@RequestBody\s+(?!byte\s*\[)[A-Za-z_]"
)
MANUAL_HMAC_RE = re.compile(r"createHmac\s*\(\s*['\"]sha256|hmac\.new\s*\(|hash_hmac\s*\(\s*['\"]sha256|HMACSHA256|hmac\.New\s*\(\s*sha256\.New|Mac\.getInstance\s*\(\s*\"HmacSHA256")
VERDICT_RE = re.compile(r"identifications\.get(Async)?\s*\(|getIdentification\s*\(|identifications\(\)\.get(Async)?\s*\(|Identifications\.Get(Async)?\s*\(|->identifications->get\s*\(")
REPLAY_RE = re.compile(r"isReplay|is_replay|IsReplay|replayCheck|claimRequestId|claim_request_id|claimRequestID|ClaimAsync|markRequestIdUsed|used_request_ids|usedRequestIds|UsedRequestIds", re.I)
FRESHNESS_RE = re.compile(r"evaluateIdentification|evaluate_identification|EvaluateIdentification|Risk::evaluate|Risk\.evaluate|Risk\.Evaluate|RiskPolicy|\bdecide\s*\(|observed_at|ObservedAt|getObservedAt|maxAge|max_age|MaxAge")
# The SDK policy helper itself: when another file of the project calls it, a file that only wraps
# the verdict read (for example a readIdentification helper) is not flagged for SL06 or SL07.
POLICY_RE = re.compile(r"evaluateIdentification|evaluate_identification|EvaluateIdentification|Risk::evaluate|Risk\.evaluate|Risk\.Evaluate")
# A missing score read as a trusted number (0-29), or compared as if it were present.
MISSING_AS_TRUSTED = r"(<=|>=|<|>|\?\?\s*[12]?\d\b)"
CLEAN_RES = [
    re.compile(r"risk_?[sS]core\s*(\?\?|\|\|)\s*0\b"),
    re.compile(r"\?\.\s*(risk_score|riskScore|RiskScore)\s*" + MISSING_AS_TRUSTED),
    re.compile(r"\?->\s*risk_score\s*" + MISSING_AS_TRUSTED),
    re.compile(r"->risk_score\s*\?\?\s*0\b"),
    re.compile(r"RiskScore\s*\?\?\s*0\b"),
    re.compile(r"getattr\([^)]*['\"]risk_score['\"][^)]*,\s*0\s*\)"),
    re.compile(r"\.get\(\s*['\"](risk_score|score)['\"]\s*,\s*0\s*\)"),
    re.compile(r"getRiskScore\)\s*\.orElse\(\s*0\s*\)"),
    re.compile(r"if\s*\(\s*!\s*identification\s*\)\s*\{?\s*return\s+(next\s*\(|true\b|allow)"),
    re.compile(r"if\s+(not\s+identification|identification\s+is\s+None)\s*:\s*return\s+True\b"),
    re.compile(r"if\s+ident\s*==\s*nil\s*\{\s*return\s+true\b"),
]
CALL_CONTEXT_RE = re.compile(r"\b(identify|useIdentify|injectIdentify|check|checkAuthenticatedUser|forceCheckAuthenticatedUser|identifyOnInteraction)\s*\(|checkOnLoad")
PII_RE = re.compile(r"\b(e-?mail|phone|msisdn|username|user_name)\b", re.I)
RAWID_RE = re.compile(r"userId\s*:\s*(String\s*\(\s*)?(user|session|account|currentUser|me|profile|auth)\w*(\?\.|\.)(user\.)?(id|userId|uid|_id|pk)\b")
USER_ID_LINE_RE = re.compile(r"\buserId\b|checkAuthenticatedUser\s*\(")
HID_WORD_RE = re.compile(r"hid|hash|hmac", re.I)
IDENTIFY_CALL_RE = re.compile(r"\bidentify\s*\(|\bcheck\s*\(\s*[{)]")
ROUTE_MARKER_RE = re.compile(r"router\.events\.on\s*\(|routeChangeComplete|router\.(afterEach|beforeEach)\s*\(|afterNavigate\s*\(|onNavigate\s*\(|NavigationEnd")
EFFECT_RE = re.compile(r"\b(useEffect|useLayoutEffect|\$effect|watch|watchEffect)\s*\(")
LAYOUT_FILES = {"layout.tsx", "layout.jsx", "layout.js", "_app.tsx", "_app.jsx", "_app.js", "App.vue", "app.vue",
                "default.vue", "+layout.svelte", "App.svelte", "app.component.ts", "root.tsx", "App.tsx", "App.jsx"}
AGENT_FILES = {"snippet.js", "shield-loader.js", "shield-bootstrap.js"}
STATIC_AGENT_IMPORT_RE = re.compile(r"^\s*import\s+[^;(]*?\bfrom\s+['\"]https://(dev\.)?cdn\.shieldlabs\.ai/")
SELF_HOSTED_TAG_RE = re.compile(r"<script[^>]*\bsrc=['\"](?!https://(dev\.)?cdn\.shieldlabs\.ai)[^'\"]*(snippet|shield-loader)\.js", re.I)
PROXY_RE = re.compile(r"(destination|target|upstream|proxy_pass)\s*[:=]?\s*['\"]?https://(dev\.)?cdn\.shieldlabs\.ai", re.I)
SCRIPT_URL_RE = re.compile(r"scriptUrl\s*[:=]\s*['\"](?!https://(dev\.)?cdn\.shieldlabs\.ai)")
DEDUPE_RE = re.compile(r"event_id|eventId|EventId|enqueueOnce|enqueue_once|EnqueueOnce|request_id|RequestId|RequestID|getRequestId|requestId")
STORAGE_CLEAR_RE = re.compile(r"localStorage\.clear\s*\(\s*\)")
STORED_REQUEST_ID_RE = re.compile(r"(localStorage|sessionStorage)\.setItem\s*\([^)]*request_?[iI]d", re.I)
MANAGEMENT_RE = re.compile(r"\bgetProfile(Async)?\s*\(|\bget_profile\s*\(|\bGetProfile(Async)?\s*\(")
HANDLER_RE = re.compile(r"app\.(get|post|put|use)\s*\(|router\.(get|post)\s*\(|@(app|router)\.(get|post)|def \w+\(request|http\.ResponseWriter|@(Get|Post|Request)Mapping|Map(Get|Post)\s*\(|export\s+(async\s+)?function\s+(GET|POST)|defineEventHandler")
ENV_KEY_RE = re.compile(r"^\s*(export\s+)?(SHIELDLABS_API_KEY|SHIELDLABS_SECRET_KEY|SHIELDLABS_WEBHOOK_SECRET|USER_HID_SECRET)\s*=\s*['\"]?([^'\"\s#]+)", re.M)
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec|e2e|testdata|fixtures)(/|$)|[._](test|spec)\.")
PLACEHOLDER_RE = re.compile(r"your|example|placeholder|changeme|xxx|test0000|<|\.\.\.", re.I)


@dataclass
class Finding:
    check: str
    severity: str
    title: str
    file: str
    line: int
    excerpt: str
    fix: str


def has_secret(line: str) -> bool:
    """True when the line holds a key-shaped value that is not a documented placeholder."""
    return any(match.group(0) not in KNOWN_FAKE_SECRETS for regex in SECRET_RES for match in regex.finditer(line))


def mask(text: str) -> str:
    text = SECRET_RES[0].sub("sec_********-********-********", text)
    text = SECRET_RES[1].sub("whsec_********", text)
    text = re.sub(r"((?:SHIELDLABS_[A-Z_]+|USER_HID_SECRET)\s*=\s*)\S+", r"\1****", text)
    return text.strip()[:160]


class Scanner:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.findings: List[Finding] = []
        self.files_scanned = 0
        self.integrated = False
        self.replay_elsewhere = False
        self.policy_elsewhere = False

    def add(self, check: str, path: Path, line: int, text: str) -> None:
        severity, title, fix = CHECKS[check]
        entry = Finding(check, severity, title, self.rel(path), line, mask(text), fix)
        if not any(f.check == entry.check and f.file == entry.file and f.line == entry.line for f in self.findings):
            self.findings.append(entry)

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def files(self) -> Iterable[Path]:
        stack = [self.root]
        while stack:
            folder = stack.pop()
            try:
                entries = sorted(folder.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.is_dir():
                    if entry.name not in SKIP_DIRS and not (entry.name == "skills" and entry.parent.name in {".agents", ".codex", ".claude"}):
                        stack.append(entry)
                elif entry.is_file() and self.wanted(entry):
                    yield entry

    @staticmethod
    def wanted(path: Path) -> bool:
        if path.name.startswith(".env"):
            return True
        if path.name.endswith(".min.js"):
            return False
        return path.suffix in CODE_EXT or path.suffix in CONFIG_EXT

    def run(self) -> None:
        texts: Dict[Path, str] = {}
        for path in self.files():
            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
                texts[path] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        self.files_scanned = len(texts)
        self.integrated = any(INTEGRATION_RE.search(text) for text in texts.values())
        project_code = [text for path, text in texts.items()
                        if path.suffix in CODE_EXT and not TEST_PATH_RE.search(self.rel(path))]
        self.replay_elsewhere = any(REPLAY_RE.search(text) for text in project_code)
        self.policy_elsewhere = any(POLICY_RE.search(text) for text in project_code)
        for path, text in texts.items():
            lines = text.splitlines()
            if path.name.startswith(".env"):
                self.check_env_file(path, text, lines)
                continue
            self.check_secrets(path, lines)
            if path.suffix in CONFIG_EXT:
                self.check_config(path, text, lines)
                continue
            self.check_code(path, text, lines)

    # Individual checks -------------------------------------------------------------------------

    def check_secrets(self, path: Path, lines: List[str]) -> None:
        is_test = bool(TEST_PATH_RE.search(self.rel(path)))  # test fixtures use key-shaped fakes
        for number, line in enumerate(lines, 1):
            if not is_test and has_secret(line):
                self.add("SL01", path, number, line)
            if PUBLIC_PREFIX_RE.search(line):
                self.add("SL02", path, number, line)

    def check_env_file(self, path: Path, text: str, lines: List[str]) -> None:
        for number, line in enumerate(lines, 1):
            if PUBLIC_PREFIX_RE.search(line):
                self.add("SL02", path, number, line)
        if path.name.endswith((".example", ".sample", ".template", ".dist")):
            for number, line in enumerate(lines, 1):
                if has_secret(line):
                    self.add("SL01", path, number, line)
            return
        real = [m for m in ENV_KEY_RE.finditer(text) if not PLACEHOLDER_RE.search(m.group(3))]
        if not real:
            return
        state = git_state(self.root, path)
        if state == "tracked" or (state == "untracked-not-ignored"):
            line = text[: real[0].start()].count("\n") + 1
            self.add("SL15", path, line, lines[line - 1] if line <= len(lines) else "")
        elif state is None and not ignored_by_gitignore(self.root, path):
            line = text[: real[0].start()].count("\n") + 1
            self.add("SL15", path, line, lines[line - 1] if line <= len(lines) else "")

    def check_config(self, path: Path, text: str, lines: List[str]) -> None:
        self.check_csp(path, text, lines)
        for number, line in enumerate(lines, 1):
            if PROXY_RE.search(line):
                self.add("SL12", path, number, line)

    def check_code(self, path: Path, text: str, lines: List[str]) -> None:
        mentions = bool(INTEGRATION_RE.search(text)) or "shieldlabs" in text.lower()
        is_test = bool(TEST_PATH_RE.search(self.rel(path)))
        if self.is_client_file(path, text):
            for number, line in enumerate(lines, 1):
                if SERVER_ONLY_RE.search(line):
                    self.add("SL03", path, number, line)
        if path.name in AGENT_FILES and "shieldlabs" in text.lower():
            self.add("SL12", path, 1, f"{path.name} is in the repository")
        for number, line in enumerate(lines, 1):
            if STATIC_AGENT_IMPORT_RE.search(line) or (SELF_HOSTED_TAG_RE.search(line) and re.search(r"publicKey|shield", line, re.I)):
                self.add("SL12", path, number, line)
            elif PROXY_RE.search(line) or (SCRIPT_URL_RE.search(line) and mentions and not is_test):
                self.add("SL12", path, number, line)
            if STORAGE_CLEAR_RE.search(line) and self.integrated:
                self.add("SL16", path, number, line)
            if STORED_REQUEST_ID_RE.search(line):
                self.add("SL18", path, number, line)
        self.check_csp(path, text, lines)
        if not mentions and not WEBHOOK_HEADER_RE.search(text):
            return
        self.check_webhook(path, text, lines)
        self.check_verdict(path, text, lines)
        self.check_clean(path, lines)
        self.check_user_hid(path, lines)
        self.check_render(path, lines)
        if MANAGEMENT_RE.search(text) and HANDLER_RE.search(text):
            number = next(i for i, line in enumerate(lines, 1) if MANAGEMENT_RE.search(line))
            self.add("SL17", path, number, lines[number - 1])

    @staticmethod
    def is_client_file(path: Path, text: str) -> bool:
        parts = {p.lower() for p in path.parts}
        if USE_CLIENT_RE.match(text):
            return True
        if path.suffix == ".vue" and "server" not in parts:
            return True
        if path.suffix == ".svelte" or path.name.endswith(".component.ts"):
            return True
        return bool(parts & {"public", "static", "assets"}) and path.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs"}

    def check_webhook(self, path: Path, text: str, lines: List[str]) -> None:
        if not (WEBHOOK_HEADER_RE.search(text) or (WEBHOOK_CALL_RE.search(text) and "shieldlabs" in text.lower())):
            return
        calls = [i for i, line in enumerate(lines) if WEBHOOK_CALL_RE.search(line)]
        header_lines = [i for i, line in enumerate(lines) if WEBHOOK_HEADER_RE.search(line)]
        anchors = calls or header_lines
        for anchor in anchors:
            for i in range(max(0, anchor - 25), anchor):
                if PARSE_FIRST_RE.search(lines[i]):
                    self.add("SL04", path, i + 1, lines[i])
            window = "\n".join(lines[max(0, anchor - 40): anchor + 40])
            if not DEDUPE_RE.search(window) and "createWebhookHandler" not in lines[anchor]:
                self.add("SL13", path, anchor + 1, lines[anchor])
        if "express.json(" in text and "express.raw(" not in text:
            number = next(i for i, line in enumerate(lines, 1) if "express.json(" in line)
            self.add("SL04", path, number, lines[number - 1])
        # Tests sign deliveries themselves to exercise the receiver, like the key-shaped fakes of SL01.
        is_test = bool(TEST_PATH_RE.search(self.rel(path)))
        if header_lines and not calls and not is_test and MANUAL_HMAC_RE.search(text):
            number = next(i for i, line in enumerate(lines, 1) if MANUAL_HMAC_RE.search(line))
            self.add("SL05", path, number, lines[number - 1])

    def check_verdict(self, path: Path, text: str, lines: List[str]) -> None:
        reads = [i for i, line in enumerate(lines, 1) if VERDICT_RE.search(line)]
        if not reads:
            return
        # A helper file that only reads the verdict is fine when the guards run elsewhere in the
        # project; the audit still checks every handler by hand (references/audit.md).
        if not REPLAY_RE.search(text) and not self.replay_elsewhere:
            self.add("SL06", path, reads[0], lines[reads[0] - 1])
        if not FRESHNESS_RE.search(text) and not self.policy_elsewhere:
            self.add("SL07", path, reads[0], lines[reads[0] - 1])

    def check_clean(self, path: Path, lines: List[str]) -> None:
        for number, line in enumerate(lines, 1):
            if any(r.search(line) for r in CLEAN_RES):
                self.add("SL08", path, number, line)

    def check_user_hid(self, path: Path, lines: List[str]) -> None:
        for index, line in enumerate(lines):
            if not USER_ID_LINE_RE.search(line) or HID_WORD_RE.search(line):
                continue
            context = "\n".join(lines[max(0, index - 3): index + 2])
            if not CALL_CONTEXT_RE.search(context):
                continue
            if PII_RE.search(line):
                self.add("SL09", path, index + 1, line)
            elif RAWID_RE.search(line):
                self.add("SL10", path, index + 1, line)

    def check_render(self, path: Path, lines: List[str]) -> None:
        for index, line in enumerate(lines):
            if EFFECT_RE.search(line):
                for j in range(index, min(len(lines), index + 10)):
                    if IDENTIFY_CALL_RE.search(lines[j]) and "runOnMount" not in lines[j]:
                        self.add("SL11", path, j + 1, lines[j])
                        break
        if any(IDENTIFY_CALL_RE.search(line) for line in lines):
            for number, line in enumerate(lines, 1):
                if ROUTE_MARKER_RE.search(line):
                    self.add("SL11", path, number, line)
                    break
        if path.name in LAYOUT_FILES:
            for number, line in enumerate(lines, 1):
                if re.search(r"runOnMount\s*[:=]\s*\{?\s*true", line):
                    self.add("SL11", path, number, line)

    def check_csp(self, path: Path, text: str, lines: List[str]) -> None:
        if not self.integrated or ("script-src" not in text and "connect-src" not in text):
            return
        for number, line in enumerate(lines, 1):
            if "script-src" in line and "cdn.shieldlabs.ai" not in text:
                self.add("SL14", path, number, line)
                break
        for number, line in enumerate(lines, 1):
            if "connect-src" in line and "rest.shieldlabs.ai" not in text:
                self.add("SL14", path, number, line)
                break


def git_state(root: Path, path: Path) -> Optional[str]:
    """'tracked', 'ignored', 'untracked-not-ignored', or None when git is not available."""
    try:
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", str(path)],
                                 capture_output=True, text=True, timeout=10)
        if tracked.returncode == 0:
            return "tracked"
        inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True, timeout=10)
        if inside.returncode != 0:
            return None
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", str(path)],
                                 capture_output=True, text=True, timeout=10)
        return "ignored" if ignored.returncode == 0 else "untracked-not-ignored"
    except (OSError, subprocess.SubprocessError):
        return None


def ignored_by_gitignore(root: Path, path: Path) -> bool:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return False
    patterns = [line.strip() for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip() and not line.strip().startswith("#")]
    name = path.name
    ignored = any(fnmatch.fnmatch(name, p.lstrip("/")) for p in patterns if not p.startswith("!"))
    return ignored and not any(fnmatch.fnmatch(name, p[1:].lstrip("/")) for p in patterns if p.startswith("!"))


def scan(root: Path) -> dict:
    scanner = Scanner(root)
    scanner.run()
    findings = sorted(scanner.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.check, f.file, f.line))
    return {"root": str(root.resolve()), "files_scanned": scanner.files_scanned,
            "shieldlabs_integration_found": scanner.integrated, "findings": [asdict(f) for f in findings]}


def render(result: dict) -> str:
    lines = [f"ShieldLabs audit scan of {result['root']}",
             "Heuristic: confirm every finding in the code before reporting it.", ""]
    if not result["shieldlabs_integration_found"]:
        lines.append("No ShieldLabs integration found (no ShieldLabs packages, imports or agent URLs). Use the setup workflow.")
        lines.append("")
    for severity in ("high", "medium", "low"):
        group = [f for f in result["findings"] if f["severity"] == severity]
        if not group:
            continue
        lines.append(severity.upper())
        for finding in group:
            lines.append(f"  [{finding['check']}] {finding['title']}")
            lines.append(f"    {finding['file']}:{finding['line']}: {finding['excerpt']}")
            lines.append(f"    Fix: {finding['fix']}")
        lines.append("")
    counts = {s: sum(1 for f in result["findings"] if f["severity"] == s) for s in ("high", "medium", "low")}
    lines.append(f"Summary: {counts['high']} high, {counts['medium']} medium, {counts['low']} low in {result['files_scanned']} files.")
    lines.append("Also check by hand what a scan cannot see: see references/audit.md of the shieldlabs-setup skill.")
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Scan a project for common ShieldLabs integration problems.")
    parser.add_argument("project", nargs="?", default=".", help="project directory (default: current directory)")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument("--strict", action="store_true", help="exit with status 1 when a high-severity finding exists")
    args = parser.parse_args(argv[1:])
    root = Path(args.project)
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2
    result = scan(root)
    print(json.dumps(result, indent=2) if args.json else render(result))
    if args.strict and any(f["severity"] == "high" for f in result["findings"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
