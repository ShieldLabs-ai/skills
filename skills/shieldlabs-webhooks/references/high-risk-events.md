# Receive scored results and group transitions

Verify the exact raw bytes with the SDK first. Validate known envelopes with the bundled
[public webhook schema](../assets/webhook-event.schema.json) or
[group schema](../assets/multiaccount-changed-event.schema.json), pinned to
[public contract 3fc61ef](https://github.com/ShieldLabs-ai/shieldlabs-openapi/tree/3fc61efd051e408c9a1057707120404beb929c3e/dist/schemas).
The [JavaScript validator](../assets/validate_event.mjs) supplies a runnable raw-envelope check. Do not fetch schemas at request time. Use a JSON Schema 2020-12 validator supporting date-time
and UUID formats. Unknown future versions/types go to a retained review path; do not interpret
an unsupported group version as a successful business outcome.

Enqueue both known types atomically with a nonempty signed envelope `event_id`. A UUID is
not required for an event key: current Core group IDs are 40 hex characters. SDK parsing can
return an unknown typed event for the new group type, while its verified raw envelope is usable.
Unknown future events may be acknowledged without business effects; a known group must not
disappear into this branch. Storage/queue failure requires a non-2xx response.

`identification.scored` uses `data.identification_id` to join a visit. Its optional `data.hre`
contains account_sharing/account_takeover/impossible_travel results. Keep explicit
not_evaluated/not_applicable outcomes. Multi-account groups arrive separately and contain no
identification UUID or Risk Score. Never add `hre.multi_account` or fabricate a score for them.

For `hre.multi_account.changed`:

1. Match the expected site/domain for the signing endpoint, schema and kind.
2. Deduplicate `event_id` with the consumer's database effects in one transaction. Queue
   acceptance and consumer application have separate durable states; a failed effect must roll back.
3. Key group state by site, source publication epoch and `cluster_id`. Compare revisions as
   UInt64 decimal strings using Python integers, Java BigInteger or JavaScript BigInt, never
   JavaScript Number. Store the original string. Check source version equals revision.
4. Apply only a strictly newer revision. Retries and out-of-order events must not undo newer
   state. Membership is the complete `user_hids` list; check `members_complete` and count.
   Use the full membership for state replacement, not only added/removed deltas.
5. `detected` starts a group, `updated` changes it, `resolved` ends the detection. Preserve the
   resolved tombstone/revision so an old detection cannot resurrect it. Resolved does not prove
   each member safe. Do not automatically clear unrelated account restrictions.

[apply_multiaccount.py](../assets/apply_multiaccount.py) is a runnable SQLite application example
of atomic deduplication, state replacement and revision ordering. Call it only on a previously
verified/schema-validated durable job, using a dedicated connection and trusted expected scope.
Adapt tables/transactions to your application. Put external actions in a transactional outbox
with their own idempotency keys. Retain unprocessable jobs for investigation.

Verify ping delivery, scored Test delivery, and a signed fixture for each detected/updated/resolved
branch separately. Then verify a real group notification when the deployed Core release profile
supports emission and the authorized test scenario creates a transition. Never create unrelated
accounts or claim a synthetic fixture proves live detector emission.
