---
name: shieldlabs-server
description: Reads ShieldLabs verdicts on the backend with the official server SDKs for Node.js, Python, Go, PHP, Java and .NET. Waits for the identification behind a request ID, claims the request ID once, applies the freshness window and the SDK policy helper, and hands the result to the decision logic. Use when the user asks to verify a ShieldLabs request ID on the server, read the Risk Score for a signup, login or checkout, call identifications.get or the History API, add a ShieldLabs check to an API route, Server Action, controller or form handler, configure SHIELDLABS_API_KEY, or handle ShieldLabs API errors, rate limits and timeouts.
---

# ShieldLabs on the server

Before application integration, [check the installed SDK contract](references/sdk-contract.md).
Published SDKs can lag the current wire schema: an empty normalized identification ID is
unverified, never a valid key for replay protection or webhook deduplication. MCP uses its own
OAuth adapter; a successful MCP read does not validate an application SDK.


The backend half of a ShieldLabs integration. The page sends a request ID with the protected
action; the backend reads the verdict for it from the **History API**
(`https://account.shieldlabs.ai`) with a server SDK, then acts on it. Scoring is asynchronous: the
History row appears about 1 to 3 seconds after the browser call and can be refined for up to
about 10 seconds. `identifications.get` waits for it with backoff.

## Workflow

1. Detect the backend language, pick the SDK from the table below and read its reference file.
2. Put the Private API Key (`sec_...`) in `SHIELDLABS_API_KEY` in the server environment. Create
   one client per process and reuse it: clients are safe for concurrent use.
3. In the handler of each protected action, read `requestId` from the same request and call
   `identifications.get(requestId)` when it is present.
4. Treat every failure as **unverified**: no `requestId`, a malformed ID (`ValidationError`), no
   identification after the wait, an API or network error. Unverified is never clean.
5. Claim the request ID atomically (first use only), then run the SDK policy helper with that
   replay result and the 5-minute freshness window.
6. Act on the result with the policy of the shieldlabs-risk-decisions skill
   ([../shieldlabs-risk-decisions/SKILL.md](../shieldlabs-risk-decisions/SKILL.md)). Log
   `reason`, `band` and the request ID; answer the browser with a generic message.

## Pick the SDK

| Language | Install | Client | Read one verdict | Policy helper | Reference |
|---|---|---|---|---|---|
| Node.js 18+, Bun, Deno, edge runtimes | `npm install @shieldlabs-ai/node` | `new ShieldLabs({ apiKey })` | `await shieldlabs.identifications.get(requestId)` | `evaluateIdentification(identification, options)` | [node.md](references/node.md) |
| Python 3.9+ | `pip install shieldlabs` | `ShieldLabs()` or `AsyncShieldLabs()` | `client.identifications.get(request_id)` | `evaluate_identification(identification, ...)` | [python.md](references/python.md) |
| Go 1.23+ | `go get github.com/ShieldLabs-ai/shieldlabs-go` | `shieldlabs.NewClient(apiKey)` | `client.Identifications.Get(ctx, requestID, nil)` | `shieldlabs.EvaluateIdentification(ident, opts)` | [go.md](references/go.md) |
| PHP 8.1+ | `composer require shieldlabs/shieldlabs-php` | `new ShieldLabs()` | `$shieldlabs->identifications->get($requestId)` | `Risk::evaluate($identification, $options)` | [php.md](references/php.md) |
| Java 11+ | Maven `ai.shieldlabs:shieldlabs-java` | `ShieldLabsClient.fromEnvironment()` | `client.identifications().get(requestId)` | `Risk.evaluate(identification, options)` | [java.md](references/java.md) |
| .NET 8, .NET Standard 2.0 | `dotnet add package ShieldLabs` | `new ShieldLabsClient(options)` | `await client.Identifications.GetAsync(requestId)` | `Risk.Evaluate(identification, options)` | [dotnet.md](references/dotnet.md) |

