# Other backend languages

The server SDKs cover Node.js, Python, Go, PHP, Java and .NET. From any other language (Ruby,
Rust, Elixir and others) call the History API over HTTPS and follow the same flow. The full
reference is at https://docs.shieldlabs.ai/api/server-api.

## Read one identification

```text
GET https://account.shieldlabs.ai/api/v1/domains/{domainId}/history/identifications/{identificationId}
Authorization: Bearer sec_your_private_key
Accept: application/json
```

- The answer is `{"data": {"type": "identification", "id": "...", "risk": {"state": "ok", "score": 30}, ...}}`. Match the ID and public domain UUID. Missing or unavailable remains unverified.
- Wait the way the SDKs do: a total budget (10 seconds by default), the first request at once,
  then waits of p, 2p, 4p, 6p and then 8p for a poll interval p, each capped at max(2 s, p) (with
  the default 250 ms: 250 ms, 500 ms, 1 s, 1.5 s, then every 2 s), a wait cut short so that the
  last request runs at the deadline. Send each request once (no retries inside the loop), with a
  timeout of the time left but at least 1 second.
- Keep polling after a 429, a 5xx, a connection error or a timeout. After a 429 wait the longest
  of the next scheduled wait, 1 second and `Retry-After` capped at 10 seconds (a missing
  `Retry-After`, `0` or a date in the past counts as 0); when the capped `Retry-After` is longer
  than the time left, stop with the rate-limit error. The limit is about 15 requests per second
  per domain, shared by every caller.
- Stop at once on 400, 401, 403 or 404: a wrong request, key or base URL does not heal.
- At the deadline, report the error of the last request when it failed; otherwise the
  identification was not found in time, which means unverified.
- A single read outside that loop retries connection errors, timeouts, 429 and 5xx with
  exponential backoff, and never retries 400, 401, 402, 403 or 404. It follows `Retry-After` as
  sent, capped at 10 seconds (`0` or a date in the past retries at once), and waits at least
  1 second after a 429 without it.

## Validate and read the card

Follow [current History](current-history.md) for domain UUIDs, entity resources, flat filters,
cursor pagination and availability. Read `data.id`, `data.domain_id`, `risk.state`, `risk.score`,
`signals.state`/`items` and `created_at`. A card is not the old flat row. Preserve optional fields
and unknown states. Risk unavailable is not zero; aggregate cards need not expose a numeric score.
Apply action freshness, replay and authenticated User HID checks before the policy decision.

## Verify a webhook

`X-Shield-Signature: sha256=<lowercase hex HMAC-SHA256>`, computed over the raw request body with
the endpoint signing secret as the key, **including** its `whsec_` prefix, as UTF-8 bytes. Compare
in constant time before parsing the JSON, and accept a list of secrets while you rotate one.
