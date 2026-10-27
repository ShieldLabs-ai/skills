# Hosted MCP tools

Verified against the connected OAuth server on 2026-10-27. Endpoint
`https://mcp.shieldlabs.ai/mcp`; **21 tools**. The client may add a namespace before these names.
Use the client's current tool schema if it changes; never guess an argument.

[Input snapshot](mcp-catalog.json) records names, required fields and types without account data.

## Catalog

| Tool | Arguments (required unless marked) | Purpose |
|---|---|---|
| `shieldlabs_add_domain` | `allow_subdomains` (optional), `domain`, `include_secret` (optional) | Add an existing domain to your ShieldLabs account for installation |
| `shieldlabs_check_connection` | None | Check that this connection to the hosted ShieldLabs server works: ShieldLabs checks the access token the user signed in with |
| `shieldlabs_create_webhook` | `domain_id`, `include_secret` (optional), `name`, `url` | Create a new multi-endpoint webhook with name and public HTTPS URL |
| `shieldlabs_delete_domain` | `confirm`, `domain_id` | Delete an owned domain and its integrations |
| `shieldlabs_delete_webhook` | `confirm`, `domain_id`, `webhook_id` | Delete a webhook endpoint |
| `shieldlabs_disable_webhook` | `confirm`, `domain_id`, `webhook_id` | Disable webhook delivery |
| `shieldlabs_enable_webhook` | `domain_id`, `webhook_id` | Enable webhook delivery |
| `shieldlabs_explain_risk_score` | `domain` (optional), `identification` (optional), `request_id` (optional), `response_format` (optional) | Explain weighted risk signals, flags and the Risk Score using the local catalog |
| `shieldlabs_get_domain` | `domain_id` | Read one owned domain by public UUID |
| `shieldlabs_get_identification` | `domain` (optional), `request_id`, `response_format` (optional), `wait` (optional) | Read one request identification, optionally polling up to 10 seconds for asynchronous scoring |
| `shieldlabs_get_webhook` | `domain_id`, `webhook_id` | Read a webhook on its owned domain, with status, delivery counters and masked secret |
| `shieldlabs_list_domains` | None | List owned domains, including disabled domains |
| `shieldlabs_list_webhooks` | `domain_id` | List the new multi-endpoint webhooks of an owned domain, with status and masked secrets |
| `shieldlabs_patch_domain` | `allow_subdomains` (optional), `confirm` (optional), `domain_id`, `enabled` (optional) | Update enabled and/or allow_subdomains on an owned domain |
| `shieldlabs_patch_webhook` | `confirm` (optional), `domain_id`, `name` (optional), `url` (optional), `webhook_id` | Update webhook name and/or URL; omitted fields are preserved |
| `shieldlabs_rotate_server_key` | `confirm`, `domain_id`, `include_secret` (optional) | Rotate the domain server key |
| `shieldlabs_rotate_webhook_secret` | `confirm`, `domain_id`, `include_secret` (optional), `webhook_id` | Replace the webhook signing secret |
| `shieldlabs_search_history` | `domain` (optional), `limit` (optional), `offset` (optional), `response_format` (optional), `type`, `value` | Read paginated identification history, newest first |
| `shieldlabs_summarize_entity` | `domain` (optional), `max_items` (optional), `response_format` (optional), `type`, `value` | Aggregate a bounded recent history window for a user, device, visitor, IP or cookie |
| `shieldlabs_test_webhook` | `domain_id`, `webhook_id` | Send a signed test delivery; returns delivered, status_code, latency_ms and timed_out |
| `shieldlabs_verify_webhook` | `domain_id`, `webhook_id` | Send a signed verification ping; returns the webhook with resulting verification status |

## Domain selection

`check_connection` and `list_domains` take `{}`. History tools use `domain` as a hostname, such as
`example.com`, without scheme or path. Omit only when exactly one enabled domain exists.
Management uses `domain_id` and `webhook_id` UUIDs returned by list/create calls. An enabled domain,
its `domain_verified` value and its `allow_subdomains` setting are distinct facts.

`add_domain` registers an existing website in ShieldLabs; it does not provision DNS or a website.
`patch_domain` changes only supplied fields. Inspect `allow_subdomains` before diagnosing a
subdomain failure. Do not assume registering a root automatically enables every subdomain.

