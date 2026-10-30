# Use the backend High-Risk Events first

ShieldLabs returns detector results, separately from Risk Score. Read the verified public
payload (or current MCP projection), keeping `status`, `reason`, `level` and `cluster_id`.
Use the verified public payload for these fields. Keep the detector verdict separate from
application heuristics based on History counts.

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

Every enabled webhook endpoint with a public HTTPS URL receives multi-account group events;
the stored `multiaccount` field does not gate delivery. Create or reuse the authorized receiver
and verify its endpoint state. A URL change resets verification. Do not retry mutations
automatically or claim that a Verify ping or scored Test proves an actual group transition.
Follow the
[webhook consumer](../../shieldlabs-webhooks/references/high-risk-events.md) and test actual
detected/updated/resolved deliveries before claiming live group detection is connected.

The History recipes in the parent skill remain available for an application's additional
requirements, promo eligibility and local evidence joins. Their counts/thresholds are custom
application policy, not substitutes for these backend detector outputs.
