# Other backend languages

The server SDKs cover Node.js, Python, Go, PHP, Java and .NET. From any other language (Ruby,
Rust, Elixir and others) call the History API over HTTPS and follow the same flow. The full
reference is at https://docs.shieldlabs.ai/api/server-api.

## Read one identification

```text
GET https://account.shieldlabs.ai/api/v1/history/request_id/{requestId}?limit=1
Authorization: Bearer sec_your_private_key
Accept: application/json
```

- The answer is `{"data": [row, ...], "total": N}`. An empty `data` means "not scored yet".
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

## Validate before sending

The History API does not validate its input, so check it yourself:

- The search type must be one of `ip`, `user_hid`, `visitor_id`, `request_id`, `device_id`,
  `session_id`, `cookie_id`. Any other value returns the latest rows of the whole domain.
- UUID values must match `^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`
  (send them lowercase); `ip` must be a dotted IPv4 address. Malformed values fail with a 500.
- `user_hid` must be non-empty, must not contain `/` and must not be `.` or `..`: the History API
  cannot match those values. Send it as one path segment in canonical form: letters, digits,
  `- . _ ~` and `$ & + , : ; = @` stay as they are, and every other byte of the UTF-8 text is
  percent-encoded (space, `%`, `?`, `#`, non-ASCII characters). The hex User HIDs of the SDK
  helpers need no escaping.
- `limit` must be 1 to 100 (other values silently become 20), `offset` 0 or more.

## Read the row

History rows use different names from the SDK model: `score` (0-100, or `999` as the rate-limit
marker), `created_at` as `YYYY-MM-DD HH:MM:SS.mmm` in UTC without a zone designator, `ip` with
`"0.0.0.0"` when unknown, `country` as an English country name, `is_*` booleans for the detection
flags, and `score_details` as a JSON-encoded string ([testing.md](testing.md) maps every field). Apply the same guards as the SDK policy
helper: missing, replayed, older than 5 minutes, score above 100, the all-zero `device_id`,
automation flags, the dangerous band (60-100).

## Verify a webhook

`X-Shield-Signature: sha256=<lowercase hex HMAC-SHA256>`, computed over the raw request body with
the endpoint signing secret as the key, **including** its `whsec_` prefix, as UTF-8 bytes. Compare
in constant time before parsing the JSON, and accept a list of secrets while you rotate one.