## Investigation contract

Only `get_identification`, `search_history`, `summarize_entity` and `explain_risk_score` accept
`response_format`, default `markdown`, alternative `json`.

- `get_identification`: `request_id` UUID; `wait` defaults true, polls at most 10 seconds.
  Missing is unverified. It may be necessary to read later after asynchronous scoring.
- `search_history`: `limit` 1–100 (default 20), `offset` nonnegative (default 0). Types are
  `request_id`, `user_hid`, `device_id`, `visitor_id`, `ip`, `session_id`, `cookie_id`.
  Respect `has_more`/`next_offset` and truncation metadata. New rows can move offset pages.
- `summarize_entity`: `max_items` 1–500 (default 100). Types are `user_hid`, `device_id`,
  `visitor_id`, `ip`, `cookie_id`. Report the analyzed window and `window.complete`.
- `explain_risk_score`: exactly one of `request_id` or `identification` (object or JSON string).
  A request lookup uses the selected domain. A pasted input explains that input; it is not proof
  of an account record. History can omit detailed weights and return `signals: []` at a nonzero
  score. Use the returned score and flags; never infer zero risk or manufacture contributions.

ID lookups use UUIDs. IP searches support IPv4 and IPv4-mapped IPv6, not pure IPv6. User HIDs are
exact and case-sensitive; `/`, `.` and `..` are invalid lookup values. Do not double-encode values.
Never reuse a value marked escaped or truncated as an exact lookup identifier.

## Mutation contract

All writes need user intent for that operation. A requested installation can include registering
its domain and configuring its stated receiver; signing in alone does not authorize writes.

- `delete_domain`, `delete_webhook`, `disable_webhook`, `rotate_server_key` and
  `rotate_webhook_secret` require `confirm: true`.
- `patch_domain` also requires it when `enabled: false`; `patch_webhook` requires it when changing
  `url`. A URL change resets verification and may interrupt delivery.
- Rotation invalidates the previous key/secret immediately. `include_secret` is optional only
  on creation/rotation; omitted or false masks the value. Opt in only for an authorized installer
  that must store it privately. Clients can record tool output; never repeat credentials.
- `create_webhook` takes a trimmed name of 1–80 Unicode characters and a public HTTPS `url`
  of at most 512 UTF-8 bytes without embedded credentials. Use the user's authorized receiver.
- `verify_webhook` sends a signed ping and returns the resulting verification state.
  `test_webhook` sends a signed sample event and returns `delivered`, `status_code`, `latency_ms`
  and `timed_out`. A successful tool call can still contain a failed endpoint delivery.
- Enable/disable, rename, verify and test operate on an existing webhook under the specified
  domain. Read state after writes. If a write response is lost, read before trying again;
  mutations are never automatically retried.

## Resources and prompts

Clients that expose MCP resources/prompts can also use the current hosted server's definitions:

| Resource | Contents |
|---|---|
| `shieldlabs://contract/identification` | Normalized MCP identification schema |
| `shieldlabs://contract/webhook-event` | MCP webhook contract schema |
| `shieldlabs://reference/risk-signals` | Current MCP signal/flag/connection catalog |
| `shieldlabs://reference/risk-bands` | Band definitions and rate-limit marker |
| `shieldlabs://domains/{domain}/identifications/{request_id}` | Identification on an explicitly selected domain |

Prompts are `integrate_shieldlabs` (no arguments), `review_request` (`domain`, `request_id`) and
`investigate_user` (`domain`, `user_hid`). They guide the same workflows; they are not extra tools
or a substitute for authorization. These definitions were checked in hosted main on 2026-10-27;
not every client exposes a resource/prompt UI. The 21 tools remain the portable workflow.
The MCP's normalized schema/catalog describes its own response surface; do not assume it includes
all fields of newer application webhook or SDK contracts.

## Older local tools

The hosted catalog replaces the old seven-tool npm setup. It does not expose
`shieldlabs_get_domain_profile`, `shieldlabs_current_time` or `shieldlabs_verify_webhook_signature`.
Use domain reads for current configuration, a trusted clock for freshness, and the application's
server SDK for raw-body signature verification. Do not copy a webhook secret into MCP chat.
