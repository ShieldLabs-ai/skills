---
name: shieldlabs-setup
description: Plans and implements a complete ShieldLabs integration in the current project, or audits an existing one. Detects the stack from package.json, pyproject.toml or requirements.txt, go.mod, composer.json, pom.xml or build.gradle and .csproj files, plans the browser identification, the server-side verdict and the webhook, sets up environment variables without hardcoding keys, walks through the other ShieldLabs skills step by step and ends with a verification checklist. Use when the user says add ShieldLabs to this app, integrate ShieldLabs, set up ShieldLabs fraud detection or device intelligence, protect signup, login, checkout or payouts with ShieldLabs, runs /shieldlabs:setup, or asks to review, audit or fix an existing ShieldLabs integration (/shieldlabs:audit).
---

# Set up ShieldLabs

ShieldLabs identifies visitors and scores risk: "Detect risky users. Stop abuse of your product."
This skill is the entry point. It plans the integration and hands each step to a focused skill:
shieldlabs-browser, shieldlabs-server, shieldlabs-webhooks, shieldlabs-risk-decisions,
shieldlabs-user-linking, shieldlabs-account-abuse and shieldlabs-investigate. If those skills are
not installed, the short versions in this file are enough to finish; the full set is at
https://github.com/ShieldLabs-ai/shieldlabs-skills.

## How it fits

1. **Browser.** The ShieldLabs agent, loaded only from `https://cdn.shieldlabs.ai` by a browser
   SDK, runs an identification when the user performs a protected action and hands the page a
   **request ID**. The browser never sees a Risk Score or a device ID.
2. **Backend.** The page sends the request ID with the action. The backend reads the verdict from
   the History API with a server SDK (`identifications.get`), or receives it in a signed
   `identification.scored` webhook.
3. **Decision.** The backend maps the verdict (Risk Score bands trusted 0-29, suspicious 30-59,
   dangerous 60-100; detection flags; identifiers) to allow, step-up, review or block.

## Pick the mode

