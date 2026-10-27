"""Tests for scripts/validate_skills.py (standard library unittest)."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("validate_skills", ROOT / "scripts" / "validate_skills.py")
validate_skills = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["validate_skills"] = validate_skills
spec.loader.exec_module(validate_skills)


def copy_repository(target: Path) -> None:
    ignore = shutil.ignore_patterns(".git", "__pycache__", "dist", ".venv")
    for entry in ROOT.iterdir():
        if entry.name in {".git", "dist", ".venv"}:
            continue
        if entry.is_dir():
            shutil.copytree(entry, target / entry.name, ignore=ignore)
        else:
            shutil.copy2(entry, target / entry.name)


class ValidateRepositoryTest(unittest.TestCase):
    def test_repository_passes(self) -> None:
        errors, counts = validate_skills.validate(ROOT)
        self.assertEqual(errors, [])
        self.assertEqual(counts["skills"], 8)

    def test_slugify(self) -> None:
        self.assertEqual(validate_skills.slugify("Pick the package"), "pick-the-package")
        self.assertEqual(validate_skills.slugify("`identify()` on submit"), "identify-on-submit")
        self.assertEqual(validate_skills.slugify("Signup, login and logout"), "signup-login-and-logout")

    def test_repository_python_samples_are_checked(self) -> None:
        _, counts = validate_skills.validate(ROOT)
        self.assertGreater(counts["Python samples"], 0)

    def test_fenced_blocks(self) -> None:
        text = "Intro\n\n```python\nx = 1\n```\n\n- A step:\n\n  ```py\n  if x:\n      y = 2\n  ```\n\n~~~\nplain\n~~~\n"
        blocks = validate_skills.fenced_blocks(text)
        self.assertEqual([(info, line) for info, line, _ in blocks], [("python", 4), ("py", 10), ("", 15)])
        self.assertEqual(blocks[0][2], "x = 1\n")
        self.assertEqual(blocks[1][2], "if x:\n    y = 2\n")


class ValidateBrokenRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        copy_repository(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def errors(self) -> str:
        errors, _ = validate_skills.validate(self.root)
        return "\n".join(errors)

    def test_name_must_match_folder(self) -> None:
        skill = self.root / "skills" / "shieldlabs-browser" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8").replace("name: shieldlabs-browser", "name: browser", 1), encoding="utf-8")
        self.assertIn("must equal the folder name", self.errors())

    def test_description_needs_a_trigger_and_a_length_limit(self) -> None:
        skill = self.root / "skills" / "shieldlabs-server" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        start = text.index("description: ") + len("description: ")
        end = text.index("\n", start)
        skill.write_text(text[:start] + "Reads verdicts. " + "x" * 1100 + text[end:], encoding="utf-8")
        errors = self.errors()
        self.assertIn("description has", errors)
        self.assertIn("Use when", errors)

    def test_broken_links_and_anchors(self) -> None:
        skill = self.root / "skills" / "shieldlabs-webhooks" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n[missing](references/nope.md) [anchor](#no-such-heading)\n", encoding="utf-8")
        errors = self.errors()
        self.assertIn("broken link: references/nope.md", errors)
        self.assertIn("no heading for anchor '#no-such-heading'", errors)

    def test_orphan_reference_and_long_skill(self) -> None:
        folder = self.root / "skills" / "shieldlabs-investigate"
        (folder / "references" / "orphan.md").write_text("# Orphan\n", encoding="utf-8")
        skill = folder / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\n" * 500, encoding="utf-8")
        errors = self.errors()
        self.assertIn("orphan.md: not linked from", errors)
        self.assertIn("keep SKILL.md at or under 500", errors)

    def test_manifest_versions_must_agree(self) -> None:
        path = self.root / ".cursor-plugin" / "plugin.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = "9.9.9"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("manifests disagree on the version", self.errors())

    def test_codex_marketplace_asks_for_no_authentication_on_install(self) -> None:
        path = self.root / ".agents" / "plugins" / "marketplace.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["plugins"][0]["policy"]["authentication"] = "ON_INSTALL"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("policy.authentication must be 'ON_USE'", self.errors())
        del data["plugins"][0]["policy"]["authentication"]  # Codex reads a missing value as ON_INSTALL
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIn("policy.authentication must be 'ON_USE'", self.errors())

    def test_mcp_rejects_local_process_and_embedded_credentials(self) -> None:
        path = self.root / ".mcp.json"
        for server in (
            {"command": "npx", "args": ["-y", "@shieldlabs-ai/mcp"]},
            {"type": "http", "url": "http://mcp.shieldlabs.ai/mcp"},
            {"type": "http", "url": "https://mcp.shieldlabs.ai/mcp", "headers": {"Authorization": "Bearer placeholder"}},
        ):
            with self.subTest(server=server):
                path.write_text(json.dumps({"mcpServers": {"shieldlabs": server}}))
                self.assertIn("use the hosted HTTPS OAuth endpoint", self.errors())

    def test_frontmatter_that_yaml_would_misread(self) -> None:
        skill = self.root / "skills" / "shieldlabs-setup" / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        skill.write_text(text.replace("description: ", "description: Setup: ", 1), encoding="utf-8")
        self.assertIn("quote a value that contains ': '", self.errors())

    def test_python_samples_must_compile(self) -> None:
        reference = self.root / "skills" / "shieldlabs-account-abuse" / "references" / "python.md"
        text = reference.read_text(encoding="utf-8")
        sample = "\n```python\nif ato.suspicious:\n    return require_second_factor(account)\n```\n"
        reference.write_text(text + sample, encoding="utf-8")
        line = len(text.splitlines()) + 4  # the return statement
        self.assertIn(
            f"skills/shieldlabs-account-abuse/references/python.md:{line}: Python code does not compile: "
            "'return' outside function",
            self.errors(),
        )

    def test_python_samples_use_the_oldest_supported_grammar(self) -> None:
        reference = self.root / "skills" / "shieldlabs-server" / "references" / "python.md"
        text = reference.read_text(encoding="utf-8")
        sample = "\n```python\nmatch verdict.reason:\n    case None:\n        pass\n```\n"
        reference.write_text(text + sample, encoding="utf-8")
        found = re.search(r"skills/shieldlabs-server/references/python\.md:(\d+): Python code does not compile", self.errors())
        self.assertIsNotNone(found)
        first = len(text.splitlines()) + 3  # the match statement; Python versions report one of its lines
        self.assertIn(int(found.group(1)), range(first, first + 3))


if __name__ == "__main__":
    unittest.main()
