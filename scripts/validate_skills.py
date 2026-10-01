#!/usr/bin/env python3
"""Validate the skills, manifests and Markdown links of this repository.

Checks, with the Python standard library only:

- every skills/<name>/SKILL.md starts with YAML frontmatter whose `name` equals the folder name
  and whose `description` has at most 1024 characters and says when to use the skill;
- every SKILL.md has at most 500 lines, and reference files longer than 300 lines have a
  "Contents" section;
- every file in a skill's references/ and scripts/ folders is linked from that skill;
- every relative link and anchor in the Markdown files (.md, .mdc) resolves;
- every Python code block in those files compiles with the grammar of Python 3.9, the oldest
  version the Python SDK supports (code that returns belongs inside a named function);
- the JSON manifests parse and agree on the plugin name and version (Grok, Claude Code, Cursor
  and Codex), the Codex marketplace entry
  asks for no authentication on install, and CHANGELOG.md has an entry for that version;
- every slash command and every rule file has frontmatter with a description.

When PyYAML is installed, the frontmatter is also parsed with it and must give the same values.

Usage: python3 scripts/validate_skills.py [repository root]
Exit status: 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import ast
import json
import re
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote

try:  # Optional cross-check with a full YAML parser.
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - depends on the environment
    yaml = None

PLUGIN_NAME = "shieldlabs"
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_SKILL_LINES = 500
TOC_THRESHOLD = 300
ALLOWED_SKILL_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TRIGGER_RE = re.compile(r"\buse (?:it |this skill |them )?(?:when|whenever)\b", re.IGNORECASE)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist"}
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp://")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
FENCE_INFO_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*([^\s`]*)")
PYTHON_INFO = {"python", "python3", "py"}
PYTHON_FLOOR = (3, 9)
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR_RE = re.compile(r"<a\s+(?:[^>]*?\s)?(?:id|name)=\"([^\"]+)\"", re.IGNORECASE)
INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
LINK_RE = re.compile(r"!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
FRONTMATTER_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", re.DOTALL)
DATE_SUFFIX = r"\] - \d{4}-\d{2}-\d{2}\s*$"


class Report:
    """Collects error messages."""

    def __init__(self) -> None:
        self.errors: List[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)


# Frontmatter ----------------------------------------------------------------------------------


def split_frontmatter(text: str) -> Tuple[Optional[str], str]:
    """Returns (frontmatter block, body), or (None, text) when there is no frontmatter."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    return match.group(1), text[match.end():]


def parse_scalar(value: str, report: Report, where: str) -> object:
    """Parses the subset of YAML scalars used in frontmatter (plain, quoted, booleans)."""
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except ValueError:
            report.error(f"{where}: invalid double-quoted string")
            return value
        if not isinstance(parsed, str):
            report.error(f"{where}: expected a string")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            report.error(f"{where}: unterminated single-quoted string")
            return value
        return value[1:-1].replace("''", "'")
    if value in ("true", "false"):
        return value == "true"
    if value[0] in "&*!|>%@`[{," or value.startswith(("- ", "? ", ": ")):
        report.error(f"{where}: quote a value that starts with {value[0]!r}")
    if ": " in value or " #" in value or value.endswith(":"):
        report.error(f"{where}: quote a value that contains ': ' or ' #' (YAML would misread it)")
    return value


def parse_frontmatter(block: str, report: Report, where: str) -> Dict[str, object]:
    """Parses flat `key: value` frontmatter with optional one-level nested mappings."""
    data: Dict[str, object] = {}
    nested: Optional[Dict[str, object]] = None
    for offset, line in enumerate(block.splitlines(), start=2):
        location = f"{where}:{offset}"
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            if nested is None:
                report.error(f"{location}: unexpected indented line in frontmatter")
                continue
            key, sep, value = line.strip().partition(":")
            if not sep or not key.strip():
                report.error(f"{location}: expected 'key: value'")
                continue
            nested[key.strip()] = parse_scalar(value.strip(), report, location) if value.strip() else ""
            continue
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not key:
            report.error(f"{location}: expected 'key: value'")
            continue
        if key in data:
            report.error(f"{location}: duplicate key '{key}'")
        value = value.strip()
        if value:
            data[key] = parse_scalar(value, report, location)
            nested = None
        else:
            nested = {}
            data[key] = nested
    return data