- **Setup** (default): follow the workflow below.
- **Audit**: the user asks to review, audit or fix an existing integration, or runs
  `/shieldlabs:audit`. Jump to [Audit mode](#audit-mode).

## Setup workflow

1. **Detect the stack.** Run `python3 <this skill's directory>/scripts/detect_stack.py <project root>`
   ([detect_stack.py](scripts/detect_stack.py)) when Python is available; otherwise read the
   manifests with the table below ([stack-detection.md](references/stack-detection.md) has the
   details, monorepos and existing ShieldLabs code).
2. **List the protected actions** with the user: signup, login, checkout, payout, payment method
   change, password or email change, promo or trial redemption. Give each a sensitivity (low,
   medium, high).
3. **Present the plan** with the template below and wait for the user to confirm it before
   changing files. When the request already names the protected actions and what should happen,
   or nobody can answer (an automated or delegated run), print the plan with the defaults you
   chose for open points and continue.
4. **Keys and environment.** Add the variables to the environment and to `.env.example`, keep
   `.env` out of git, never hardcode a key ([environment.md](references/environment.md)).
5. **Browser.** Install the browser package, set it up once at the app root, and call
   `identify()` in the handler of each protected action, sending the `requestId` with the action
   (shieldlabs-browser, [../shieldlabs-browser/SKILL.md](../shieldlabs-browser/SKILL.md)).
6. **Server.** Create one client per process, read the verdict in each action's handler, claim the
   request ID once, run the policy helper and map the result to an action
   (shieldlabs-server, [../shieldlabs-server/SKILL.md](../shieldlabs-server/SKILL.md), and
   shieldlabs-risk-decisions, [../shieldlabs-risk-decisions/SKILL.md](../shieldlabs-risk-decisions/SKILL.md)).
7. **Signed-in users.** Compute a User HID on the server and pass it to the browser SDK
   (shieldlabs-user-linking, [../shieldlabs-user-linking/SKILL.md](../shieldlabs-user-linking/SKILL.md)).
   For signups, rewards and payouts, add account-level checks
   (shieldlabs-account-abuse, [../shieldlabs-account-abuse/SKILL.md](../shieldlabs-account-abuse/SKILL.md)).
8. **Webhook** (optional): only for asynchronous work such as storing device IDs per account or
   alerts (shieldlabs-webhooks, [../shieldlabs-webhooks/SKILL.md](../shieldlabs-webhooks/SKILL.md)).
9. **Verify** with the checklist below ([verification.md](references/verification.md)).

## Detect the stack

| Manifest | Look for | Browser package | Server SDK |
|---|---|---|---|
| `package.json` | `next` | `@shieldlabs-ai/next` (with `@shieldlabs-ai/react`, `@shieldlabs-ai/js`, `@shieldlabs-ai/node`) | `@shieldlabs-ai/next/server` |
| `package.json` | `nuxt` | `@shieldlabs-ai/vue` | `@shieldlabs-ai/node` in server routes |
| `package.json` | `@sveltejs/kit` | `@shieldlabs-ai/svelte` | `@shieldlabs-ai/node` in actions and endpoints |
| `package.json` | `@angular/core`, `svelte`, `vue`, `react` | `@shieldlabs-ai/angular`, `@shieldlabs-ai/svelte`, `@shieldlabs-ai/vue`, `@shieldlabs-ai/react` (each with `@shieldlabs-ai/js`) | the backend's SDK |
| `package.json` | `express`, `fastify`, `koa`, `hono`, `@nestjs/core` | | `@shieldlabs-ai/node` |
| no framework, or server-rendered pages | | `@shieldlabs-ai/js` (npm, or its IIFE build) | the backend's SDK |
| `pyproject.toml`, `requirements*.txt`, `Pipfile` | `django`, `fastapi`, `flask` | | `shieldlabs` (PyPI) |
| `go.mod` | the module | | `github.com/ShieldLabs-ai/shieldlabs-go` |
| `composer.json` | `laravel/framework`, `symfony/*` | | `shieldlabs/shieldlabs-php` |
| `pom.xml`, `build.gradle(.kts)` | `spring-boot` or any JVM app | | `ai.shieldlabs:shieldlabs-java` |
| `*.csproj` | `Microsoft.NET.Sdk.Web` | | `ShieldLabs` (NuGet) |

## Plan template

```text
ShieldLabs integration plan
Stack: <frontend framework> + <backend language and framework>
Packages: <browser package(s)>; <server SDK>
Protected actions:
- <action> (<low|medium|high>): <component> calls identify() on submit; <route or handler> reads
  the verdict, claims the request ID, applies the policy: <what happens per outcome>
Signed-in users: User HID from <stable account ID>, handed to the page through <session, prop, template>
Account checks: <none | accounts per device at signup | ...>
Webhook: <none | endpoint URL and purpose>
Environment: <variables, files, secret store>
Test domain: <registered development or staging domain>
```

## Keys and environment

| Variable | Where | Value |
|---|---|---|
| `SHIELDLABS_PUBLIC_KEY` with the framework prefix (`VITE_`, `NEXT_PUBLIC_`, `NUXT_PUBLIC_`, `PUBLIC_`) | Browser build | Public Key, from the analytics dashboard (https://app.shieldlabs.ai), Integration > API keys |
| `SHIELDLABS_API_KEY` | Server only | Private API Key, `sec_...` |
| `SHIELDLABS_WEBHOOK_SECRET` | Server only | Endpoint signing secret, `whsec_...` (Integration > Webhooks) |
| `USER_HID_SECRET` | Server only | Your own random secret: `openssl rand -hex 32` |
| `SHIELDLABS_SECRET_KEY`, `SHIELDLABS_DOMAIN` | Server only, optional | Management API (domain profile) |

Never hardcode keys or commit `.env`. Only the Public Key may carry a public prefix. Use a separate
registered domain with its own keys for development and staging.

## The minimum integration

When the focused skills are not available, this is the core for a React frontend and a Node.js
backend; other stacks follow the same shape with their SDK.

```tsx
// Browser: npm install @shieldlabs-ai/react @shieldlabs-ai/js
// Once at the root: <ShieldLabsProvider publicKey={import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY}>
import type { SyntheticEvent } from 'react';
import { useIdentify } from '@shieldlabs-ai/react';

export function SignupForm() {
  const { identify } = useIdentify();
  async function onSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = new FormData(event.currentTarget).get('email');
    const result = await identify(); // never rejects: null when there is no identification (unverified)
    await fetch('/api/signup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, requestId: result?.requestId ?? null }) });
  }
  return <form onSubmit={onSubmit}>{/* fields */}</form>;
}
```

```ts
// Server: npm install @shieldlabs-ai/node
import { ShieldLabs, ShieldLabsError, evaluateIdentification, type Identification } from '@shieldlabs-ai/node';

const shieldlabs = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY! });

export async function checkSignup(requestId: string | null) {
  let identification: Identification | null = null;
  if (requestId) {
    try {
      identification = await shieldlabs.identifications.get(requestId); // waits until scored
    } catch (error) {
      if (!(error instanceof ShieldLabsError)) throw error; // unverified, never clean
    }
  }
  // claimRequestId: an insert on a unique key (or Redis SET NX); true on first use only.
  const firstUse = identification ? await claimRequestId(identification.request_id) : false;
  return evaluateIdentification(identification, { isReplay: () => !firstUse }); // { ok, reason, band }
}
```

The server SDKs for Python (`shieldlabs`), Go, PHP, Java and .NET have the same client, the same
`identifications.get` and the same policy helper.

## Rules

- The agent loads only from `https://cdn.shieldlabs.ai` through a ShieldLabs browser package. Never
  self-host, proxy or bundle it.
- One identification per protected action: call `identify()` in the action's handler and send the
  `requestId` in the same request. Never identify on render or on route changes.
- Only the Public Key reaches the browser. `SHIELDLABS_API_KEY`, `SHIELDLABS_SECRET_KEY`,
  `SHIELDLABS_WEBHOOK_SECRET` and `USER_HID_SECRET` stay on the server, in environment variables.
- The backend reads the verdict with `identifications.get`, claims each request ID once, refuses
  identifications older than 5 minutes and runs the SDK policy helper.
- No identification means unverified, never clean. `999` is a rate-limit marker, not a score. The
  all-zero device ID means no usable device signals.
- Bands: trusted 0-29, suspicious 30-59, dangerous 60-100. Branch on bands and detection flags;
  never add up signal weights.
- Webhooks: verify `X-Shield-Signature` over the raw body before parsing, deduplicate on
  `data.request_id`, answer within one second.
- User HIDs come from the SDK `userHid` helpers on the server, never raw emails or IDs.
- Use only the public SDK APIs, and confirm package versions on the registry and at
  https://docs.shieldlabs.ai.
- The call budget: the ingest allows about 15 requests per minute per visitor IP (one
  identification uses 4 to 5), background checks run at most once per visit every 5 minutes, and
  an identification in a fresh visit can be accompanied by one automatic background check.
- The page must be a secure context, the Content Security Policy must allow the ShieldLabs
  origins, and the agent loads only after consent where consent is required (`autoLoad: false`,
  then `load()`).
- Limits: History API about 15 requests per second per domain; Management API about 15 per minute
  per IP, then a 10-minute block. Each identification is delivered once per endpoint by webhook
  today; the History API is the dependable read.

## Pitfalls

- Changing files in an interactive run before the user confirmed the plan, or planning only the
  browser half: without the server check nothing is protected.
- Keys pasted into code, examples or chat instead of environment variables and `.env.example`
  placeholders.
- Identifying in a layout, on page load or on route changes instead of at the protected action.
- Testing on `localhost` and concluding the backend is broken: identifications are recorded only
  on registered domains.
- Deciding in the webhook handler instead of at the action; forgetting to claim request IDs.
- Using production keys in development instead of a separate registered domain.

## Verification checklist

- [ ] The build passes and no `sec_` or `whsec_` value appears in the frontend output (or, without
  a build step, in the folder the server serves).
- [ ] The app runs on a registered domain over HTTPS (not `localhost`).
- [ ] Triggering a protected action sends a `requestId`, and the server log shows the verdict it
  read and the decision.
- [ ] The History API returns the row for that request ID (MCP tool
  `shieldlabs_get_identification`, a server SDK one-liner, or `curl`).
- [ ] Reusing the request ID is refused; an action without one takes the unverified path.
- [ ] Webhooks (if any): Verify and Test in the analytics dashboard get a 2xx; a repeated Test is
  processed once.
- [ ] The identification appears in the analytics dashboard.

Commands and details: [verification.md](references/verification.md).

## Audit mode

1. Run `python3 <this skill's directory>/scripts/audit_scan.py <project root>`
   ([audit_scan.py](scripts/audit_scan.py)): read-only, offline, keys masked. Without Python, use
   the search patterns in [audit.md](references/audit.md).
2. Confirm every finding by reading the code, and drop false positives.
3. Check by hand what a scan cannot see (listed in [audit.md](references/audit.md)).
4. Report findings by severity with file and line, why each matters and the fix, then offer to fix
   them, starting with the high ones.

| Problem | Severity |
|---|---|
| Secret or private keys reachable from client bundles (a public prefix, client code, committed `.env`) | high |
| A webhook body parsed before its signature is verified | high |
| Request IDs accepted more than once (no replay guard) | high |
| A missing identification or "not found" treated as clean | high |
| Emails, phone numbers or usernames passed as the User HID | high |
| The agent self-hosted, proxied or bundled | high |
| Raw account IDs passed as the User HID | medium |
| Identify on every render or route change | medium |
| No freshness guard | medium |
| A webhook handler without deduplication or slower than one second | medium |
| A Content Security Policy without the ShieldLabs origins | medium |
| The Management API called on request paths | low |

## Versions

This skill targets the 1.x SDKs. Before pinning, confirm the current version on the package
registry (npm, PyPI, pkg.go.dev, Packagist, Maven Central, NuGet) and at
https://docs.shieldlabs.ai.
