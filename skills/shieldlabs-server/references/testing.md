# Test server verification

## Use a controlled local API

Start the included mock before running an application's server integration:

```bash
python3 <skill-directory>/scripts/history_mock.py --port 4010
```

Set SHIELDLABS_API_BASE_URL=http://127.0.0.1:4010 and
SHIELDLABS_DOMAIN_ID=11111111-1111-4111-8111-111111111111 in the private test environment.
Use a fake API key accepted by the mock. Do not connect this test configuration to production.
The mock returns a scored identification card for a valid UUID. GET /api/v1/domains returns the
test registration. The supported card route is /api/v1/domains/{domain_id}/history/identifications/{id}.
The retired unscoped route returns endpoint_retired.

For configured cases use --rows rows.json. Each key is an identification UUID and the value is a
fixture override: score, minutes_ago and legacy fixture fields; null means missing. These are
controlled test inputs, not evidence that the real detector emitted those values. A score above
100 makes the HTTP mock return rate_limited rather than inventing a valid entity Risk Score.

## Current response shape

```json
{"data":{"type":"identification","id":"33333333-3333-4333-8333-333333333333","domain_id":"11111111-1111-4111-8111-111111111111","domain":"example.com","risk":{"state":"ok","score":30,"band":"suspicious","as_of":"2026-10-29T09:00:00Z"},"signals":{"state":"unavailable","items":[]},"created_at":"2026-10-29T09:00:00Z"}}
```

Match data.id to the browser UUID. Read risk.state before using risk.score. Unavailable is unknown,
not zero. A list has data as an array and an optional next_page_token; it has no exact total.
Use the SDK's domain-scoped reads and preserve the original entity card when availability matters.
Detailed weights may be unavailable even when Score is known; do not invent contributions.

## Application checks

Verify a scored identification, a blocked band, missing/unavailable result, stale result and replay
rejection. Claim each identification ID atomically. Exercise transport errors with a controlled
HTTP response, not by generating repeated real browser identifications. Mocked rows and synthetic
webhooks establish client handling only; live scoring and signed event delivery need separate tests.

For webhooks, sign the original bytes with a local test secret. Deduplicate verified envelopes by
event_id and correlate data.identification_id to the action UUID. A valid ping does not verify the
scored or group-event consumer. Follow the webhooks skill for signature and receiver tests.