def load_frontmatter(path: Path, report: Report, root: Path) -> Optional[Dict[str, object]]:
    where = rel(path, root)
    text = path.read_text(encoding="utf-8")
    block, _ = split_frontmatter(text)
    if block is None:
        report.error(f"{where}: missing YAML frontmatter (the file must start with '---')")
        return None
    data = parse_frontmatter(block, report, where)
    if yaml is not None:
        try:
            loaded = yaml.safe_load(block)
        except yaml.YAMLError as exc:  # pragma: no cover - reported, not expected
            report.error(f"{where}: frontmatter is not valid YAML: {exc}")
            return data
        if not isinstance(loaded, dict):
            report.error(f"{where}: frontmatter must be a YAML mapping")
        else:
            for key, value in data.items():
                if not isinstance(value, dict) and loaded.get(key) != value:
                    report.error(f"{where}: a YAML parser reads '{key}' differently; quote the value")
    return data


# Markdown links and anchors -------------------------------------------------------------------


def markdown_lines(text: str) -> List[Tuple[int, str]]:
    """Returns (line number, line) pairs outside fenced code blocks, without inline code spans."""
    result: List[Tuple[int, str]] = []
    fence: Optional[str] = None
    for number, line in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
                continue
            if marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
                continue
        if fence is not None:
            continue
        result.append((number, INLINE_CODE_RE.sub("", line)))
    return result


