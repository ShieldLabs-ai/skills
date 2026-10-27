# MCP playbooks

Call `shieldlabs_check_connection` and `shieldlabs_list_domains` first. In every history call below,
replace `example.com` with the chosen hostname. Management calls take the domain's UUID instead.

## Review one identification

1. `shieldlabs_get_identification`:
   `{"domain":"example.com","request_id":"6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a","wait":true,"response_format":"json"}`.
   On missing data check domain/ID, allow asynchronous processing, and make a bounded follow-up
   read. If still missing, report unverified and the elapsed time.
2. `shieldlabs_explain_risk_score` with the same domain/ID, in Markdown for a readable report.
   Compare score, band and flags. Empty weights can be expected from History.
3. Compare `observed_at` with a trusted current clock. An old identification should not authorize
   a fresh protected action; the application's SDK implements replay/freshness checks.
4. Summarize its device and User HID, skipping placeholder IDs. Explain both the evidence and the
   sample window. The MCP summary is not a backend High-Risk Event verdict.

## Investigate an entity

1. `shieldlabs_summarize_entity` with
   `{"domain":"example.com","type":"user_hid","value":"<exact-user-hid>","max_items":100,"response_format":"json"}`.
2. Inspect `summary.risk`, `devices`, `users`, `countries`, `flags_seen` and `window.complete`.
3. Summarize at most five associated devices/accounts if needed. For a timeline, use
   `shieldlabs_search_history` with the same domain/type/value, `limit: 50`, `offset: 0`.
4. Explain one to three relevant identifications. Shared IPs alone are weak account evidence.

For device, visitor, cookie or IPv4 investigations change `type` and the exact value. History
also accepts request and session IDs; summaries do not. Report time/window limits explicitly.

## Manage an integration

1. Read existing domains; reuse the intended one. If absent and registration is authorized,
   `shieldlabs_add_domain` with `domain: "example.com"` and the intended `allow_subdomains` setting.
   Leave `include_secret` false unless installing a needed credential into a private store.
2. Read the domain with `shieldlabs_get_domain`. Use `shieldlabs_patch_domain` only for requested
   settings. A root domain's subdomain behavior is controlled by `allow_subdomains`.
3. `shieldlabs_list_webhooks` with `domain_id`; reuse an existing endpoint rather than creating
   duplicates. Implement and deploy the receiver using the webhooks skill before testing it.
4. If authorized and absent, `shieldlabs_create_webhook` with `domain_id`, `name` and the user's
   public HTTPS `url`. Obtain/store the signing secret privately for the receiver as needed.
5. `shieldlabs_verify_webhook` sends a signed ping. Check the resulting status. Then
   `shieldlabs_test_webhook`; inspect `delivered`, HTTP status, latency and timeout.
6. Read the webhook again and check receiver logs, with secrets and personal payloads redacted.
   For a rename use `patch_webhook` with only `name`. For a URL change use `confirm: true`, then
   repeat verification and test. `enable_webhook` restores delivery; `disable_webhook` requires
   `confirm: true` and authorization to stop delivery.
7. Domain/webhook deletion and key/secret rotation are maintenance actions, never test cleanup
   for pre-existing resources. Only perform them when requested. Record created test resource
   UUIDs so authorized cleanup targets exactly those resources.

## Verify the real visit chain

1. Note the target hostname, current time and expected production snippet/public key.
2. Open the actual page and trigger an identification. Capture the UUID from the actual callback
   or application request. Do not manufacture a History row or use a sample webhook as a visit.
3. Read that same UUID through `get_identification` with the explicit domain and `wait: true`.
4. Compare domain, ID, time, score and flags. Call `explain_risk_score` for the same UUID.
5. Search its visitor/device history and summarize that entity. If real webhook delivery is part
   of the requested setup, match the received event's identification UUID to this visit.
6. Report each stage separately: page loaded, browser ID obtained, History found, Risk Score
   returned, explanation read, real webhook received (if tested). Distinguish pending from failed.

## Debug delivery or a signature

Read `get_webhook`, then use verify/test only for an authorized receiver. A 4xx, 5xx or timeout is
an endpoint result, not automatically an MCP failure. Inspect the receiver's raw-body handling,
correct secret and response path. Verify signatures locally with the SDK; do not ask the user to
paste a secret. A valid ping does not prove the scored-event branch works.
