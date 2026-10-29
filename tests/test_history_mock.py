"""Tests for the History API mock of the shieldlabs-server skill (standard library unittest)."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "shieldlabs-server" / "scripts" / "history_mock.py"
spec = importlib.util.spec_from_file_location("history_mock", SCRIPT)
assert spec is not None and spec.loader is not None
history_mock = importlib.util.module_from_spec(spec)
sys.modules["history_mock"] = history_mock
spec.loader.exec_module(history_mock)

BAD = "6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a"
MISSING = "0b8e6f3c-2d4a-4b1e-9c7f-5a6d8e9f0a1b"
OLD = "7d6c5b4a-3e2f-4a1b-8c9d-0e1f2a3b4c5d"
HID = "9f86d081884c7d659a2feaa0c55ad015"
ROWS = {
    BAD: {"score": 80, "is_antidetect": True, "user_hid": HID},
    MISSING: None,
    OLD: {"minutes_ago": 10, "user_hid": HID},
}


def parse_created_at(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)


class HistoryMockTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "rows.json"
        path.write_text(json.dumps(ROWS), encoding="utf-8")
        self.mock = history_mock.HistoryMock(history_mock.load_rows(path))

    def test_default_row_is_a_fresh_trusted_identification(self) -> None:
        status, body = self.mock.search("request_id", "11111111-2222-4333-8444-555555555555", 1, 0)
        self.assertEqual(status, 200)
        self.assertEqual(body["total"], 1)
        row = body["data"][0]
        self.assertEqual(row["score"], 0)
        self.assertEqual(row["score_details"], "")
        self.assertFalse(any(row[column] for column in history_mock.FLAG_COLUMNS))
        age = datetime.now(timezone.utc) - parse_created_at(row["created_at"])
        self.assertLess(age, timedelta(seconds=5))

    def test_rows_file_overrides_and_not_found(self) -> None:
        row = self.mock.search("request_id", BAD.upper(), 1, 0)[1]["data"][0]
        self.assertEqual((row["score"], row["is_antidetect"], row["identification_id"]), (80, True, BAD))
        self.assertEqual(self.mock.search("request_id", MISSING, 1, 0)[1], {"data": [], "total": 0})
        old = self.mock.search("request_id", OLD, 1, 0)[1]["data"][0]
        age = datetime.now(timezone.utc) - parse_created_at(old["created_at"])
        self.assertGreater(age, timedelta(minutes=9))
        self.assertNotIn("minutes_ago", old)

    def test_other_lookups_search_the_file_newest_first(self) -> None:
        status, body = self.mock.search("user_hid", HID, 100, 0)
        self.assertEqual(status, 200)
        self.assertEqual([row["identification_id"] for row in body["data"]], [BAD, OLD])
        self.assertEqual(self.mock.search("user_hid", HID.upper(), 100, 0)[1]["total"], 0)  # exact match
        self.assertEqual(self.mock.search("user_hid", HID, 1, 1)[1]["data"][0]["identification_id"], OLD)
        self.assertEqual(self.mock.search("user_hid", HID, 500, 0)[1]["total"], 2)  # limit 500 becomes 20

    def test_current_wire_id_does_not_hide_legacy_sdk_mismatch(self) -> None:
        row = self.mock.search("request_id", BAD, 1, 0)[1]["data"][0]
        self.assertEqual(row["identification_id"], BAD)
        self.assertNotIn("request_id", row)
        self.assertIn("is_ai_bot", row)
        self.assertIn("is_device_spoof", row)
        self.assertEqual(self.mock.search("identification_id", BAD, 1, 0)[1]["data"], [row])

    def test_legacy_contract_is_explicit(self) -> None:
        mock = history_mock.HistoryMock({}, contract="legacy")
        row = mock.search("request_id", BAD, 1, 0)[1]["data"][0]
        self.assertEqual(row["request_id"], BAD)
        self.assertNotIn("identification_id", row)
        self.assertNotIn("is_ai_bot", row)
        with self.assertRaises(ValueError):
            history_mock.HistoryMock({}, contract="invalid")

    def test_invalid_values_behave_like_the_api(self) -> None:
        self.assertEqual(self.mock.search("request_id", "not-a-uuid", 1, 0)[0], 500)
        self.assertEqual(self.mock.search("ip", "2001:db8::1", 1, 0)[0], 500)
        self.assertEqual(self.mock.search("email", "x", 1, 0)[0], 400)

    def test_only_rows(self) -> None:
        mock = history_mock.HistoryMock(self.mock.rows, only_rows=True)
        self.assertEqual(mock.search("request_id", "11111111-2222-4333-8444-555555555555", 1, 0)[1]["total"], 0)

    def test_rejects_bad_rows_files(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rows.json"
            for content in ('["x"]', '{"not-a-uuid": {}}', '{"%s": 5}' % BAD):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    history_mock.load_rows(path)

    def test_http_server(self) -> None:
        server = history_mock.ThreadingHTTPServer(("127.0.0.1", 0), history_mock.make_handler(self.mock, quiet=True))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}/api/v1"
        request = urllib.request.Request(f"{base}/domains/11111111-1111-4111-8111-111111111111/history/identifications/{BAD}",
                                         headers={"Authorization": "Bearer sec_test0000-test0000-test0000"})
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.headers["Content-Type"], "application/json")
            body = json.loads(response.read())
        self.assertEqual(body["data"]["risk"]["score"], 80)
        self.assertEqual(body["data"]["signals"], {"state": "unavailable", "items": []})
        self.mock.rows[BAD]["entity_signals"] = {"state": "ok", "items": ["browser_automation"]}
        with urllib.request.urlopen(request, timeout=5) as response:
            available = json.loads(response.read())["data"]
        self.assertEqual(available["signals"], {"state": "ok", "items": ["browser_automation"]})
        self.mock.rows[BAD]["entity_signals"] = {"state": "ok", "items": []}
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(json.loads(response.read())["data"]["signals"], {"state": "ok", "items": []})

        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"{base}/domains/11111111-1111-4111-8111-111111111111/history/identifications/{BAD}", timeout=5)
        self.assertEqual(caught.exception.code, 401)
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()
