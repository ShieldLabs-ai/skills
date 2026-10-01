---
name: shieldlabs-webhooks
description: Receives ShieldLabs webhooks safely. Verifies the X-Shield-Signature HMAC over the raw request body before parsing, turns identification.scored and webhook.ping deliveries into typed events with the server SDKs, deduplicates on data.request_id and answers within one second. Covers Express, Next.js route handlers, NestJS, edge runtimes, FastAPI, Flask, Django, Go net/http, plain PHP, Laravel, Symfony, Spring and ASP.NET Core. Use when the user asks to verify a ShieldLabs webhook, add a ShieldLabs webhook endpoint or receiver, handle identification.scored events, debug an invalid or failing webhook signature, rotate a whsec_ signing secret, or choose between webhooks and the History API.
---

# ShieldLabs webhooks

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
| The latest state, or anything a delivery may have missed | The History API: rows can be refined after the webhook was sent, and the webhook is not sent again |

## Workflow

1. Register the endpoint in the analytics dashboard (https://app.shieldlabs.ai, Integration >
   Webhooks > Add endpoint) with a public HTTPS URL on a route the backend controls. Copy its
   signing secret (`whsec_...`) into `SHIELDLABS_WEBHOOK_SECRET` on the server.
2. Make that route receive the raw body bytes: no JSON body parser before verification.
3. Verify and parse with the SDK's `constructEvent(rawBody, signatureHeader, secrets)`. Answer 401
   on a signature error and 400 on a parse error. Read the secrets once at startup; when none is
   set, log it and answer 500: a missing secret is a configuration error, and a 401 would look
   like a wrong secret.
4. Deduplicate on `data.request_id` with an atomic insert, answer 2xx within one second, and hand
   slow work to a queue.
5. Handle `identification.scored` (its `data` is the same `Identification` model the History API
   returns). Acknowledge `webhook.ping` and unknown event types with 2xx.
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
    // Atomic "first time" check, then enqueue. Both must be fast: the sender waits 1 second.
    if (await claimDelivery(event.data.request_id)) await jobs.enqueue(event.data);
  }
  return res.sendStatus(200); // webhook.ping and unknown event types: acknowledge
});

app.use(express.json()); // global parsers after the webhook route
```

## The signature

- Header: `X-Shield-Signature: sha256=<lowercase hex HMAC-SHA256>`.
- Key: the endpoint signing secret as UTF-8 bytes, **including** its `whsec_` prefix. Never strip
  the prefix, and never hex- or base64-decode the secret.
- Message: the raw request body exactly as received. Parsing and re-serializing the JSON breaks the
  signature (the sender escapes `&` as `\u0026`, and Verify and Test bodies have sorted keys).
- The SDKs compare in constant time, accept upper-case hex in the header, and accept several
  secrets. There is no timestamp, delivery ID or event-type header: the idempotency key is
  `data.request_id`.

## Delivery rules

- One delivery per identification per endpoint, sent when scoring finishes, with a 1-second
  timeout. Today each identification is delivered once; a later release adds retries that resend
  identical bytes. Make the handler idempotent on `data.request_id` now.
- Answer 2xx fast. A handler that takes longer than one second counts as a failed delivery.
- The webhook is a snapshot taken when it was sent. The History row can be refined afterwards and
  the webhook is not sent again: read the History API for the latest state.
- Up to 10 endpoints per domain, each with its own secret; every endpoint gets the same body bytes.
- Never redirect the webhook URL: a 301 or 302 turns the POST into a GET without a body.
- A paused endpoint receives no deliveries.

## Events

| `event_type` | When | Payload |
|---|---|---|
| `identification.scored` | Every scored identification, and the **Test** button | `data`: the `Identification` (`request_id`, `visitor_id`, `device_id`, `user_hid`, `public_ip`, `local_ip`, `connection_type`, `risk_score`, `signals`, `detection_flags`, `traffic_source`, `observed_at`, ...) |
| `webhook.ping` | The **Verify** button | no `data` |
| anything else | Event types added later | acknowledge with 2xx; the SDKs return an "unknown event" instead of throwing |

- A `risk_score` of `999` with the single signal `rate_limited` is the rate-limit marker: the
  visitor IP was blocked for sending too many identifications. It is not a score.
- The Test delivery always carries the same `request_id`, a `null` `user_hid`, 17 of the 19
  detection flags (the SDKs read missing flags as `false`) and second-precision timestamps. A
  handler that deduplicates on `request_id` processes it once.

## Rotate the signing secret

**Rotate secret** in the analytics dashboard replaces the endpoint secret at once: the old one
stops working immediately. Deploy the new secret right after rotating and keep both secrets
configured while the change rolls out (the SDKs accept a list; `createWebhookHandler` and the
examples read `SHIELDLABS_WEBHOOK_SECRET` as a comma-separated list). Deliveries that fail in the
gap are not sent again; the History API still has those identifications.

## Test the receiver

- The endpoint URL must be public HTTPS (no `localhost`, `.local` or private IP addresses). To test
  a local server, expose it through an HTTPS tunnel, register the tunnel URL as a separate
  endpoint, then press Verify and Test.
- In automated tests, sign a body yourself with the test secret and post it to the route:

  ```js
  import { createHmac } from 'node:crypto';

  const body = '{"created_at":"2026-09-30T12:34:56Z","event_type":"webhook.ping","schema_version":"2026-06-01"}';
  const signature = 'sha256=' + createHmac('sha256', 'whsec_test_secret').update(body).digest('hex');
  // POST `body` with the header X-Shield-Signature: signature, and expect 200.
  ```

- The MCP tool `shieldlabs_verify_webhook_signature` (shieldlabs-investigate skill) checks a
  received delivery and names the usual mistake when the signature does not match.

## Pitfalls

- A global JSON body parser in front of the route (Express `express.json()`, NestJS without
  `rawBody`, Spring `@RequestBody` with a DTO, ASP.NET `[FromBody]`, Flask `request.json`).
- CSRF middleware rejecting the POST (Django, Laravel, Rails): exempt the webhook route.
- A hand-written check with `==` instead of a constant-time comparison: use the SDK.
- Passing `SHIELDLABS_WEBHOOK_SECRET` unsplit (two secrets during a rotation become one wrong
  secret), or answering 401 when it is not set: Verify then looks like a wrong secret.
- Slow work (HTTP calls, heavy database writes) before the 2xx.
- Not deduplicating: later releases resend identical bytes.
- Sharing one store between webhook deduplication and the request IDs that authorized actions:
  the webhook would mark a request ID as used before the signup handler claims it. Use a separate
  table or key prefix (for example `shieldlabs:delivered:` next to `shieldlabs:used:`).
- Gating the user's action on the webhook: it races with the user's request.
- Throwing on unknown event types, or on the 17-flag Test delivery.
- Logging whole payloads: `traffic_source.landing_url` can hold query-string personal data. Log
  `request_id`, `risk_score` and the band instead.

## Versions

This skill targets the 1.x SDKs. Before pinning, confirm the current version on the package
registry and at https://docs.shieldlabs.ai.
