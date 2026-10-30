# Current SDK and History contracts

Select the SDK from the project's actual language, framework, runtime and lock file. The browser
SDK runs identification; the server reads Risk Score and risk signals using the official public
API. Never install a Node server in a Python, Go, PHP, Java or .NET application just to read History.
For a website without accounts, keep checks anonymous. For an application with accounts, generate
User HIDs on the server with the matching SDK's HMAC helper and pass them after authentication.

## Packages and SDK routing

- Browser JavaScript: `@shieldlabs-ai/js@1.1.0`, including its IIFE build. Use the matching React,
  Next.js, Vue/Nuxt, Angular or Svelte/SvelteKit package and satisfy its peer dependencies.
- Node.js, Bun, Deno and compatible edge server: `@shieldlabs-ai/node@1.3.2`. Use it directly in
  Next.js route handlers/Server Actions, Nuxt server routes and SvelteKit actions for the History
  examples below. Read options include the domain UUID on every call; it is not a constructor option.
- Other backends: use the matching official SDK for User HID and webhook helpers. For History,
  use that SDK's documented domain-scoped entity methods when present, otherwise call the public
  HTTPS routes below using that backend's HTTP client. Preserve the entity response and its states;
  do not pass entity cards into a policy helper that expects a different identification model.

## Domain and credentials

History origin: `https://account.shieldlabs.ai`. Send `Authorization: Bearer <Private API Key>`
from the server only. Resolve the hostname through `GET /api/v1/domains`, Node
`shieldlabs.entities.domains()` or MCP `shieldlabs_list_domains`, then use its public UUID.
The response to the HTTP domain list is `{"domains":[{"id":"<domain UUID>","domain":"example.com"}]}`.
Cache the selected registration; never substitute its hostname or an internal numeric ID.
OAuth authenticates MCP separately and supplies no application credential implicitly.

## Routes and response shapes

| Read | Public route |
|---|---|
| Domain list | `GET /api/v1/domains` |
| Identification or user list | `GET /api/v1/domains/{domain_id}/history/{resource}` (`identifications` or `user`) |
| Entity card | `GET /api/v1/domains/{domain_id}/history/{resource}/{resource_id}` (`identifications`, `user`, `visitor`, `device`, `ip`) |

A card returns `{"data":{...entity...}}`. A list returns `{"data":[...],"next_page_token":null}`
(or an opaque next cursor), with no exact total. Follow the cursor with the same window and filters.
The unscoped `/api/v1/history/{type}/{value}` route is retired. Do not call old `history.search`
or `history.iterate` methods; do not reinterpret an error as an empty history.

UUIDs identify domains, identifications, visitors and devices. A User HID is exact case-sensitive
text. Encode an ID once as a path segment. Reject slash/backslash, control characters, empty IDs,
`.` and `..`. IP cards accept IPv4; normalize IPv4-mapped IPv6, and do not send pure IPv6.
Session and cookie IDs can appear on identification cards; they are not standalone card resources.

## Availability and policy

An entity has `type`, `id`, `domain_id`, `domain`, `risk` and `signals`. Match ID, resource type and
domain before using it. Read risk only when `risk.state === "ok"`; an identification then has
`risk.score` (0–100), `risk.band` and `risk.as_of`. Aggregate user/visitor/device/IP cards may
have a band without a numeric score: do not invent one. Unavailable risk has `band: null`,
`as_of: null` and no score. Counts and other fields may be null or absent.

`signals.state` is independently `ok` or `unavailable`; `items` contains public signal codes.
An unavailable or omitted signal state cannot prove that each flag is false. Detailed weighted
signals can be absent even when Risk Score and signal codes are available. Do not sum weights or
invent an explanation. Preserve `identity_risk`, `device_identity`, `traffic`, High-Risk Events,
unknown fields and nullable states when present. HRE confidence Medium/High is separate from risk.

For a protected action: match the submitted UUID and domain, require available numeric risk and
signal states, enforce a five-minute age limit using `created_at`, atomically claim the UUID once,
compare User HID with the authenticated account when applicable, and apply the application's
band/flag policy. Missing, unavailable, malformed, stale or mismatched data is unverified.
Use `check()` for background checks; call `identify()` only for the protected action.

`banned_ip` is the canonical public Banned IP signal and filter; `999` is its marker, never a score or a
fourth Risk Score band. An HTTP 429 error code remains `rate_limited`; it is a transport outcome.
Do not send `rate_limited` as a History filter. HTTP 402 requires its actual response evidence;
a missing identification is not proof of exhausted volume.

## Flat filters and cards

- Pair RFC3339 `from`/`to` with timezone (inclusive start, exclusive end), or omit both.
- List `limit`: 1–100; use opaque `page_token`, preserving `snapshot` when provided.
- `risk_bands`: trusted/suspicious/dangerous; `risk_signals`: codes combined with OR.
- `hre_min_accounts`: 3–99; `hre_min_devices`: 4–99. These do not change Risk Score.
- `ids`: one exact User HID string, user lists only. `source` and `campaign`: at most eight values combined.
- The 20 boolean filters are `is_vpn`, `is_tor`, `is_proxy`, `is_privacy_relay`,
  `network_check_incomplete`, `check_incomplete`, `is_antidetect`, `is_os_mismatch`,
  `is_os_not_detected`, `is_timezone_mismatch`, `is_js_disabled`, `is_browser_automation`,
  `is_incognito`, `is_search_bot`, `ip_mismatch`, `latency_test`, `device_spoofing`,
  `banned_ip`, `ai_bot`, `ai_browser`. Preserve explicit false.

These are top-level SDK/tool options and ordinary repeated HTTP query parameters for arrays.
No nested `filter`, `chips`, `offset`, `include_total`, `sort` or raw score range is accepted.
Wire signal codes and normalized SDK detection flags have their own names; do not derive a flag
name by stripping `is_`. The [MCP tool reference](../../shieldlabs-investigate/references/tools.md)
contains the corresponding inputs for all 21 tools.

Cards accept `device_id_source` (`legacy` or `fp21_record`). Inspect the returned
related_counts without turning unavailable or missing counts into zero. Use known IDs for
additional card reads and the application's own database for its account/device associations.

## Quiet setup verification

Capture one actual browser UUID. Use `shieldlabs_get_identification` with the public domain UUID
and `wait: true` (up to ten seconds). If pending, make one nonwaiting read of the same UUID within
a total 10–15 second window. Avoid repeated progress messages and another `identify()` call.
At the deadline, report a persistent failure with status, UUID, time and the failed stage. Do not
hide a failed UUID because a later one succeeds. A Test webhook, ping or fixture is not a live visit.
