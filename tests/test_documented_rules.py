"""SDK rules that several skill files state, checked in every file that states them.

SKILL.md and the reference files describe the same SDK behaviour in their own words. These tests
pin the facts that must not drift between them: each test finds the paragraphs, list items or
table rows that state a rule and checks the parts of the rule that are easy to lose.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
SERVER = SKILLS / "shieldlabs-server"
SERVER_REFERENCES = [
    SERVER / "references" / f"{name}.md" for name in ("node", "python", "go", "php", "java", "dotnet")
]
OTHER_LANGUAGES = SERVER / "references" / "other-languages.md"
BROWSER = SKILLS / "shieldlabs-browser"
NEXTJS = BROWSER / "references" / "nextjs.md"

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}#{1,6}\s")
ITEM_START_RE = re.compile(r"^\s*(?:[-*+] |\d+\. |\|)")
TEN_SECONDS_RE = re.compile(r"\b10 (?:s|seconds)\b")
ONE_SECOND_RE = re.compile(r"\b1 (?:s|second)\b")


def blocks(path: Path) -> List[str]:
    """The paragraphs, list items, table rows and headings outside code blocks, each on one line."""
    result: List[str] = []
    current: List[str] = []
    fence: Optional[str] = None

    def flush() -> None:
        if current:
            result.append(" ".join(current))
            current.clear()

    for line in path.read_text(encoding="utf-8").splitlines():
        match = FENCE_RE.match(line)
        if match:
            flush()
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        if not line.strip() or ITEM_START_RE.match(line) or HEADING_RE.match(line):
            flush()
        if line.strip():
            current.append(line.strip())
        if HEADING_RE.match(line):
            flush()
    flush()
    return result


def blocks_with(path: Path, *needles: str) -> List[str]:
    """The blocks of `path` that contain every needle."""
    return [block for block in blocks(path) if all(needle in block for needle in needles)]


def name_of(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


class BlocksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "sample.md"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_blocks_are_paragraphs_list_items_table_rows_and_headings_without_code(self) -> None:
        self.path.write_text(
            "## Heading\nIntro line one\nline two.\n\n- Item one\n  continues.\n- Item two\n\n| a | b |\n"
            "|---|---|\n\n```ts\nconst hidden = 'Retry-After';\n```\n\nLast.\n",
            encoding="utf-8",
        )
        self.assertEqual(
            blocks(self.path),
            [
                "## Heading",
                "Intro line one line two.",
                "- Item one continues.",
                "- Item two",
                "| a | b |",
                "|---|---|",
                "Last.",
            ],
        )
        self.assertEqual(blocks_with(self.path, "Item", "continues"), ["- Item one continues."])
        self.assertEqual(blocks_with(self.path, "Retry-After"), [])


class RateLimitInsideTheWaitTest(unittest.TestCase):
    """A 429 while identifications.get waits: the Retry-After capped at 10 s decides."""

    def test_a_429_ends_the_wait_only_when_the_capped_retry_after_is_longer_than_the_time_left(self) -> None:
        for path in [SERVER / "SKILL.md", *SERVER_REFERENCES, OTHER_LANGUAGES, NEXTJS]:
            with self.subTest(file=name_of(path)):
                statements = blocks_with(path, "429", "Retry-After", "time left")
                self.assertTrue(statements, "the file does not state when a 429 ends the wait")
                for statement in statements:
                    self.assertRegex(statement, TEN_SECONDS_RE, "Retry-After without its 10 s cap")

    def test_the_next_poll_after_a_429_waits_the_longest_of_the_scheduled_wait_1_s_and_retry_after(self) -> None:
        for path in [SERVER / "SKILL.md", *SERVER_REFERENCES, OTHER_LANGUAGES]:
            with self.subTest(file=name_of(path)):
                statements = blocks_with(path, "429", "Retry-After", "time left", "scheduled wait")
                self.assertTrue(statements, "the file does not state the wait after a 429")
                for statement in statements:
                    self.assertRegex(statement, ONE_SECOND_RE, "the wait after a 429 without its 1 s minimum")
                    self.assertRegex(statement, TEN_SECONDS_RE, "Retry-After without its 10 s cap")


class OrdinaryRetriesTest(unittest.TestCase):
    """Calls outside the wait retry after Retry-After as sent, and at least 1 s after a 429 without it."""

    def test_retry_after_is_followed_as_sent_capped_at_10_s(self) -> None:
        files = [SERVER / "SKILL.md", SERVER / "references" / "node.md", SERVER / "references" / "python.md"]
        for path in [*files, OTHER_LANGUAGES]:
            with self.subTest(file=name_of(path)):
                statements = blocks_with(path, "Retry-After", "as sent")
                self.assertTrue(statements, "the file does not state how a retry follows Retry-After")
                for statement in statements:
                    self.assertRegex(statement, TEN_SECONDS_RE, "Retry-After without its 10 s cap")
                    self.assertIn("retries at once", statement, "Retry-After: 0 must retry at once")
                    self.assertRegex(statement, r"\bat least 1 (?:s|second)\b", "no minimum without Retry-After")


class CurrentHistoryContractTest(unittest.TestCase):
    """Only documented public entity routes may appear in executable History examples."""

    def test_no_executable_retired_history_calls_remain(self) -> None:
        retired = re.compile(r"(?:\.history\.(?:search|iterate|iter)|\.History\.(?:Search|All|Iterate)|\.history\(\)\.(?:search|stream))\s*\(")
        for path in SKILLS.rglob("*.md"):
            for code in re.findall(r"```[^\n]*\n(.*?)```", path.read_text(), re.S):
                with self.subTest(file=name_of(path)):
                    self.assertIsNone(retired.search(code))

    def test_node_read_examples_supply_domain_id(self) -> None:
        call = re.compile(r"\b(?:shieldlabs|s)\.identifications\.get\(([^\n]+)")
        for path in SKILLS.rglob("*.md"):
            for code in re.findall(r"```(?:ts|tsx|javascript|js|bash|sh)[^\n]*\n(.*?)```", path.read_text(), re.S):
                for match in call.finditer(code):
                    with self.subTest(file=name_of(path)):
                        self.assertIn("domainId", match.group(1))

    def test_non_node_readers_use_public_domain_scoped_routes(self) -> None:
        for name in ("python", "go", "php", "java", "dotnet"):
            text = (SERVER / "references" / f"{name}.md").read_text()
            with self.subTest(language=name):
                self.assertIn("https://account.shieldlabs.ai/api/v1/domains/", text)
                self.assertNotIn("/api/v1/history/", text)
                self.assertIn("unverified", text)


class HelperUserIdTest(unittest.TestCase):
    """The `userId` key of a helper call overrides the helper's User HID, even as undefined or null."""

    def test_the_key_decides_and_undefined_or_null_mean_anonymous(self) -> None:
        for name in ("react.md", "vue-nuxt.md", "angular.md"):
            with self.subTest(file=name):
                statements = blocks_with(BROWSER / "references" / name, "the `userId` key")
                self.assertTrue(statements, "the file does not say that the userId key overrides the helper")
                self.assertTrue(
                    any(
                        "`undefined`" in s and "`null`" in s and "anonymous" in s and "without the `userId` key" in s
                        for s in statements
                    )
                )

    def test_the_user_linking_pitfall_names_the_override(self) -> None:
        statements = blocks_with(SKILLS / "shieldlabs-user-linking" / "SKILL.md", '`"anonymous"`', "`userId` key")
        self.assertTrue(any("overrides the helper's User HID" in statement for statement in statements))


class LoadFailureTest(unittest.TestCase):
    """After a load error or a load timeout, getAgent() rejects and runOnMount ends without a re-run."""

    FILES = [BROWSER / "SKILL.md"] + [
        BROWSER / "references" / name for name in ("react.md", "vue-nuxt.md", "angular.md", "svelte-sveltekit.md")
    ]

    def test_get_agent_rejects_with_the_load_error(self) -> None:
        for path in self.FILES:
            with self.subTest(file=name_of(path)):
                statements = blocks_with(path, "getAgent()", "rejects with the load error", "fails or times out")
                self.assertTrue(statements, "the file does not say that getAgent() rejects after a failed load")

    def test_run_on_mount_ends_with_the_load_error_and_does_not_run_again(self) -> None:
        for path in self.FILES:
            with self.subTest(file=name_of(path)):
                statements = blocks_with(
                    path, "runOnMount", "fails or times out", "does not run again", "when the agent arrives later"
                )
                self.assertTrue(statements, "the file does not say how runOnMount ends after a failed load")


if __name__ == "__main__":
    unittest.main()
