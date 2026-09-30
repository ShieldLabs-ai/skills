# Investigation playbooks

Each playbook lists the tool calls in order, with example arguments. Replace the example values
with the ones the user gave. Report with the template of the skill.

## Review one request

1. `shieldlabs_get_identification` with `{"request_id": "6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a"}`.
   If it is not found, report "unverified": the identification may be seconds old (try again
   shortly) or belong to another domain. Stop there.
2. `shieldlabs_explain_risk_score` with the same `request_id`: band, weighted risk signals, flags.
3. `shieldlabs_current_time`, then compare with `observed_at`. Older than about 5 minutes means
   the request ID should not authorize a new protected action.
4. `shieldlabs_summarize_entity` with `{"type": "device_id", "value": "<device_id>"}`, unless the
   device ID is `00000000-0000-0000-0000-000000000000`: how many accounts use the device.
5. `shieldlabs_summarize_entity` with `{"type": "user_hid", "value": "<user_hid>"}`, unless it is
   `null`, `"anonymous"`, `"fail"`, `"-1"` or `"unknown"` (these name no account): the account's
   usual devices and countries.
6. Suggest an action with the decision table of the shieldlabs-risk-decisions skill: the band, the
   sensitivity of the action it protected, then the account evidence. Remind the user that one
   request ID authorizes one action: a request ID that was already used must be refused.

## Investigate an account (User HID)

1. `shieldlabs_summarize_entity` with `{"type": "user_hid", "value": "<user_hid>", "max_items": 200}`.
   Note the worst band, band counts, devices, countries, IPs, flags and rate-limit markers.
2. For the account's top devices (at most 5, skipping the all-zero device ID), call
   `shieldlabs_summarize_entity` with `{"type": "device_id", "value": "<device_id>"}` and look at
   `users.distinct`: other accounts on the same devices point to multi-accounting.
3. `shieldlabs_search_history` with `{"type": "user_hid", "value": "<user_hid>", "limit": 50}` for
   the timeline: country changes within an hour, new devices, bursts of identifications, the
   dangerous identifications.
4. `shieldlabs_explain_risk_score` for the riskiest one to three identifications.
5. Mention that the High-Risk Events ShieldLabs detected on this user are on the user card in the
   analytics dashboard.

The server's `investigate_user` prompt runs the same steps.

## Investigate a device, a visitor or a cookie

1. `shieldlabs_summarize_entity` with `type` `device_id`, `visitor_id` or `cookie_id`.
2. For each account in `users.top`, `shieldlabs_summarize_entity` with `user_hid` (at most 5) to
   see whether those accounts also share other devices.
3. `shieldlabs_search_history` with the same `type` and `value` to read the individual
   identifications when the timeline matters.

A device ID survives cleared cookies and private windows, so it is the strongest of the three for
counting accounts.

## Investigate an IP address

1. `shieldlabs_summarize_entity` with `{"type": "ip", "value": "203.0.113.24"}` (IPv4 only).
2. Read it as weak evidence: offices, universities and mobile carriers put many people behind one
   address. Look at `rate_limit_markers` (the IP was blocked for sending too many
   identifications), `flags_seen` (`datacenter_ip`, `proxy`, `tor`) and the accounts found.

## Why was a signup blocked or allowed?

1. Get the request ID from the application logs (the backend should log it with every decision).
2. Run "Review one request".
3. Compare with the reason the application logged (`missing`, `replayed`, `stale`,
   `rate_limited`, `no_device_signals`, `blocked_flag`, `blocked_band`, or its own rule), and say
   which check decided. Suggest tuning per action when the evidence looks legitimate.

## Debug a webhook signature

1. Ask for the raw body exactly as the server received it (base64 of the logged bytes is safest)
   and the `X-Shield-Signature` header value.
2. `shieldlabs_verify_webhook_signature` with `payload`, `signature_header` and
   `payload_encoding: "base64"` when you pass base64. Let it read `SHIELDLABS_WEBHOOK_SECRET` from
   the server environment instead of pasting the secret.
3. Act on its `checks`: a re-serialized or pretty-printed body means a JSON parser ran before
   verification; a missing `whsec_` prefix means the secret was stripped; a mismatch with a valid
   format usually means the secret of another endpoint, or one replaced by **Rotate secret**.

## Check the remaining included identifications

`shieldlabs_get_domain_profile` (needs `SHIELDLABS_SECRET_KEY` and `SHIELDLABS_DOMAIN`). A negative
`remaining_identifications` means the account is over its included volume. Call it once per
question, never in a loop.