The Node.js and Go SDKs never read environment variables: pass the key. The Python and PHP clients
read `SHIELDLABS_API_KEY` when no key is passed, Java reads it in `fromEnvironment()`, and .NET
takes it in `ShieldLabsClientOptions`. For other languages, see
[other-languages.md](references/other-languages.md).

## The handler shape

Node.js and Express; the other references show the same flow in their language:

```ts
import express from 'express';
import { ShieldLabs, ShieldLabsError, evaluateIdentification, type Identification } from '@shieldlabs-ai/node';

const shieldlabs = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY! }); // one per process

app.post('/api/signup', express.json(), async (req, res) => {
  const requestId = typeof req.body?.requestId === 'string' ? req.body.requestId : '';

  let identification: Identification | null = null;
  if (requestId) {
    try {
      identification = await shieldlabs.identifications.get(requestId); // waits up to 10 s
      if (identification && identification.request_id !== requestId) identification = null; // schema mismatch: unverified
    } catch (error) {
      if (!(error instanceof ShieldLabsError)) throw error;
      console.warn('ShieldLabs lookup failed:', error.name); // the signup stays unverified
    }
  }

  // One identification authorizes one action: claim the request ID before trusting it.
  const firstUse = identification ? await claimRequestId(identification.request_id) : false;
  const verdict = evaluateIdentification(identification, { isReplay: () => !firstUse });

  if (!verdict.ok) {
    console.info('signup refused', { reason: verdict.reason, band: verdict.band, requestId });
    return res.status(403).json({ error: 'signup_refused' });
  }
  // Create the account. Store identification.device_id with it for later account-abuse checks.
  return res.status(201).json({ ok: true });
});
```

## How `identifications.get` waits

The same rules in every server SDK:

- **Total budget.** `timeout` (10 seconds by default; `waitFor` in Java) is the time budget of the
  whole call, counted from the call and including the time the requests take.
- **Schedule.** The first lookup runs at once. With the poll interval p (default 250 ms) the waits
  are p, 2p, 4p, 6p and then 8p, each capped at max(2 s, p): 250 ms, 500 ms, 1 s, 1.5 s, then
  every 2 s by default, and every 3 s for a poll interval of 3 s. Go raises a poll interval below
  100 ms to 100 ms. A wait that would pass the deadline is cut short, so the last lookup runs at
  the deadline.
- **One attempt per lookup.** Each lookup is a single HTTP request without the client's retries.
  It gets the client timeout, shortened to the time left but never below 1 s, so the call can end
  up to about 1 s after the budget.
- **Transient errors keep polling.** A 429, a 5xx, a connection error or an attempt timeout does
  not end the wait.
- **429.** The next wait is the longest of the scheduled wait, 1 s and `Retry-After` capped at
  10 s (a missing `Retry-After`, `0` or a date in the past counts as 0). When the capped
  `Retry-After` is longer than the time left, that rate-limit error is thrown at once.
- **At the deadline** the error of the last lookup is thrown when it failed; otherwise the result is
  `null` (`None`, `nil`, `Optional.empty()`): no identification in time, which means unverified.
- **Errors that do not heal stop at once.** 400, 401, 403 and 404 throw right away. A 401 or 403
  means the key must be the **Private API Key** of the domain the page runs on, not its Public Key
  or Secret Key; a 404 usually means a wrong base URL.
- The request ID must be a UUID. Anything else fails with a validation error before any request.
- With `wait` off (`NoWait: true` in Go, `noWait()` in Java) it reads once, with the client's
  usual retries. Use that for jobs that look at old identifications, or to read the refined row
  about 10 seconds later.

## The policy helper

Every SDK ships the same guard. The checks run in this order and the first failure wins:

| Order | Check | `reason` |
|---|---|---|
| 1 | No identification | `missing` |
| 2 | The replay callback says the request ID was used before | `replayed` |
| 3 | Older than the freshness window (default 5 minutes, by `observed_at`) | `stale` |
| 4 | Risk Score above 100: `999` is a rate-limit marker, never a score | `rate_limited` |
| 5 | The all-zero device ID `00000000-0000-0000-0000-000000000000`: no usable device signals | `no_device_signals` |
| 6 | A flag in the blocked flags (default `browser_automation`, `javascript_disabled`) | `blocked_flag` |
| 7 | A band in the blocked bands (default `dangerous`, 60-100) | `blocked_band` |

