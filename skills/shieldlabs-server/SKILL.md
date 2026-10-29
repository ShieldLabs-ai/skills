---
name: shieldlabs-server
description: Reads ShieldLabs verdicts on the backend with the official server SDKs for Node.js, Python, Go, PHP, Java and .NET. Waits for the identification behind a request ID, claims the request ID once, applies the freshness window and the SDK policy helper, and hands the result to the decision logic. Use when the user asks to verify a ShieldLabs request ID on the server, read the Risk Score for a signup, login or checkout, call identifications.get or the History API, add a ShieldLabs check to an API route, Server Action, controller or form handler, configure SHIELDLABS_API_KEY, or handle ShieldLabs API errors, rate limits and timeouts.
---

# ShieldLabs on the server

Read [current SDK and History contracts](references/current-history.md) for stack routing, public domain UUIDs, filters and availability before adding server reads.

When connecting results to orders, promos or other actions, follow the [business context join](references/business-context.md), including webhook-first arrival and tenant scope.

For field names and delivery correlation, see [identifiers and payloads](references/sdk-contract.md).

The backend half of a ShieldLabs integration. Node.js 1.3.0 supplies domain-scoped reads; other language examples use the same public HTTP entity contract with that stack’s client. The page sends a request ID with the protected
action; the backend reads the verdict for it from the **History API**
(`https://account.shieldlabs.ai`) with the matching SDK or public HTTPS client, then acts on it. Scoring is asynchronous: the
History row appears about 1 to 3 seconds after the browser call and can be refined for up to
about 10 seconds. `identifications.get` waits for it with backoff.

## Workflow

1. Detect the backend language, pick the SDK from the table below and read its reference file.
2. Put the Private API Key (`sec_...`) in `SHIELDLABS_API_KEY` in the server environment. Create
   one client per process and reuse it: clients are safe for concurrent use.
3. In the protected action handler, read the submitted `identificationId`. Node uses `identifications.get(identificationId, { domainId })`; other stacks read the domain-scoped identification card. Require available risk and signals before policy evaluation.
4. Treat every failure as **unverified**: no `identificationId`, a malformed ID (`ValidationError`), no
   identification after the wait, an API or network error. Unverified is never clean.
5. Claim the request ID atomically (first use only), enforce the 5-minute freshness window and apply policy. Use the Node helper on its normalized model or the raw-card checks for other stacks.
6. Act on the result with the policy of the shieldlabs-risk-decisions skill
   ([../shieldlabs-risk-decisions/SKILL.md](../shieldlabs-risk-decisions/SKILL.md)). Log
   `reason`, `band` and the request ID; answer the browser with a generic message.

## Pick the SDK

| Language | Install | Client | Read one verdict | Policy helper | Reference |
|---|---|---|---|---|---|
| Node.js 18+, Bun, Deno, edge runtimes | `npm install @shieldlabs-ai/node@1.3.0` | `new ShieldLabs({ apiKey })` | `await shieldlabs.identifications.get(identificationId, { domainId })` | `evaluateIdentification(identification, options)` | [node.md](references/node.md) |
| Python 3.9+ | `pip install shieldlabs` | public HTTP client | domain-scoped identification card | card policy below | [python.md](references/python.md) |
| Go 1.23+ | `go get github.com/ShieldLabs-ai/shieldlabs-go` | public HTTP client | domain-scoped identification card | card policy below | [go.md](references/go.md) |
| PHP 8.1+ | `composer require shieldlabs/shieldlabs-php` | public HTTP client | domain-scoped identification card | card policy below | [php.md](references/php.md) |
| Java 11+ | Maven `ai.shieldlabs:shieldlabs-java` | public HTTP client | domain-scoped identification card | card policy below | [java.md](references/java.md) |
| .NET 8, .NET Standard 2.0 | `dotnet add package ShieldLabs` | public HTTP client | domain-scoped identification card | card policy below | [dotnet.md](references/dotnet.md) |

