# Risk decisions in Python

Start with the [Python public History reader](../../shieldlabs-server/references/python.md).
Its dictionary returned by read_card is a current entity card, not the SDK's normalized webhook Identification model.
Apply the [action decision table](../SKILL.md#decision-table) to these wire fields directly.
Do not call an old normalized-model helper with this card or invent a conversion method.

## Current card action path

1. Read the submitted UUID under the selected public domain UUID. Match `type=identification`,
   `id` and `domain_id`. A network/API failure, wrong identity or missing card is unverified.
2. Require `risk.state=ok`, numeric integer `risk.score` in 0–100, a valid `risk.band`, and
   `signals.state=ok` with a list of codes in `signals.items`. Preserve unavailable/missing
   states. Detailed weights are optional; their absence does not erase available signal codes.
3. Atomically claim this exact tenant/domain/identification UUID (record the expected action as metadata, not a separate uniqueness scope) in your application's store.
   An existing claim or unavailable store cannot authorize the action. Check `created_at` with
   timezone against a five-minute freshness window. An invalid timestamp is unverified.
4. For a signed-in action, compare `user_hid` to the HMAC User HID computed from the authenticated
   account. Never trust the client to select the expected account. A mismatch can only make the
   decision stricter. Missing or nil `device_id` means no usable device signals.
5. Apply the table: replay/stale or `browser_automation`/`javascript_disabled` blocks; Banned IP
   `banned_ip` means step-up or review. Otherwise use the returned trusted/suspicious/dangerous
   band and action sensitivity. Unknown data follows the unverified path, never a clean allow.
6. Log domain, identification UUID, decision and reason privately. Return a generic application
   result. Keep HRE status/confidence separate; use backend HRE results for account-abuse decisions.

The public card never has Risk Score 999. That Banned IP marker in a scored webhook is not a
fourth band; an HTTP 429 `rate_limited` is a separate transport failure. Do not rename it or add
it as an input filter. A successful HTTP response is insufficient when required states are unavailable.

For an asynchronous signed webhook, the official SDK can verify and normalize its own webhook
model, after signature verification and event_id deduplication. That path does not replace the
current card guards above or identify which account is authenticated in the application.
