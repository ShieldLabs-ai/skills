# Identifiers and payloads

## Correlate one identification

- Browser SDK: `identificationId`.
- Server SDK and public payload: `identification_id`.
- MCP argument: `request_id`.

Pass the same UUID through the protected action, server read and MCP lookup. Verify that the
returned identification ID equals the submitted ID. A missing or different ID is unverified.

## Read the result

Use the returned Risk Score, detection flags and observation time. Risk Score bands are
trusted 0-29, suspicious 30-59 and dangerous 60-100. `999` is a rate-limit marker. Missing
fields remain unknown; empty detailed weights do not imply a zero score.

## Correlate webhook deliveries

Verify `X-Shield-Signature` over the original request bytes before parsing. Use the verified
`event_id` as the idempotency key, and `data.identification_id` to join the event to the browser
identification. Treat event IDs as opaque strings, not UUIDs.

Persist deduplication and durable enqueue atomically, then acknowledge promptly. Keep the
verified envelope for asynchronous processing. Repeated delivery of the same event must have
one business effect; two Test requests create two separate events.

A verification ping, sample Test event and real scored visit are separate checks.
For HRE, read the backend's status, reason and confidence separately from the Risk Score;
see [High-Risk Events](../../shieldlabs-account-abuse/references/high-risk-events.md).