Configure the chosen client explicitly from the application's private environment. Never expose
the Private API Key to the browser. For other languages, see [other-languages.md](references/other-languages.md).

## The handler shape

Node.js and Express; the other references show the same flow in their language:

```ts
import express from 'express';
import { ShieldLabs, ShieldLabsError, evaluateIdentification, type Identification } from '@shieldlabs-ai/node';

const shieldlabs = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY! }); // one per process

app.post('/api/signup', express.json(), async (req, res) => {
  const identificationId = typeof req.body?.identificationId === 'string' ? req.body.identificationId : '';

  let identification: Identification | null = null;
  if (identificationId) {
    try {
      identification = await shieldlabs.identifications.get(identificationId, { domainId: process.env.SHIELDLABS_DOMAIN_ID! }); // waits up to 10 s
      if (identification && (!Number.isFinite(identification.risk_score) || identification.raw.domain_id !== process.env.SHIELDLABS_DOMAIN_ID || (identification.raw.signals as { state?: string } | undefined)?.state !== "ok")) identification = null;
      if (identification && identification.identification_id !== identificationId) identification = null; // schema mismatch: unverified
    } catch (error) {
      if (!(error instanceof ShieldLabsError)) throw error;
      console.warn('ShieldLabs lookup failed:', error.name); // the signup stays unverified
    }
  }

  // One identification authorizes one action: claim the request ID before trusting it.
  const firstUse = identification ? await claimRequestId(identification.identification_id) : false;
  const verdict = evaluateIdentification(identification, { isReplay: () => !firstUse });

  if (!verdict.ok) {
    console.info('signup refused', { reason: verdict.reason, band: verdict.band, identificationId });
    return res.status(403).json({ error: 'signup_refused' });
  }
  // Create the account. Store identification.device_id with it for later account-abuse checks.
  return res.status(201).json({ ok: true });
});
```

## How `identifications.get` waits

For Node.js 1.3.0, the polling rules are:

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
- **Errors that do not heal stop at once.** 400, 401, 402 and 403 throw right away. A 401 or 403 means the key must be the **Private API Key** for the domain, not a Public Key or Secret Key. A JSON-object 404 is treated as a missing card and remains eligible for the bounded wait. A non-object or non-JSON 404 throws; check the route/base URL. Preserve a 402 response without guessing its cause.
- The request ID must be a UUID. Anything else fails with a validation error before any request.
- With `wait` off (`NoWait: true` in Go, `noWait()` in Java) it reads once, with the client's
  usual retries. Use that for jobs that look at old identifications, or to read the refined row
  about 10 seconds later.

## The policy helper

The Node SDK helper consumes a normalized Identification after availability checks. For raw entity cards in other stacks, apply equivalent guards using the current wire fields, preserving unknown states. The intended checks are:

| Order | Check | `reason` |
|---|---|---|
| 1 | No identification | `missing` |
| 2 | The replay callback says the request ID was used before | `replayed` |
| 3 | Older than the freshness window (default 5 minutes, by `observed_at`) | `stale` |
| 4 | Risk Score above 100: `999` is a Banned IP marker, never a score | `banned_ip` |
| 5 | The all-zero device ID `00000000-0000-0000-0000-000000000000`: no usable device signals | `no_device_signals` |
| 6 | A flag in the blocked flags (default `browser_automation`, `javascript_disabled`) | `blocked_flag` |
| 7 | A band in the blocked bands (default `dangerous`, 60-100) | `blocked_band` |

The result has `ok`, `reason`, `band` (`trusted` 0-29, `suspicious` 30-59, `dangerous` 60-100, or
`banned_ip`) and `flag` for `blocked_flag`. The defaults are a starting point per action: the
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

The hosts are the same everywhere. For development and staging, inspect parent `allow_subdomains` and use an authorized covered hostname with its keys. Separate registration/keys are an isolation choice. For offline tests,
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
