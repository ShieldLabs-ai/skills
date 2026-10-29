# Current MCP tools

Connect through OAuth at `https://mcp.shieldlabs.ai/mcp`. Start with connection and domain reads.
The [input catalog](mcp-catalog.json) contains the registered schemas for all 21 tools.

## Tool inputs

| Tool | Required | Optional |
|---|---|---|
| `shieldlabs_add_domain` | `domain` | `allow_subdomains`, `include_secret` |
| `shieldlabs_check_connection` | none | none |
| `shieldlabs_create_webhook` | `domain_id`, `name`, `url` | `multiaccount`, `include_secret` |
| `shieldlabs_delete_domain` | `domain_id`, `confirm` | none |
| `shieldlabs_delete_webhook` | `domain_id`, `webhook_id`, `confirm` | none |
| `shieldlabs_disable_webhook` | `domain_id`, `webhook_id`, `confirm` | none |
| `shieldlabs_enable_webhook` | `domain_id`, `webhook_id` | none |
| `shieldlabs_explain_risk_score` | none | `domain`, `identification_id`, `identification`, `response_format` |
| `shieldlabs_get_domain` | `domain_id` | none |
| `shieldlabs_get_history` | `domain`, `resource`, `resource_id` | `response_format`, `from`, `to`, `device_id_source`, `relation`, `relation_limit`, `relation_page_token`, `flat filters (below)` |
| `shieldlabs_get_identification` | `domain`, `identification_id` | `response_format`, `from`, `to`, `wait` |
| `shieldlabs_get_webhook` | `domain_id`, `webhook_id` | none |
| `shieldlabs_list_domains` | none | none |
| `shieldlabs_list_history` | `domain`, `resource` | `response_format`, `from`, `to`, `limit`, `page_token`, `flat filters (below)` |
| `shieldlabs_list_webhooks` | `domain_id` | none |
| `shieldlabs_patch_domain` | `domain_id` | `enabled`, `allow_subdomains`, `confirm` |
| `shieldlabs_patch_webhook` | `domain_id`, `webhook_id` | `name`, `url`, `multiaccount`, `confirm` |
| `shieldlabs_rotate_server_key` | `domain_id`, `confirm` | `include_secret` |
| `shieldlabs_rotate_webhook_secret` | `domain_id`, `webhook_id`, `confirm` | `include_secret` |
| `shieldlabs_test_webhook` | `domain_id`, `webhook_id` | none |
| `shieldlabs_verify_webhook` | `domain_id`, `webhook_id` | none |

History `domain` is the public domain UUID from `shieldlabs_list_domains`, never a hostname.
Management uses `domain_id` and `webhook_id`. Names and IDs are separate values.
Only get_identification, list_history, get_history and explain_risk_score accept
`response_format`, with `markdown` by default and `json` for structured inspection.

## History filters

Lists support resources `identifications` and `user`; cards also support `visitor`, `device` and
`ip`. UUIDs identify identifications/visitors/devices. User HID is exact, case-sensitive text;
IP cards use IPv4 (IPv4-mapped IPv6 is normalized). Pass IDs unencoded; the client handles path
encoding. Do not use `/`, `.` or `..` as a User HID lookup or reuse truncated display values.

- `from` and `to`: send both RFC3339 timestamps with timezone, or neither. Start inclusive,
  end exclusive. Preserve fractional seconds. For a full UTC day use midnight to next midnight.
- `limit`: 1–100, default 20. Continue with the opaque `next_page_token` as `page_token`.
- `snapshot`: preserves the API snapshot when supplied. Keep it with the same query.
- `risk_bands`: an array drawn from `trusted`, `suspicious`, `dangerous`.
- `hre_min_accounts`: 3–99; `hre_min_devices`: 4–99. These are HRE evidence thresholds, not scores.
- `ids`: up to 100 exact User HIDs, user lists only.
- `risk_signals`: public signal codes. Multiple codes combine with OR.
- `source` and `campaign`: arrays, at most 8 values combined. `_empty` selects no referrer;
  `No campaign` selects visits without a campaign.
- Boolean fields: `is_vpn`, `is_tor`, `is_proxy`, `is_privacy_relay`,
  `network_check_incomplete`, `check_incomplete`, `is_antidetect`, `is_os_mismatch`,
  `is_os_not_detected`, `is_timezone_mismatch`, `is_js_disabled`, `is_browser_automation`,
  `is_incognito`, `is_search_bot`, `ip_mismatch`, `latency_test`, `device_spoofing`,
  `banned_ip`, `ai_bot`, `ai_browser`. Preserve explicit JSON false.

Pass filters as top-level tool fields. Different filter groups narrow the selection; repeated
values use the API's documented matching semantics. Keep every constraint when paging.
Offset, nested JSON filter, include_total, sort and raw score_from/score_to are not inputs.
Use risk bands rather than converting marker 999 into dangerous risk. Empty results mean no
matches under this query, not proof of no activity or clean traffic.

Card-only options: `device_id_source` (`legacy` or `fp21_record`), `relation`, `relation_limit`
(1–100), and opaque `relation_page_token`. Relations are visitors, devices, users, public_ips,
sessions, cookies, local_ips, countries, local_countries, browsers, os, device_types,
connection_types, risk_signals and high_risk_events. Identification cards reject relation reads.

## Identification and Explain

Use `identification_id` for the browser's identification UUID. `get_identification` needs the
public domain UUID and can wait up to 10 seconds. Missing remains unverified. The card exposes
`id` and `risk.state`/`risk.score`; preserve unavailable state rather than inventing zero.

Explain takes exactly one of `identification_id` (with domain) or a pasted `identification`.
Weighted signals take priority over score_details. Available score_details can recover missing
weights; an empty list alone never means no contribution. High-Risk Event confidence and
identification Risk Score are separate axes. Preserve optional identity/HRE availability.

## Mutations and receiver verification

Writes require user intent. Destructive operations require confirm=true; disabling a domain or
changing a webhook URL also needs it. Rotation invalidates the previous credential. Read existing
state and reuse resources. A lost response requires readback before another write, never an
automatic mutation retry. Secrets stay masked except authorized one-time installation retrieval.

Webhook create/patch accept `multiaccount`; omission preserves existing settings. Read back after
writes. Verify sends a signed ping. Test reports delivered/status_code/latency_ms/timed_out; check
the endpoint result. Neither proves real identification or hre.multi_account.changed delivery.
Verify real event signatures in the application's receiver with the SDK and raw body.

## Prompts and data

Use current tool schemas as the portable workflow. When the client exposes prompts,
`review_request` uses domain and identification_id; `investigate_user` uses domain and user_hid.
Browser strings remain untrusted data. Respect escaped/truncated fields and unknown availability.
