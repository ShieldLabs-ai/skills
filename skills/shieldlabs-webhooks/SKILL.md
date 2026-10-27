---
name: shieldlabs-webhooks
description: Receives ShieldLabs webhooks safely. Verifies the X-Shield-Signature HMAC over the raw request body before parsing, turns identification.scored and webhook.ping deliveries into typed events with the server SDKs, deduplicates on the verified event_id and answers within one second. Covers Express, Next.js route handlers, NestJS, edge runtimes, FastAPI, Flask, Django, Go net/http, plain PHP, Laravel, Symfony, Spring and ASP.NET Core. Use when the user asks to verify a ShieldLabs webhook, add a ShieldLabs webhook endpoint or receiver, handle identification.scored events, debug an invalid or failing webhook signature, rotate a whsec_ signing secret, or choose between webhooks and the History API.
---

# ShieldLabs webhooks

Before application integration, [check the installed SDK contract](../shieldlabs-server/references/sdk-contract.md).
Published SDKs can lag the current wire schema: an empty normalized identification ID is
unverified, never a valid key for replay protection or webhook deduplication. MCP uses its own
OAuth adapter; a successful MCP read does not validate an application SDK.


ShieldLabs posts a signed `identification.scored` event to each enabled endpoint when it finishes
scoring an identification: usually a few seconds after the browser call, and at most about 10
seconds after the identification arrives when follow-up network checks run. Webhooks are optional. The History API read at the protected action
(shieldlabs-server skill, [../shieldlabs-server/SKILL.md](../shieldlabs-server/SKILL.md)) is the
dependable read.

## When a webhook fits

| Need | Use |
|---|---|
| Decide on the action that carries the request ID (signup, login, checkout, payout) | `identifications.get` at the action, not the webhook |
| React asynchronously: store `device_id` and `user_hid` per account, alert on the dangerous band, flag accounts for review, feed analytics | The webhook |
| The latest state, or anything a delivery may have missed | The History API: rows can be refined after the webhook was sent, so a delivery is not a live view of the row |

## Configure through OAuth MCP

The [MCP skill](../shieldlabs-investigate/SKILL.md) covers listing, creation, patches, enable/disable,
rotation, verification, tests and deletion. Reuse the selected domain UUID and existing endpoint.
Use only the authorized receiver URL; verification and testing send requests to it. Leave secrets
masked unless installing a needed credential privately. Verify a ping, test the scored-event branch,
then match a real visit's identification UUID separately. Changing a URL resets verification;
rotating a secret invalidates the old one immediately. Do not automatically retry mutations.

## Workflow

1. Register the endpoint in the analytics dashboard (https://app.shieldlabs.ai, Integration >
   Webhooks > Add endpoint) with a public HTTPS URL on a route the backend controls. Copy its
   signing secret (`whsec_...`) into `SHIELDLABS_WEBHOOK_SECRET` on the server.
2. Make that route receive the raw body bytes: no JSON body parser before verification.
3. Verify and parse with the SDK's `constructEvent(rawBody, signatureHeader, secrets)`. Answer 401
   on a signature error and 400 on a parse error. Read the secrets once at startup; when none is
   set, log it and answer 500: a missing secret is a configuration error, and a 401 would look
   like a wrong secret.
4. Deduplicate by the verified envelope `event_id` and durably enqueue the complete raw envelope
   in one atomic operation; answer 2xx promptly, preferably within one second. Never mark an event
   processed before its job is durable. Use `data.identification_id` to correlate the visit.
5. Handle `identification.scored` (parse its `data` with the installed SDK; History may omit detailed signal weights). Acknowledge `webhook.ping` and unknown event types with 2xx.
6. In the analytics dashboard press **Verify** (sends `webhook.ping`) and **Test** (sends a sample
   `identification.scored`), then check the server logs.

## SDK entry points

