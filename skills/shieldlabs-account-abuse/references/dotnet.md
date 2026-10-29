# Account-abuse evidence in Dotnet

Start with the [backend High-Risk Events](high-risk-events.md). Preserve each returned status,
reason and Medium/High confidence; unavailable or not_evaluated is not a negative detector verdict.
These events are separate from Risk Score. Multi-accounting is a separate group event;
account sharing, impossible travel and account takeover can accompany identification.scored.

Use the [Dotnet server integration](../../shieldlabs-server/references/dotnet.md) to
read the current public domain-scoped History API. Read a `user` card with the exact server-generated
User HID, or a visitor/device card with its UUID. Request the needed relation and a bounded
relation_limit; use only its returned relation_page_token to continue with the same window.
Do not use retired unscoped SDK searches or rebuild backend HRE results from a sample of rows.

For a separately requested application policy, query your own scoped accounts, bans or redemptions
first, joining stored domain/identification UUIDs to the verified result. Ignore anonymous HID
placeholders and nil device IDs. A shared IP is weak evidence; prefer step-up/review to a block
based on one relationship. A truncated page, missing count or unavailable result remains unknown.

Catch network/API errors at the action boundary and apply the application's unverified path.
No positive result from a sample means no match in that sample, not proof that all activity is clean.