def slugify(heading: str) -> str:
    """GitHub-style anchor for a heading."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def headings_of(body: str) -> List[str]:
    """Heading texts outside fenced code blocks, with inline code kept."""
    headings: List[str] = []
    fence: Optional[str] = None
    for line in body.splitlines():
        match = FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            headings.append(heading.group(2))
    return headings


def anchors_of(path: Path, cache: Dict[Path, set]) -> set:
    if path in cache:
        return cache[path]
    anchors: set = set()
    counts: Dict[str, int] = {}
    _, body = split_frontmatter(path.read_text(encoding="utf-8"))
    for heading in headings_of(body):
        slug = slugify(heading)
        seen = counts.get(slug, 0)
        anchors.add(slug if seen == 0 else f"{slug}-{seen}")
        counts[slug] = seen + 1
    for _, line in markdown_lines(body):
        anchors.update(HTML_ANCHOR_RE.findall(line))
    cache[path] = anchors
    return anchors


def links_of(path: Path) -> List[Tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    links: List[Tuple[int, str]] = []
    for number, line in markdown_lines(text):
        for match in LINK_RE.finditer(line):
            links.append((number, match.group(1)))
    return links


def check_links(files: List[Path], root: Path, report: Report) -> int:
    """Checks relative links and anchors. Returns the number of links checked."""
    cache: Dict[Path, set] = {}
    checked = 0
    for path in files:
        for number, target in links_of(path):
            if target.startswith(EXTERNAL_PREFIXES):
                continue
            checked += 1
            where = f"{rel(path, root)}:{number}"
            file_part, _, fragment = target.partition("#")
            if not file_part:
                if fragment and fragment not in anchors_of(path, cache):
                    report.error(f"{where}: no heading for anchor '#{fragment}'")
                continue
            resolved = (path.parent / unquote(file_part)).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                report.error(f"{where}: link leaves the repository: {target}")
                continue
            if not resolved.exists():
                report.error(f"{where}: broken link: {target}")
                continue
            if fragment and resolved.is_file() and resolved.suffix in (".md", ".mdc"):
                if fragment not in anchors_of(resolved, cache):
                    report.error(f"{where}: no heading for anchor '#{fragment}' in {file_part}")
    return checked


# Code samples ---------------------------------------------------------------------------------------


def fenced_blocks(text: str) -> List[Tuple[str, int, str]]:
    """(info string in lowercase, line number of the first code line, code) of each fenced block.

    The indentation of the opening fence (a block inside a list item) is removed from every line.
    """
    blocks: List[Tuple[str, int, str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = FENCE_INFO_RE.match(lines[index])
        if not match:
            index += 1
            continue
        indent, marker, info = len(match.group(1)), match.group(2), match.group(3).lower()
        end = index + 1
        while end < len(lines):
            closing = FENCE_RE.match(lines[end])
            if closing and closing.group(1)[0] == marker[0] and len(closing.group(1)) >= len(marker):
                break
            end += 1
        code = []
        for line in lines[index + 1:end]:
            spaces = len(line) - len(line.lstrip(" "))
            code.append(line[min(indent, spaces):])
        blocks.append((info, index + 2, "\n".join(code) + "\n"))
        index = end + 1
    return blocks


def check_python_blocks(files: List[Path], root: Path, report: Report) -> int:
    """Compiles every Python code block. Returns the number of blocks checked."""
    checked = 0
    for path in files:
        for info, first_line, code in fenced_blocks(path.read_text(encoding="utf-8")):
            if info not in PYTHON_INFO:
                continue
            checked += 1
            try:
                with warnings.catch_warnings():  # warnings differ between Python versions
                    warnings.simplefilter("ignore")
                    compile(ast.parse(code, feature_version=PYTHON_FLOOR), rel(path, root), "exec")
            except SyntaxError as exc:
                line = first_line + (exc.lineno or 1) - 1
                report.error(f"{rel(path, root)}:{line}: Python code does not compile: {exc.msg}")
    return checked


# Skills -------------------------------------------------------------------------------------------


def linked_files(path: Path) -> set:
    """Resolved local files linked from a Markdown file."""
    result = set()
    for _, target in links_of(path):
        if target.startswith(EXTERNAL_PREFIXES) or target.startswith("#"):
            continue
        file_part = target.partition("#")[0]
        result.add((path.parent / unquote(file_part)).resolve())
    return result


def check_skill(skill_dir: Path, root: Path, report: Report) -> None:
    name = skill_dir.name
    where = rel(skill_dir, root)
    if not NAME_RE.match(name) or len(name) > MAX_NAME:
        report.error(f"{where}: folder name must be kebab-case with at most {MAX_NAME} characters")
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        report.error(f"{where}: missing SKILL.md")
        return
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if len(lines) > MAX_SKILL_LINES:
        report.error(
            f"{rel(skill_md, root)}: {len(lines)} lines; keep SKILL.md at or under "
            f"{MAX_SKILL_LINES} and move details to references/"
        )
    data = load_frontmatter(skill_md, report, root)
    if data is not None:
        check_skill_frontmatter(data, name, rel(skill_md, root), report)

    from_skill = linked_files(skill_md)
    reachable = set(from_skill)
    references_dir = skill_dir / "references"
    references = sorted(references_dir.glob("*.md")) if references_dir.is_dir() else []
    for reference in references:
        reachable |= linked_files(reference)
    for reference in references:
        if reference.resolve() not in from_skill:
            report.error(f"{rel(reference, root)}: not linked from {rel(skill_md, root)}")
        ref_lines = reference.read_text(encoding="utf-8").splitlines()
        has_contents = any(re.match(r"^##\s+Contents\s*$", line) for line in ref_lines)
        if len(ref_lines) > TOC_THRESHOLD and not has_contents:
            report.error(f"{rel(reference, root)}: {len(ref_lines)} lines; add a '## Contents' section")
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        scripts = sorted(p for p in scripts_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        for script in scripts:
            if script.resolve() not in reachable:
                report.error(f"{rel(script, root)}: not linked from the skill's SKILL.md or references")
    for entry in sorted(skill_dir.iterdir()):
        if entry.name not in {"SKILL.md", "references", "scripts", "assets"}:
            report.error(f"{rel(entry, root)}: unexpected entry in a skill folder")


def check_skill_frontmatter(data: Dict[str, object], folder: str, where: str, report: Report) -> None:
    unexpected = sorted(set(data) - ALLOWED_SKILL_KEYS)
    if unexpected:
        report.error(f"{where}: unexpected frontmatter keys {unexpected}; allowed: {sorted(ALLOWED_SKILL_KEYS)}")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        report.error(f"{where}: frontmatter needs a 'name'")
    elif name != folder:
        report.error(f"{where}: name '{name}' must equal the folder name '{folder}'")
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        report.error(f"{where}: frontmatter needs a 'description'")
        return
    if len(description) > MAX_DESCRIPTION:
        report.error(f"{where}: description has {len(description)} characters (at most {MAX_DESCRIPTION})")
    if "<" in description or ">" in description:
        report.error(f"{where}: description must not contain angle brackets")
    if not TRIGGER_RE.search(description):
        report.error(f"{where}: description must say when to use the skill ('Use when ...')")
    if re.match(r"^(I|You|We)\b", description):
        report.error(f"{where}: write the description in the third person")


# Manifests ----------------------------------------------------------------------------------------


def load_json(path: Path, root: Path, report: Report) -> Optional[dict]:
    if not path.is_file():
        report.error(f"{rel(path, root)}: missing")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        report.error(f"{rel(path, root)}: invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        report.error(f"{rel(path, root)}: expected a JSON object")
        return None
    return data


def plugin_entries(data: Optional[dict], where: str, report: Report) -> List[dict]:
    if data is None:
        return []
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        report.error(f"{where}: 'plugins' must be a non-empty list")
        return []
    entries = [p for p in plugins if isinstance(p, dict) and p.get("name") == PLUGIN_NAME]
    if not entries:
        report.error(f"{where}: no plugin named '{PLUGIN_NAME}'")
    return entries


def check_manifests(root: Path, report: Report) -> Optional[str]:
    """Checks the JSON manifests. Returns the plugin version when all manifests agree on it."""
    grok = load_json(root / ".grok-plugin/plugin.json", root, report)
    grok_market = load_json(root / ".grok-plugin/marketplace.json", root, report)
    claude = load_json(root / ".claude-plugin/plugin.json", root, report)
    claude_market = load_json(root / ".claude-plugin/marketplace.json", root, report)
    cursor = load_json(root / ".cursor-plugin/plugin.json", root, report)
    cursor_market = load_json(root / ".cursor-plugin/marketplace.json", root, report)
    codex = load_json(root / ".codex-plugin/plugin.json", root, report)
    agents_market = load_json(root / ".agents/plugins/marketplace.json", root, report)
    mcp = load_json(root / ".mcp.json", root, report)

    versions: Dict[str, object] = {}
    for label, manifest in (
        (".grok-plugin/plugin.json", grok),
        (".claude-plugin/plugin.json", claude),
        (".cursor-plugin/plugin.json", cursor),
        (".codex-plugin/plugin.json", codex),
    ):
        if manifest is None:
            continue
        if manifest.get("name") != PLUGIN_NAME:
            report.error(f"{label}: name must be '{PLUGIN_NAME}'")
        versions[label] = manifest.get("version")

    for label, market in (
        (".grok-plugin/marketplace.json", grok_market),
        (".claude-plugin/marketplace.json", claude_market),
        (".cursor-plugin/marketplace.json", cursor_market),
        (".agents/plugins/marketplace.json", agents_market),
    ):
        if market is None:
            continue
        if market.get("name") != PLUGIN_NAME:
            report.error(f"{label}: marketplace name must be '{PLUGIN_NAME}'")
        for entry in plugin_entries(market, label, report):
            if "version" in entry:
                versions[f"{label} plugins[{PLUGIN_NAME}]"] = entry["version"]
    if grok_market is not None:
        metadata = grok_market.get("metadata")
        if isinstance(metadata, dict) and "version" in metadata:
            versions[".grok-plugin/marketplace.json metadata"] = metadata["version"]
        for entry in plugin_entries(grok_market, ".grok-plugin/marketplace.json", Report()):
            if entry.get("source") != "./":
                report.error(".grok-plugin/marketplace.json: the plugin source must be './'")
    if claude_market is not None:
        metadata = claude_market.get("metadata")
        if isinstance(metadata, dict) and "version" in metadata:
            versions[".claude-plugin/marketplace.json metadata"] = metadata["version"]
        for entry in plugin_entries(claude_market, ".claude-plugin/marketplace.json", Report()):
            if entry.get("source") != "./":
                report.error(".claude-plugin/marketplace.json: the plugin source must be './'")

    distinct = {str(value) for value in versions.values()}
    if len(distinct) > 1:
        detail = ", ".join(f"{label}={value}" for label, value in versions.items())
        report.error(f"manifests disagree on the version: {detail}")
    version = next(iter(distinct)) if len(distinct) == 1 else None
    if version is not None and not re.match(r"^\d+\.\d+\.\d+$", version):
        report.error(f"plugin version '{version}' is not MAJOR.MINOR.PATCH")

    for label, manifest in (
        (".grok-plugin/plugin.json", grok),
        (".claude-plugin/plugin.json", claude),
        (".codex-plugin/plugin.json", codex),
    ):
        if manifest is None:
            continue
        for key in ("mcpServers", "skills"):
            target = manifest.get(key)
            if isinstance(target, str) and not (root / target).exists():
                report.error(f"{label}: {key} points to a missing path: {target}")
    if codex is not None and not any(key in codex for key in ("apps", "mcpServers")):
        # Nothing in the Codex plugin signs in to anything, and Codex reads a missing value as ON_INSTALL.
        for entry in plugin_entries(agents_market, ".agents/plugins/marketplace.json", Report()):
            policy = entry.get("policy")
            if not isinstance(policy, dict) or policy.get("authentication") != "ON_USE":
                report.error(
                    ".agents/plugins/marketplace.json: the Codex plugin has no apps or MCP servers, "
                    "so policy.authentication must be 'ON_USE'"
                )
    if mcp is not None:
        servers = mcp.get("mcpServers")
        server = servers.get(PLUGIN_NAME) if isinstance(servers, dict) else None
        if not isinstance(server, dict):
            report.error(f".mcp.json: mcpServers must define '{PLUGIN_NAME}'")
        elif "@shieldlabs-ai/mcp" not in (server.get("args") or []):
            report.error(".mcp.json: the server must start @shieldlabs-ai/mcp")

    changelog = root / "CHANGELOG.md"
    if version is not None:
        entry = re.compile("^## \\[" + re.escape(version) + DATE_SUFFIX, re.MULTILINE)
        if not changelog.is_file():
            report.error("CHANGELOG.md: missing")
        elif not entry.search(changelog.read_text(encoding="utf-8")):
            report.error(f"CHANGELOG.md: no '## [{version}] - YYYY-MM-DD' entry")
    return version


def check_commands_and_rules(root: Path, report: Report) -> None:
    commands_dir = root / "commands"
    for path in sorted(commands_dir.glob("*.md")) if commands_dir.is_dir() else []:
        data = load_frontmatter(path, report, root)
        if data is not None and not (isinstance(data.get("description"), str) and data["description"].strip()):
            report.error(f"{rel(path, root)}: frontmatter needs a 'description'")
    rules_dir = root / "rules"
    for path in sorted(rules_dir.glob("*.mdc")) if rules_dir.is_dir() else []:
        data = load_frontmatter(path, report, root)
        if data is None:
            continue
        if not (isinstance(data.get("description"), str) and data["description"].strip()):
            report.error(f"{rel(path, root)}: frontmatter needs a 'description'")
        if not isinstance(data.get("alwaysApply"), bool):
            report.error(f"{rel(path, root)}: frontmatter needs 'alwaysApply: true' or 'alwaysApply: false'")


# Entry point ---------------------------------------------------------------------------------------


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def markdown_files(root: Path) -> List[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix in (".md", ".mdc"):
            files.append(path)
    return files


def validate(root: Path) -> Tuple[List[str], Dict[str, int]]:
    """Runs every check. Returns (errors, counts)."""
    report = Report()
    skills_dir = root / "skills"
    skills = sorted(p for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
    if not skills:
        report.error("skills/: no skills found")
    for skill in skills:
        check_skill(skill, root, report)
    check_manifests(root, report)
    check_commands_and_rules(root, report)
    files = markdown_files(root)
    links = check_links(files, root, report)
    samples = check_python_blocks(files, root, report)
    counts = {"skills": len(skills), "markdown files": len(files), "relative links": links, "Python samples": samples}
    return report.errors, counts


def main(argv: List[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    errors, counts = validate(root)
    for message in errors:
        print(f"error: {message}")
    summary = ", ".join(f"{value} {label}" for label, value in counts.items())
    if errors:
        print(f"\n{len(errors)} problem(s) found ({summary}).")
        return 1
    print(f"All checks passed ({summary}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
