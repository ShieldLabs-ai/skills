# MCP playbooks

Start with `shieldlabs_check_connection` and `shieldlabs_list_domains`. Resolve the hostname to
its public UUID and use that UUID for every History call. Examples use an illustrative UUID;
replace it with the returned value, not a made-up domain.

## Review one identification

1. Capture the browser's actual identification UUID. During setup allow 10–15 seconds for
   asynchronous processing, then call:

   ```json
   {"domain":"11111111-1111-4111-8111-111111111111","identification_id":"33333333-3333-4333-8333-333333333333","wait":true,"response_format":"json"}
   ```

   Use `shieldlabs_get_identification`. If still pending, wait and read the same UUID once more.
   A missing result remains unverified. Do not create another identification just to poll.
2. Call `shieldlabs_explain_risk_score` with the same domain and identification_id. Inspect score,
   band and signal availability. Missing weights never establish zero contribution.
3. Match ID, domain and created_at to the action. The application enforces freshness and replay
   prevention with its server SDK; an investigation read does not authorize that action.
4. For linked activity use the visitor/device/user card via `shieldlabs_get_history`.

## Investigate an entity

Call `shieldlabs_get_history` with domain, resource and resource_id. User cards use the exact
User HID; visitor/device cards use their UUID; IP cards use IPv4.

```json
{"domain":"11111111-1111-4111-8111-111111111111","resource":"user","resource_id":"<exact-user-hid>","response_format":"json"}
```

Inspect risk, signals, high_risk_events, related_counts and availability. Read linked records
with `relation` and `relation_limit`; continue only with that relation's returned cursor as
`relation_page_token`, keeping the card, window and filters unchanged. Do not invent totals or
turn unavailable counts into zero. Cookie and session IDs may be relations, not standalone cards.

## Filter and page a list

Use `shieldlabs_list_history`. Lists exist for identifications and user only.

```json
{"domain":"11111111-1111-4111-8111-111111111111","resource":"identifications","from":"2026-10-28T00:00:00Z","to":"2026-10-29T00:00:00Z","risk_bands":["dangerous"],"is_vpn":true,"is_proxy":false,"limit":20,"response_format":"json"}
```

For exact accounts use resource user and `ids: ["<User HID>"]`. HRE thresholds are separate from
Risk Score: hre_min_accounts 3–99 and hre_min_devices 4–99. Multiple risk_signals codes use OR;
other filter groups narrow the result. See [all filters](tools.md#history-filters).

If next_page_token is present, send it as page_token with the same resource, window and filters.
Stop when absent/null. Keep the snapshot parameter when used. Displayed data may be truncated;
never treat a bounded page as the full history. Do not drop filters after an input error.

## Manage an integration

1. Read domains and reuse the intended registration. If absent and registration is authorized,
   add_domain takes its hostname and intended allow_subdomains. Domain registration creates no DNS.
2. Read configuration through get_domain. Patch only requested settings. Inspect parent coverage
   before diagnosing a subdomain or creating another registration.
3. List webhooks under domain_id. Implement the authorized HTTPS receiver with the webhooks skill
   and deploy it before creating or testing the subscription. Reuse an existing endpoint.
4. Create with domain_id/name/url and optional multiaccount. Store an authorized one-time secret
   privately; never repeat it. A subscription-only patch preserves endpoint verification.
5. Verify sends a signed ping; test sends a sample. Inspect delivery result, receiver logs and
   readback. For URL changes use confirm=true and repeat verification. Mutations are not retried.
6. Cleanup only test resources created for this run and authorized for deletion. Never rotate or
   delete existing production integrations as routine cleanup.

## Verify a real visit and event

Record hostname, time and installed public key. Open the real page and capture the actual SDK UUID.
Read that same UUID through get_identification with the public domain UUID, then Explain. Match ID,
created_at and score. Use entity cards/relations for linked activity.

For a real scored webhook, match the verified event's identification_id to the visit and verify
HMAC over raw body. For a group event, first create a new test group after an authorized
multiaccount subscription; match hre.multi_account.changed and verify its HMAC. A test/ping or
synthetic group fixture cannot substitute for a real event.

Report each verified stage separately. Handle routine asynchronous setup waits quietly; save exact
endpoint/status/UUID/time privately for persistent failures. Do not infer quota exhaustion or
claim success for a failed UUID because a later different UUID succeeded.

## Debug a delivery

Read get_webhook. Verify/test only on the authorized receiver. Endpoint 4xx/5xx/timeout is a delivery
result, not automatically an MCP failure. Inspect raw-body handling, secret selection and response
latency. Verify locally with the SDK; never request a secret in chat. Read state before retrying a
mutation with an uncertain outcome.
