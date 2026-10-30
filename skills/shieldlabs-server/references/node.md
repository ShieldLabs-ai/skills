# Node.js with `@shieldlabs-ai/node`

Node.js 18 or later, Bun, Deno and edge runtimes with `fetch` and WebCrypto (Cloudflare Workers,
Vercel Edge Functions). No runtime dependencies. Use this package directly in Next.js, Nuxt and SvelteKit server handlers. Browser wrappers remain chosen by the frontend framework.

## Install and create the client

```bash
npm install @shieldlabs-ai/node@1.3.2
```

```ts
// shieldlabs.ts
import { ShieldLabs } from '@shieldlabs-ai/node';

export const shieldlabs = new ShieldLabs({
  apiKey: process.env.SHIELDLABS_API_KEY!, // Private API Key, sec_...
  baseUrl: process.env.SHIELDLABS_API_BASE_URL || undefined, // tests only: a local History API mock
});
```

Options: `apiKey` (required; a key that does not look like `sec_xxxxxxxx-xxxxxxxx-xxxxxxxx` logs a
one-time warning), `baseUrl` (plain `http` only for localhost, 127.0.0.1 and [::1] unless
`allowInsecureHttp: true`), `timeout` (milliseconds per HTTP attempt, default `10000`),
`maxRetries` (default `2`), `fetch` (custom implementation). The SDK never reads environment
variables itself. Offline tests: [testing.md](testing.md).

Resolve the public domain UUID with `await shieldlabs.entities.domains()` or MCP list_domains and configure `SHIELDLABS_DOMAIN_ID` privately. Pass it in every read’s options, never in `new ShieldLabs(...)`.

## Handlers

The Express handler is in the skill ([The handler shape](../SKILL.md#the-handler-shape)); import
`shieldlabs` from the module above and `claimRequestId` from the one below. Register webhook routes
with `express.raw()` before any global `express.json()` (shieldlabs-webhooks skill).

## Claim request IDs

```ts
// used-request-ids.ts: true the first time a request ID is claimed.
import { Pool } from 'pg';

const pool = new Pool();
// CREATE TABLE used_request_ids (request_id uuid PRIMARY KEY, used_at timestamptz NOT NULL DEFAULT now());

export async function claimRequestId(identificationId: string): Promise<boolean> {
  try {
    const result = await pool.query(
      'INSERT INTO used_request_ids (request_id) VALUES ($1) ON CONFLICT DO NOTHING',
      [identificationId],
    );
    return result.rowCount === 1;
  } catch {
    return false; // the store is unreachable: refuse rather than allow
  }
}
```

With Redis (for example ioredis): `(await redis.set('shieldlabs:used:' + identificationId, '1', 'EX', 86400, 'NX')) === 'OK'`.
Delete rows older than a day in a scheduled job.

## `identifications.get` options

```ts
const identification = await shieldlabs.identifications.get(identificationId, { domainId: process.env.SHIELDLABS_DOMAIN_ID!,
  timeout: 5_000, // total budget: the last poll runs 5 s after the call (default 10 000)
  pollInterval: 250, // waits of p, 2p, 4p, 6p, then 8p, each at most max(2 s, p)
  signal: AbortSignal.timeout(6_000), // hard limit, including the last request
});

const latest = await shieldlabs.identifications.get(identificationId, { domainId: process.env.SHIELDLABS_DOMAIN_ID!, wait: false }); // one lookup, usual retries
```

Each poll is one HTTP attempt, and a 429, a 5xx, a connection error or an attempt timeout keeps it
polling. When time runs out and the last poll failed, that error is thrown instead of returning
`null`. 400, 401, 402 and 403 are thrown at once, and so is a 429 whose `Retry-After` (capped at
10 s) is longer than the time left; after any other 429 the next poll waits the longest of the
scheduled wait, 1 s and the capped `Retry-After` (0 when missing), cut short at the deadline. Catch
`ShieldLabsError` and treat it as unverified. A JSON-object 404 is a missing card (null, or another bounded poll when waiting); a non-object or non-JSON 404 throws.

An entity with unavailable risk cannot supply a score; the normalized model may have a nonfinite risk_score. Before the policy helper, require a finite Risk Score and `identification.raw.signals.state === "ok"` (narrow the raw object in TypeScript). Otherwise treat the result as unverified. Use `entities.get` when preserving all availability fields.

## `evaluateIdentification` options

```ts
const verdict = evaluateIdentification(identification, {
  maxAge: 5 * 60_000, // milliseconds, by observed_at
  blockBands: ['dangerous'],
  blockFlags: ['browser_automation', 'javascript_disabled'],
  isReplay: () => !firstUse, // must return a boolean synchronously
  now: Date.now(), // for tests
});
// { ok: false, reason: 'blocked_flag', band: 'dangerous', flag: 'browser_automation' }
```

`riskBand(score)` returns `'trusted' | 'suspicious' | 'dangerous' | 'banned_ip'`,
`isRateLimited(score)` checks the `999` marker, and `NIL_UUID` is the all-zero device ID.

## Errors

Every error extends `ShieldLabsError`: `ValidationError` (bad argument, nothing sent), `ApiError`
with `status`, `body` and `headers`, and its subclasses `BadRequestError` (400),
`AuthenticationError` (401, 403), `QuotaExceededError` (402; inspect its response before diagnosing the cause), `NotFoundError` (404; only `identifications.get` converts a JSON-object 404 to missing), `RateLimitError` (429, `retryAfter`), `ServerError` (5xx); plus
`ConnectionError` and `TimeoutError`. Requests are retried on connection errors, timeouts, 429 and
5xx with exponential backoff (0.5 s base, capped at 8 s). `Retry-After` is followed as sent, capped
at 10 s (`0` or a date in the past retries at once), and a 429 without it waits at least 1 s. The
polls of `identifications.get` are single attempts: its schedule takes the place of these retries.

## Frameworks

- **Fastify, Koa, Hono, NestJS**: the same code in the route handler. Read `identificationId` from the
  parsed JSON body of that route.
- **Nuxt** server routes and **SvelteKit** actions: see the shieldlabs-browser skill references
  `vue-nuxt.md` and `svelte-sveltekit.md`.
- **Edge runtimes**: the same client works. For webhooks use `webhooks.constructEventAsync`, and
  for User HIDs `userHidAsync`.

## Management API

```ts
import { ShieldLabsManagement } from '@shieldlabs-ai/node';

const management = new ShieldLabsManagement({
  secretKey: process.env.SHIELDLABS_SECRET_KEY!,
  domain: process.env.SHIELDLABS_DOMAIN!, // "https://www.Example.com/" is sent as "example.com"
});
const profile = await management.getProfile(); // cache it: about 15 calls per minute per IP
// profile.remaining_identifications is negative when the account is over its included volume
```

## Domain-scoped entity reads

```ts
const domains = await shieldlabs.entities.domains();
const domainId = domains.find((item) => item.domain === "example.com")?.id;
if (!domainId) throw new Error("Select an authorized registered domain");
const page = await shieldlabs.entities.list(domainId, "identifications", {
  limit: 20, risk_bands: ["dangerous"], is_vpn: true, is_proxy: false,
});
if (page.next_page_token) {
  const next = await shieldlabs.entities.list(domainId, "identifications", {
    limit: 20, risk_bands: ["dangerous"], is_vpn: true, is_proxy: false,
    page_token: page.next_page_token,
  });
}
const card = await shieldlabs.entities.get(domainId, "user", accountHid);
// Preserve card.risk.state, card.signals.state, nullable fields and high_risk_events.
```

Use [current History](current-history.md) for resources, flat options and availability.