The result has `ok`, `reason`, `band` (`trusted` 0-29, `suspicious` 30-59, `dangerous` 60-100, or
`rate_limited`) and `flag` for `blocked_flag`. The defaults are a starting point per action: the
shieldlabs-risk-decisions skill maps each reason and band to allow, step-up, review or block.
The freshness window is milliseconds in Node.js (`maxAge: 300_000`), seconds or a `timedelta` in
Python and seconds in PHP (`max_age`), a `Duration` in Go and Java, and a `TimeSpan` in .NET.

## Claim each request ID once

One identification authorizes one protected action. The SDKs keep no state, so record each
request ID in your own store with a unique key, and treat "already there" as a replay:

- SQL: `INSERT INTO used_request_ids (request_id) VALUES (?)` on a primary key; a duplicate-key
  error (or `ON CONFLICT DO NOTHING` with 0 rows) means "used before".
- Redis: `SET shieldlabs:used:<request_id> 1 NX EX 86400`; a null reply means "used before".
- Keep entries a little longer than the freshness window (one day is simple); older
  identifications fail as `stale` anyway.
- Claim on first use whatever the outcome, and treat an unreachable store as a replay, so that
  failures refuse rather than allow.
- In Node.js the `isReplay` callback must answer synchronously, and async Python code has the same
  constraint: claim first, then pass `() => !firstUse`. The other SDKs can claim inside the
  callback.

## Bind the identification to the account

For actions by signed-in users, the page passes the User HID to `identify({ userId })`. Compare
`identification.user_hid` with the User HID you compute for the session user (shieldlabs-user-linking
skill). A mismatch means the request ID came from another account's identification or an
anonymous one: treat it as unverified.

## Limits and costs

- History API: about 15 requests per second **per domain**, shared by every caller of that domain
  (your servers and tools such as the MCP server). One lookup per protected action stays far
  inside it. The SDKs retry a 429 after `Retry-After` as sent, capped at 10 s (`0` or a date in the
  past retries at once), and after at least 1 s when it is missing; while `identifications.get`
  waits, the lookup after any 429 comes at least 1 s later.
- History reads and Management API calls do not use your included identifications. Only
  identifications from the browser do.
- Management API (`getProfile`, the remaining included identifications and masked keys): about 15
  requests per minute per caller IP, then that IP is blocked for 10 minutes. The SDKs never retry
  its 429. Call it rarely and cache the result.

## Environments

The hosts are the same everywhere. For development and staging, register a separate domain in the
analytics dashboard (Integration > Domains) and use its keys. For offline tests,
`SHIELDLABS_API_BASE_URL` points the SDK at a local stand-in of the History API: the skill ships
one in [scripts/history_mock.py](scripts/history_mock.py), and [testing.md](references/testing.md) explains it with the
History row format and example rows for every branch of the policy helper.

## Pitfalls

- Treating `null`, a timeout or an error as "no risk". It is unverified.
- Reading the verdict in the browser, or shipping `SHIELDLABS_API_KEY` in a client bundle.
- Creating a client per request, or polling in your own loop without backoff.
- Branching on signal names or adding up signal weights: branch on `risk_score` (through the band)
  and `detection_flags`; weights can be negative.
- Returning `reason`, flags or the score to the browser: log them on the server instead.
- Gating an action on the webhook: the History read at the action is the dependable read. Webhooks
  are for asynchronous work (shieldlabs-webhooks skill).
- Treating only `null` as a failure: at the deadline `identifications.get` throws the error of a
  failed last lookup (for example a 429 or a 5xx) instead of returning `null`. Catch the SDK's base
  error and treat it as unverified too.

## Versions

This skill targets the 1.x SDKs. Before pinning, confirm the current version on the package
registry (npm, PyPI, pkg.go.dev, Packagist, Maven Central, NuGet) and at
https://docs.shieldlabs.ai.