| Stack | Verify and parse | Reference |
|---|---|---|
| Node.js (Express, NestJS, `node:http`) | `webhooks.constructEvent(body, header, secret)` | [node.md](references/node.md) |
| Edge runtimes (Workers, Vercel Edge, Deno) | `await webhooks.constructEventAsync(body, header, secret)` | [node.md](references/node.md) |
| Next.js route handler | `createWebhookHandler({ onEvent })` from `@shieldlabs-ai/next/server` | [node.md](references/node.md) |
| Python (FastAPI, Flask, Django) | `webhooks.construct_event(payload, header, secret)` | [python.md](references/python.md) |
| Go (`net/http`) | `webhook.ConstructEvent(body, header, secrets...)` | [go.md](references/go.md) |
| PHP (plain, Laravel, Symfony) | `Webhook::constructEvent($payload, $header, $secret)` | [php.md](references/php.md) |
| Java (Spring, `com.sun.net.httpserver`) | `Webhooks.constructEvent(rawBody, header, secrets...)` | [java.md](references/java.md) |
| .NET (ASP.NET Core) | `WebhookEvents.ConstructEvent(body, header, secrets)` | [dotnet.md](references/dotnet.md) |

Every SDK also has a boolean `verifySignature` (`verify_signature`, `VerifySignature`,
`WebhookSignature.Verify`) and accepts one secret or a list.

## The receiver shape

```js
import express from 'express';
import { SignatureVerificationError, webhooks } from '@shieldlabs-ai/node';

const app = express();

// Several secrets, comma-separated, while you rotate one.
const secrets = (process.env.SHIELDLABS_WEBHOOK_SECRET ?? '').split(',').map((s) => s.trim()).filter(Boolean);
if (secrets.length === 0) console.error('SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500');

// express.raw keeps the exact bytes. Register this route before any global express.json().
app.post('/webhooks/shieldlabs', express.raw({ type: 'application/json', limit: '1mb' }), async (req, res) => {
  if (secrets.length === 0) return res.sendStatus(500);
  let event;
  try {
    event = webhooks.constructEvent(req.body, req.get('x-shield-signature'), secrets);
  } catch (error) {
    return res.sendStatus(error instanceof SignatureVerificationError ? 401 : 400);
  }

  if (event.event_type === 'identification.scored') {
    const eventId = event.raw.event_id;
    if (typeof eventId !== 'string' || eventId.length === 0) return res.sendStatus(400);
    // Application-provided atomic dedup + durable enqueue; rejects/rolls back on storage failure.
    await jobs.enqueueOnce(eventId, event.raw);
  }
  return res.sendStatus(200); // webhook.ping and unknown event types: acknowledge
});

app.use(express.json()); // global parsers after the webhook route
```

Treat `event_id` as an opaque, nonempty string. Production Core can send a 40-character hex
ID, while Test can send a UUID. Do not impose a UUID regex on the event key. The
`data.identification_id` used to correlate a visit is a separate UUID.

## The signature

- Header: `X-Shield-Signature: sha256=<lowercase hex HMAC-SHA256>`.
- Key: the endpoint signing secret as UTF-8 bytes, **including** its `whsec_` prefix. Never strip
  the prefix, and never hex- or base64-decode the secret.
- Message: the raw request body exactly as received. Parsing and re-serializing the JSON breaks the
  signature (the sender escapes `&` as `\u0026`, and Verify and Test bodies have sorted keys).
- The SDKs compare in constant time, accept upper-case hex in the header, and accept several
  secrets. The signature check does not require a timestamp header. Current deliveries carry
  `event_id` in the signed body; Core may also send `X-Shield-Event-Id`. Use the body ID for
  delivery deduplication, after verifying the original bytes.

## Delivery rules

- Delivery is not an exactly-once guarantee. Keep retries idempotent on `event_id`; preserve the
  whole envelope and schema version in the durable job. Profiles and timeout budgets can differ.
- Answer 2xx promptly, preferably within one second, after durable acceptance. Portal Verify/Test
  probes have a five-second budget; this is not a reason to block the receiver for five seconds.
