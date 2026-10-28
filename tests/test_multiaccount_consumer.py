"""Execute the shipped consumer against real public-contract fixtures and SQLite transactions."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "consumer", ROOT / "skills/shieldlabs-webhooks/assets/apply_multiaccount.py")
consumer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(consumer)


class MultiaccountConsumerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        consumer.create_tables(self.db)
        self.events = {name: json.loads((ROOT / ("tests/fixtures/webhook-multiaccount-" + name + ".json")).read_text())
                       for name in ("detected", "updated", "resolved")}

    def tearDown(self):
        self.db.close()

    def apply(self, event, **kwargs):
        return consumer.apply_transition(self.db, event, 319, "example.com", **kwargs)

    def state(self):
        return json.loads(self.db.execute("SELECT payload FROM multiaccount_groups").fetchone()[0])

    def test_three_transition_types_and_retries(self):
        for name in ("detected", "updated", "resolved"):
            self.assertEqual(self.apply(self.events[name]), "applied")
            self.assertEqual(self.apply(self.events[name]), "duplicate")
        self.assertEqual(self.state()["data"]["action"], "resolved")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0], 3)

    def test_out_of_order_cannot_resurrect_resolved_group(self):
        self.assertEqual(self.apply(self.events["resolved"]), "applied")
        self.assertEqual(self.apply(self.events["detected"]), "stale")
        self.assertEqual(self.state()["data"]["action"], "resolved")

    def test_failure_rolls_back_both_state_and_dedup(self):
        def fail():
            raise RuntimeError("simulated commit failure")
        with self.assertRaises(RuntimeError):
            self.apply(self.events["detected"], after_write=fail)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM multiaccount_groups").fetchone()[0], 0)
        self.assertEqual(self.apply(self.events["detected"]), "applied")

    def test_uint64_precision_above_javascript_safe_integer(self):
        for index, version in enumerate(("9007199254740992", "9007199254740993", "18446744073709551615")):
            event = copy.deepcopy(self.events["detected"])
            event["event_id"] = format(index + 1, "040x")
            event["data"]["revision"] = version
            event["data"]["source"]["publication_version"] = version
            self.assertEqual(self.apply(event), "applied")
        self.assertEqual(self.state()["data"]["revision"], "18446744073709551615")
        with self.assertRaises(ValueError):
            consumer.revision("18446744073709551616")

    def test_wrong_scope_incomplete_membership_and_source_fail_closed(self):
        for path, value in ((('site_id',), 320), (('data', 'domain'), 'other.example'),
                            (('data', 'members_complete'), False),
                            (('data', 'users_count'), 9),
                            (('data', 'source', 'publication_epoch'), 'future'),
                            (('data', 'source', 'publication_version'), '8')):
            event = copy.deepcopy(self.events['detected'])
            target = event
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            with self.assertRaises(ValueError):
                self.apply(event)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0], 0)

    def test_same_cluster_on_another_site_is_separate(self):
        self.apply(self.events['detected'])
        event = copy.deepcopy(self.events['detected'])
        event['site_id'] = 320
        consumer.apply_transition(self.db, event, 320, 'example.com')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM multiaccount_groups").fetchone()[0], 2)
