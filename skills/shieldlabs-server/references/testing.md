# Test the server side without the live API

## Unit tests

Wrap the verdict read in one function of your own (for example `readIdentification(requestId)`,
which returns an identification or `null` on any failure) and replace it in unit tests. Build the
identifications as data: a plain object with the `Identification` fields in Node.js,
`Identification.from_dict()` in Python, or verify a recorded webhook body with a test secret
(`constructEvent`) in any SDK. Pass `now` (`now=`, `Now`) to the policy helper to test the
freshness window.

## Integration tests against a local History API

[`scripts/history_mock.py`](../scripts/history_mock.py) (Python 3, standard library) answers the
History API paths with History rows, so the SDK's real client, polling and model mapping run:

```bash
python3 <shieldlabs-server skill directory>/scripts/history_mock.py --port 4010 --rows rows.json
export SHIELDLABS_API_BASE_URL=http://127.0.0.1:4010
export SHIELDLABS_API_KEY=sec_test0000-test0000-test0000
```

- Use `127.0.0.1` or `localhost`: some SDKs accept a plain `http` base URL only for loopback hosts.
- Where the base URL goes: the Node.js and Go clients take it as an option (see their references);
  Python, PHP, Java's `ShieldLabsClient.fromEnvironment()` and `getIdentification` of
  `@shieldlabs-ai/next/server` read `SHIELDLABS_API_BASE_URL`; .NET takes `BaseUrl` in its options.
- Without `--rows`, every request ID finds a trusted identification observed just now.

`rows.json` maps request IDs to the History fields that differ from that default, or to `null`
for "not found". `minutes_ago` moves the row into the past:

```json
{
  "6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a": {
    "score": 80, "connection_type": "proxy", "is_proxy": true, "is_datacenter": true, "is_antidetect": true,
    "score_details": "[{\"Value\":60,\"Description\":\"Antidetect browser (turn_block)\"},{\"Value\":10,\"Description\":\"Is proxy\"},{\"Value\":10,\"Description\":\"Is datacenter\"}]"
  },
  "2b9e7c1d-4f3a-4e8b-9d6c-1a2b3c4d5e6f": { "is_browser_automation": true, "score": 60,
    "score_details": "[{\"Value\":60,\"Description\":\"Browser Automation\"}]" },
  "3c2d1e0f-9a8b-4c7d-8e6f-5a4b3c2d1e0f": { "score": 999, "device_id": "00000000-0000-0000-0000-000000000000",
    "score_details": "[{\"Value\":999,\"Description\":\"User has been banned 1H, to many requests\"}]" },
  "7d6c5b4a-3e2f-4a1b-8c9d-0e1f2a3b4c5d": { "minutes_ago": 10 },
  "0b8e6f3c-2d4a-4b1e-9c7f-5a6d8e9f0a1b": null
}
```

Those five request IDs exercise the `blocked_band`, `blocked_flag`, `rate_limited`, `stale` and
`missing` branches of the policy helper. Lookups by `device_id`, `user_hid`, `visitor_id`, `ip`,
`session_id` and `cookie_id` search the rows of the file, which is how account-abuse checks are
tested.

## History rows are not the `Identification` model

The History API returns rows with their own field names; the SDKs map them to `Identification`.
A hand-written mock must use the row names, or the SDK finds no score, time or flags:

| `Identification` | History row |
|---|---|
| `risk_score` | `score` |
| `observed_at` | `created_at`, as `YYYY-MM-DD HH:MM:SS.mmm` in UTC without a zone |
| `public_ip.ip`, `public_ip.country` | `ip` (`"0.0.0.0"` when none), `country` (an English country name) |
| `signals` | `score_details`: a JSON string of `[{"Value": 60, "Description": "..."}]`; entries with `Value` 0 are left out |
| `detection_flags.vpn`, `tor`, `proxy`, `privacy_relay`, `incognito`, `search_bot` | `is_vpn`, `is_tor`, `is_proxy`, `is_privacy_relay`, `is_incognito`, `is_search_bot` |
| `datacenter_ip`, `abuser`, `anti_detect_browser`, `browser_automation`, `javascript_disabled` | `is_datacenter`, `is_abuser`, `is_antidetect`, `is_browser_automation`, `is_js_disabled` |
| `os_mismatch`, `os_not_detected`, `timezone_mismatch`, `stun_not_checked`, `check_incomplete` | `is_os_mismatch`, `is_os_not_detected`, `is_timezone_mismatch`, `is_stun_not_checked`, `check_incomplete` |
| `suspicious_paid_click` | `is_suspicious_paid_click` (left out when false) |
| `browser_vpn_proxy` | `connection_type` equal to `"browser_vpn_proxy"` |
| `domain` | `site_domain` when present, else `domain` |
| `request_id`, `visitor_id`, `device_id`, `session_id`, `cookie_id`, `user_hid`, `connection_type`, `os`, `browser`, `device_type` | the same names |

The response is `{"data": [rows, newest first], "total": n}`; a request ID that is not found gives
`{"data": [], "total": 0}`.

## Webhooks

Sign a body with the test secret and post it to your route (shieldlabs-webhooks skill, "Test the
receiver"). Use a body with the webhook field names (`risk_score`, `observed_at`,
`detection_flags`), which differ from the History row names above.