- The webhook is a snapshot taken when it was sent. The History row can be refined afterwards and
  a delivery is a snapshot, not a live row: read the History API for the latest state.
- Up to 10 endpoints per domain, each with its own secret; every endpoint gets the same body bytes.
- Never redirect the webhook URL: a 301 or 302 turns the POST into a GET without a body.
- A paused endpoint receives no deliveries.

## Events

| `event_type` | When | Payload |
|---|---|---|
| `identification.scored` | Every scored identification, and the **Test** button | Verified raw `data` uses `identification_id`, identifiers, score, flags and optional current fields. Older typed SDKs may expose a smaller model; keep the raw envelope |
| `webhook.ping` | The **Verify** button | no `data` |
| anything else | Event types added later | acknowledge with 2xx; the SDKs return an "unknown event" instead of throwing |

- A `risk_score` of `999` with the single signal `rate_limited` is the rate-limit marker: the
  visitor IP was blocked for sending too many identifications. It is not a score.
- Current Test uses a fixed synthetic `data.identification_id` but a fresh `event_id` on every
  click. Process two Test clicks as two events; replaying the same signed event has one effect.
  Preserve fields absent from an old typed SDK by using its verified `raw` envelope.

## Rotate the signing secret

**Rotate secret** in the analytics dashboard replaces the endpoint secret at once: the old one
stops working immediately. Deploy the new secret right after rotating and keep both secrets
configured while the change rolls out (the SDKs accept a list; `createWebhookHandler` and the
examples read `SHIELDLABS_WEBHOOK_SECRET` as a comma-separated list). Do not assume that retries bridge the
gap; the History API remains available for reconciliation.

## Test the receiver

- The endpoint URL must be public HTTPS (no `localhost`, `.local` or private IP addresses). To test
  a local server, expose it through an HTTPS tunnel, register the tunnel URL as a separate
  endpoint, then press Verify and Test.
- In automated tests, sign a body yourself with the test secret and post it to the route:

  ```js
  import { createHmac } from 'node:crypto';

  const body = JSON.stringify({ event_id: "6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a", created_at: "2026-10-28T00:00:00Z", event_type: "webhook.ping", schema_version: "2026-10-13", site_id: 7 });
  const signature = 'sha256=' + createHmac('sha256', 'whsec_test_secret').update(body).digest('hex');
  // POST `body` with the header X-Shield-Signature: signature, and expect 200.
  ```

- Signature verification runs locally with the receiver SDK. OAuth MCP provides
  `shieldlabs_verify_webhook` (a ping) and `shieldlabs_test_webhook` (a sample delivery); neither
  is an offline verifier of a pasted body.

## Pitfalls

- A global JSON body parser in front of the route (Express `express.json()`, NestJS without
  `rawBody`, Spring `@RequestBody` with a DTO, ASP.NET `[FromBody]`, Flask `request.json`).
- CSRF middleware rejecting the POST (Django, Laravel, Rails): exempt the webhook route.
- A hand-written check with `==` instead of a constant-time comparison: use the SDK.
- Passing `SHIELDLABS_WEBHOOK_SECRET` unsplit (two secrets during a rotation become one wrong
  secret), or answering 401 when it is not set: Verify then looks like a wrong secret.
- Slow work (HTTP calls, heavy database writes) before the 2xx.
- Treating delivery as exactly once, or using the identification UUID as the current event ID.
- Sharing one store between webhook deduplication and the request IDs that authorized actions:
  the webhook would mark a request ID as used before the signup handler claims it. Use a separate
  table or key prefix (for example `shieldlabs:delivered:` next to `shieldlabs:used:`).
- Gating the user's action on the webhook: it races with the user's request.
- Throwing on unknown event types, or silently discarding newer fields from a verified payload.
- Logging whole payloads: `traffic_source.landing_url` can hold query-string personal data. Log
  `request_id`, `risk_score` and the band instead.

## Versions

This skill targets the 1.x SDKs. Before pinning, confirm the current version on the package
registry and at https://docs.shieldlabs.ai.
