"""Application SQLite consumer example. Input must already be signature/schema verified.

Use a dedicated connection and a durable queue. This is application code, not an SDK API.
"""
import json
import re


def create_tables(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS processed_events (
      site INTEGER NOT NULL, event_id TEXT NOT NULL, PRIMARY KEY(site, event_id));
    CREATE TABLE IF NOT EXISTS multiaccount_groups (
      site INTEGER NOT NULL, epoch TEXT NOT NULL, cluster TEXT NOT NULL,
      revision TEXT NOT NULL, payload TEXT NOT NULL,
      PRIMARY KEY(site, epoch, cluster));
    """)


def revision(value):
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value):
        raise ValueError("revision must be a positive decimal string")
    number = int(value)
    if number > 18446744073709551615:
        raise ValueError("revision exceeds UInt64")
    return number


def apply_transition(db, event, expected_site, expected_domain, after_write=None):
    """Apply once, atomically with event dedup; return applied, duplicate or stale.

    Run on a dedicated connection outside an existing transaction. after_write is a test seam
    for demonstrating rollback; do not put remote side effects inside this transaction.
    """
    if event.get("event_type") != "hre.multi_account.changed":
        raise ValueError("wrong event type")
    if event.get("schema_version") != "2026-10-07":
        raise ValueError("unsupported group schema; retain job for review")
    data = event["data"]
    if event.get("site_id") != expected_site or data["domain"] != expected_domain:
        raise ValueError("wrong site/domain")
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not re.fullmatch(r"[a-f0-9]{40}", event_id):
        raise ValueError("invalid event ID")
    source = data["source"]
    epoch = source["publication_epoch"]
    if epoch != "multiaccount-v1" or source["publication_version"] != data["revision"]:
        raise ValueError("unsupported publication source")
    incoming = revision(data["revision"])
    if data["members_complete"] is not True or len(data["user_hids"]) != data["users_count"]:
        raise ValueError("incomplete membership")
    if len(set(data["user_hids"])) != data["users_count"]:
        raise ValueError("duplicate members")
    key = (expected_site, epoch, data["cluster_id"])
    db.execute("BEGIN IMMEDIATE")
    try:
        existing = db.execute("SELECT 1 FROM processed_events WHERE site=? AND event_id=?",
                              (expected_site, event_id)).fetchone()
        if existing:
            db.commit()
            return "duplicate"
        current = db.execute("SELECT revision FROM multiaccount_groups WHERE site=? AND epoch=? AND cluster=?",
                             key).fetchone()
        outcome = "stale" if current and incoming <= revision(current[0]) else "applied"
        if outcome == "applied":
            db.execute("""INSERT INTO multiaccount_groups VALUES (?,?,?,?,?)
                ON CONFLICT(site,epoch,cluster) DO UPDATE SET revision=excluded.revision,payload=excluded.payload""",
                       key + (data["revision"], json.dumps(event)))
        db.execute("INSERT INTO processed_events VALUES (?,?)", (expected_site, event_id))
        if after_write:
            after_write()
        db.commit()
        return outcome
    except BaseException:
        db.rollback()
        raise
