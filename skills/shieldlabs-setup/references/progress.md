# Installation progress and resume

Show this map before making changes and refresh it after each verified stage. Derive it from
the repository, configured client and returned evidence; never mark a package installation as
a working integration. On resume inspect existing code/configuration and read current state
before repeating an operation. Keep the user's existing choices and authorization.

| Stage | Evidence needed for verified |
|---|---|
| Account and OAuth MCP | Authenticated `shieldlabs_check_connection`; selected account/domain |
| Domain and environments | Parent domain UUID, `allow_subdomains`, authorized production/staging hostnames, key placement |
| Browser SDK | A real background check or protected-action UUID on a covered HTTPS hostname |
| Stored result | That exact UUID found for the selected domain, Risk Score and observation time |
| Server verification (when selected) | Missing, replayed, stale, rate-limited and current IDs exercise the real action handler |
| User linking (when selected) | Server-derived User HID on a fresh signed-in identification |
| High-Risk Events (when selected) | Backend status/reason/level read; group subscription and receiver tested independently |
| Signed webhooks (when selected) | Valid signature, durable enqueue, Verify ping, Test sample and a real delivery |

Use `verified`, `needs check`, `pending`, `not selected` or `blocked`, with a short evidence
pointer or reason. An absent result is pending/unverified, never clean. A synthetic sample
does not verify production emission. Say which choices remain optional. Do not re-ask for an
already selected stage or repeat key rotation, domain creation or subscription changes on resume.

Inventory hostnames before choosing keys: `example.com`, `www.example.com`, an authorized
`staging.example.com`, and any preview origin actually in scope. With parent coverage enabled,
reuse its keys for covered children. Separate keys can isolate test data when supported and
requested. Do not register every child, assume arbitrary preview hosts are covered, change DNS,
or broaden `allow_subdomains` without the installation scope authorizing it.
