# Use the backend High-Risk Events first

ShieldLabs returns detector results, separately from Risk Score. Read the verified public
payload (or current MCP projection), keeping `status`, `reason`, `level` and `cluster_id`.
If an older SDK lacks these fields, use its verified `raw` data and the current public schema;
do not add an invented SDK method or reconstruct a backend verdict from a History count.

| Delivery | Result |
|---|---|
| `identification.scored.data.hre.account_sharing` | Account sharing |
| `identification.scored.data.hre.account_takeover` | Account takeover |
| `identification.scored.data.hre.impossible_travel` | Impossible travel |
| Separate `hre.multi_account.changed` event | Complete multi-account group transition |

`evaluated` with `medium` or `high` reports the detector confidence. A null level is not a
positive detection. `not_evaluated` (for example `no_history`), `not_applicable`, absent metadata
or an unavailable History projection must remain distinct. Preserve unfamiliar status/reason
strings and report unsupported states without turning them into an allow decision. Do not
confuse an HRE confidence with the trusted/suspicious/dangerous Risk Score bands.

Enable multi-account events only when requested. Through OAuth MCP, pass `multiaccount: true`
to `shieldlabs_create_webhook` or `shieldlabs_patch_webhook` with the existing domain/webhook
UUIDs. Read back the saved subscription. Omission preserves an existing subscription;
`false` opts out of future jobs, without replaying history or cancelling already queued jobs.
A subscription-only patch preserves endpoint verification; a URL change resets it.

The account/Core release profile may disable this capability. Report an explicit unavailable
response and verify saved state; never claim success or retry mutations automatically. Saved
`multiaccount: true`, a Verify ping and a scored Test are three different facts, none proves
that Core emitted a real group transition. Follow the
[webhook consumer](../../shieldlabs-webhooks/references/high-risk-events.md) and test actual
detected/updated/resolved deliveries before claiming live group detection is connected.

The History recipes in the parent skill remain available for an application's additional
requirements, promo eligibility and local evidence joins. Their counts/thresholds are custom
application policy, not substitutes for these backend detector outputs.
