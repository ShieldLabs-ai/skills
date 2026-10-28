# Join application actions with identifications

Keep order, payment, promo and action context in the application's database. ShieldLabs does
not require an invented SDK `tag` field. At an existing protected action, obtain a fresh
identification UUID and send it with that action to the backend. Authenticate the caller,
validate input and resolve order/promo IDs and permissions on the server.

Store a row with your tenant/site scope, registered domain, identification UUID, internal action
ID, authenticated account reference (or anonymous session), action type and server timestamp.
Use server-resolved order/promo references; browser context is a claim, never authoritative.
In a multi-tenant backend select the correct domain/key from trusted configuration, not a
browser-supplied domain. Do not log raw emails, keys or whole landing URLs.

Apply the server SDK verdict, freshness and atomic request-ID claim before committing the
protected action. Store the decision and result identifiers with the same action. Use a unique
scope+identification key and a transaction/idempotency key so a retried HTTP request cannot
redeem a promo twice. Webhook event deduplication is a separate store/key.

For `identification.scored`, join `data.identification_id` to that scoped action row. The
webhook may arrive before the action record: durably store an unmatched result and reconcile
when either side arrives. Never drop the result, invent an order from the payload, or wait for
a webhook inside the action handler. Keep event/result versions when available so an older
delivery does not overwrite newer state.

`hre.multi_account.changed` has no identification UUID or order. Join its complete membership
by site/domain and User HIDs to your own account mapping. Do not pretend it identifies a
specific transaction. Store group transitions independently of the per-action verdict.

Verify both arrival orders, duplicate action submissions and webhook retries, wrong tenant/domain,
missing identification, unknown order/promo, and a group event without an identification UUID.
