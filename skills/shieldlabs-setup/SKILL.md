---
name: shieldlabs-setup
description: Plans and implements a complete ShieldLabs integration in the current project, or audits an existing one. Detects the stack from package.json, pyproject.toml or requirements.txt, go.mod, composer.json, pom.xml or build.gradle and .csproj files, plans the browser identification, the server-side verdict and the webhook, sets up environment variables without hardcoding keys, walks through the other ShieldLabs skills step by step and ends with a verification checklist. Use when the user asks to connect ShieldLabs MCP with OAuth, configure a domain or webhook, says add ShieldLabs to this app, integrate ShieldLabs, set up ShieldLabs fraud detection or device intelligence, protect signup, login, checkout or payouts with ShieldLabs, runs /shieldlabs:setup, or asks to review, audit or fix an existing ShieldLabs integration (/shieldlabs:audit).
---

# Set up ShieldLabs

Read [current SDK and History contracts](../shieldlabs-server/references/current-history.md) for stack routing, public domain UUIDs, filters and availability before adding server reads.

Start by showing the [progress and resume map](references/progress.md). Keep it current after each verified stage.

ShieldLabs adds identification, risk signals and Risk Score to your website or application: "Detect risky users. Stop abuse of your product."
This skill is the entry point. It plans the integration and hands each step to a focused skill:
shieldlabs-browser, shieldlabs-server, shieldlabs-webhooks, shieldlabs-risk-decisions,
shieldlabs-user-linking, shieldlabs-account-abuse and shieldlabs-investigate. If those skills are
not installed, the short versions in this file are enough to finish; the full set is at
https://github.com/ShieldLabs-ai/skills.

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

## Guided checkpoints

Use questions between major stages, not before every file edit or package install. Reuse the
user's choices and approvals. If several stages are already requested, complete those without
asking again. Audit mode reports findings first and follows the authorized fix scope.

- If no authenticated connection exists, start one OAuth flow in the user’s normal browser. The ShieldLabs page handles login or signup, followed by consent; already signed-in users continue to consent. Do not ask a separate account-status question or start concurrent flows.
- Show the detected stack, domain, existing action and proposed changes. Ask for confirmation
  only if the scope has not already been approved. An explicit installation request authorizes
  the necessary changes; an existing integration needs agreement on the proposed changes.
- For a general install request, complete browser identification and verify its first stored
  result before offering additional stages. Server checks, webhooks and user linking run now
  only when already requested or selected. The numbered workflow below supplies implementation
  details; it is not a requirement to run every optional stage.
- After each verified stage, ask **"What would you like to set up next?"** Offer only applicable,
  unfinished choices: server-side verification; signed webhooks; signed-in user linking and
  account-abuse checks; finish for now. Do not ask again for a next stage already selected.
- For a backend in another repository, ask its path. For a webhook, ask for its authorized HTTPS
  receiver if unknown. Do not add a backend or invent a user/account action without a request.
- Run the selected stage, verify it, then offer what remains. If verification fails, explain and
  resolve that stage before advancing. If the user chooses finish, stop and report both verified
  stages and what remains unconfigured. Browser-only identification does not prove server-side
  protection. Credential rotation and destructive changes retain their explicit approval rules.

## Choose one account setup path

Use **OAuth MCP by default**. Use the **ShieldLabs dashboard** only when the user chooses it or
the client does not support OAuth MCP. Do one path, then install the SDKs. While OAuth approval is pending, wait;
do not start a second flow or switch to the dashboard path.

### OAuth MCP

Use [shieldlabs-investigate](../shieldlabs-investigate/SKILL.md) and its [client setup](../shieldlabs-investigate/references/clients.md).
Open the fresh OAuth flow in the user’s normal browser. They sign in or create a ShieldLabs account, then approve access. Already signed-in users proceed to consent. Wait for completion. If signup happens separately, return
to the same pending flow in that browser or create a fresh flow if it expired.
If tools are absent after OAuth, save the setup checkpoint, ask the user to restart the detected client, return to this same chat and continue. Recheck tool discovery; reuse completed steps. Never invent a Restart button or a platform-specific shortcut.
Run `shieldlabs_check_connection` and `shieldlabs_list_domains`; select the requested domain.
Reuse configured keys. If absent, create only the authorized domain with `shieldlabs_add_domain`.
Opt into `include_secret=true` only when installing a needed server credential; save it privately
([environment.md](references/environment.md)). An existing server key is masked: ask for secure
configuration or explicit rotation approval, never rotate automatically.

Use the returned public domain UUID for both History and domain management. Inspect `allow_subdomains`
before using a subdomain; registering a domain does not create DNS or deploy the application.
Pause SDK installation and integration code edits until this connection step is complete. OAuth authenticates MCP; the app's SDK still uses its domain keys. Never extract OAuth tokens or
call private dashboard APIs. The MCP client may retain one-time credential responses.

### ShieldLabs dashboard

Guide the user to https://app.shieldlabs.ai to add or select the intended domain and configure
its keys locally. Never request private keys in chat. Continue with SDK installation without
requiring MCP; verify through the backend and dashboard instead.

Pass the browser's `identificationId` to the backend and use `identification_id` in the server
SDK. MCP accepts the same UUID as `identification_id`.

## Setup workflow

1. **Detect the stack.** Run `python3 <this skill's directory>/scripts/detect_stack.py <project root>`
   ([detect_stack.py](scripts/detect_stack.py)) when Python is available; otherwise read the
   manifests with the table below ([stack-detection.md](references/stack-detection.md) has the
   details, monorepos and existing ShieldLabs code).
2. **Inspect existing integration and select the action.** Preserve working setup. Ask before
   replacing an existing integration. Use the actions the user requested, or a relevant existing
   action for a basic install; do not invent signup, billing or account flows.
3. **State the plan and choose one setup path above.** A request to install authorizes the
   necessary project changes; proceed within that scope. Clarify genuinely missing decisions,
   and obtain approval before destructive changes or credential rotation.
4. **Keys and environment.** Configure through the chosen path. Add variable placeholders to
   `.env.example`, keep `.env` out of git and never hardcode keys ([environment.md](references/environment.md)).
5. **Browser.** Install the matching browser package and set it up once. Use `check()` or `checkOnLoad` for background identification. For each existing protected action, call `identify()` in its handler and send `identificationId` with that action
   (shieldlabs-browser, [../shieldlabs-browser/SKILL.md](../shieldlabs-browser/SKILL.md)).
6. **Server, when selected.** Create one client per process, read the verdict in each action's handler, claim the
   request ID once, run the policy helper and map the result to an action
   (shieldlabs-server, [../shieldlabs-server/SKILL.md](../shieldlabs-server/SKILL.md), and
   shieldlabs-risk-decisions, [../shieldlabs-risk-decisions/SKILL.md](../shieldlabs-risk-decisions/SKILL.md)).
7. **Signed-in users, when selected.** Compute a User HID on the server and pass it to the browser SDK
   (shieldlabs-user-linking, [../shieldlabs-user-linking/SKILL.md](../shieldlabs-user-linking/SKILL.md)).
   When account-abuse protection is requested, add the relevant account-level checks
   (shieldlabs-account-abuse, [../shieldlabs-account-abuse/SKILL.md](../shieldlabs-account-abuse/SKILL.md)).
8. **Webhook** (optional): only for asynchronous work such as storing device IDs per account or
   alerts (shieldlabs-webhooks, [../shieldlabs-webhooks/SKILL.md](../shieldlabs-webhooks/SKILL.md)).
9. **Verify the first result.** Match the browser UUID to its stored identification and Risk Score
   through MCP (`wait=true`) or the dashboard, and to the backend result when present. Run the
   applicable checklist below ([verification.md](references/verification.md)). Webhooks and
   additional account checks are optional and do not block verified browser identification.
   After a selected stage passes, return to the guided checkpoint above.

If the app has no backend, install browser identification and verify through MCP or the dashboard.
Do not create a backend unless requested, expose private keys in the frontend or claim a browser-only
integration enforces server-side decisions. Mark server verification as not configured.

## Detect the stack

| Manifest | Look for | Browser package | Server SDK |
|---|---|---|---|
| `package.json` | `next` | `@shieldlabs-ai/next` (with `@shieldlabs-ai/react`, `@shieldlabs-ai/js@1.1.0`, `@shieldlabs-ai/node`) | `@shieldlabs-ai/node@1.3.2` |
| `package.json` | `nuxt` | `@shieldlabs-ai/vue` | `@shieldlabs-ai/node` in server routes |
| `package.json` | `@sveltejs/kit` | `@shieldlabs-ai/svelte` | `@shieldlabs-ai/node` in actions and endpoints |
| `package.json` | `@angular/core`, `svelte`, `vue`, `react` | `@shieldlabs-ai/angular`, `@shieldlabs-ai/svelte`, `@shieldlabs-ai/vue`, `@shieldlabs-ai/react` (each with `@shieldlabs-ai/js@1.1.0`) | the backend's SDK |
| `package.json` | `express`, `fastify`, `koa`, `hono`, `@nestjs/core` | | `@shieldlabs-ai/node` |
| no framework, or server-rendered pages | | `@shieldlabs-ai/js@1.1.0` (npm, or its IIFE build) | the backend's SDK |
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
| `SHIELDLABS_DOMAIN_ID` | Server only | Public domain UUID returned by MCP list_domains or SDK entities.domains() |
| `SHIELDLABS_WEBHOOK_SECRET` | Server only | Endpoint signing secret, `whsec_...` (Integration > Webhooks) |
| `USER_HID_SECRET` | Server only | Your own random secret: `openssl rand -hex 32` |
| `SHIELDLABS_SECRET_KEY`, `SHIELDLABS_DOMAIN` | Server only, optional | Management API (domain profile) |

Never hardcode keys or commit `.env`. Only the Public Key may carry a public prefix. Resolve `SHIELDLABS_DOMAIN_ID` from the authorized domain list. Inspect `allow_subdomains` before using staging; a separate registration is an isolation choice.

## The minimum integration

When the focused skills are not available, this is the core for a React frontend and a Node.js
backend; other stacks follow the same shape with their SDK.

```tsx
// Browser: npm install @shieldlabs-ai/react @shieldlabs-ai/js@1.1.0
// Once at the root: <ShieldLabsProvider publicKey={import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY}>
import type { SyntheticEvent } from 'react';
import { useIdentify } from '@shieldlabs-ai/react';

export function SignupForm() {
  const { identify } = useIdentify();
  async function onSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = new FormData(event.currentTarget).get('email');
    const result = await identify(); // never rejects: null when there is no identification (unverified)
    await fetch('/api/signup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, identificationId: result?.identificationId ?? null }) });
  }
  return <form onSubmit={onSubmit}>{/* fields */}</form>;
}
```

```ts
// Server: npm install @shieldlabs-ai/node@1.3.2
import { ShieldLabs, ShieldLabsError, evaluateIdentification, type Identification } from '@shieldlabs-ai/node';

const shieldlabs = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY! });

export async function checkSignup(identificationId: string | null) {
  let identification: Identification | null = null;
  if (identificationId) {
    try {
      identification = await shieldlabs.identifications.get(identificationId, { domainId: process.env.SHIELDLABS_DOMAIN_ID! }); // waits until scored
      if (identification && (!Number.isFinite(identification.risk_score) || identification.raw.domain_id !== process.env.SHIELDLABS_DOMAIN_ID || (identification.raw.signals as { state?: string } | undefined)?.state !== "ok")) identification = null;
      if (identification && identification.identification_id !== identificationId) identification = null; // schema mismatch
    } catch (error) {
      if (!(error instanceof ShieldLabsError)) throw error; // unverified, never clean
    }
  }
  // claimRequestId: an insert on a unique key (or Redis SET NX); true on first use only.
  const firstUse = identification ? await claimRequestId(identification.identification_id) : false;
  return evaluateIdentification(identification, { isReplay: () => !firstUse }); // { ok, reason, band }
}
```

For Python, Go, PHP, Java and .NET, select that stack’s official SDK for its documented helpers and use the current public HTTP History contract when needed; see [current History](../shieldlabs-server/references/current-history.md). Do not transpose Node option names into another SDK.

## Rules

- The agent loads only from `https://cdn.shieldlabs.ai` through a ShieldLabs browser package. Never
  self-host, proxy or bundle it.
- One identification per protected action: call `identify()` in the action's handler and send the
  `identificationId` in the same request. Never identify on render or on route changes.
- Only the Public Key reaches the browser. `SHIELDLABS_API_KEY`, `SHIELDLABS_SECRET_KEY`,
  `SHIELDLABS_WEBHOOK_SECRET` and `USER_HID_SECRET` stay on the server, in environment variables.
- The backend reads the verdict with `identifications.get`, claims each request ID once, refuses
  identifications older than 5 minutes and runs the SDK policy helper.
- No identification or unavailable risk means unverified, never clean. `999` is a Banned IP marker, not a score. The
  all-zero device ID means no usable device signals.
- Bands: trusted 0-29, suspicious 30-59, dangerous 60-100. Branch on bands and detection flags;
  never add up signal weights.
- Webhooks: verify `X-Shield-Signature` over the raw body before parsing, deduplicate on
  verified envelope `event_id`, durably enqueue before answering promptly.
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
  per IP, then a 10-minute block. Webhook delivery must be idempotent;
  use the History API for reconciliation.

## Pitfalls

- Replacing a working integration without approval, or describing browser identification alone
  as server-side protection.
- Keys pasted into code, examples or chat instead of environment variables and `.env.example`
  placeholders.
- Identifying in a layout, on page load or on route changes instead of at the protected action.
- Testing on `localhost` and concluding the backend is broken: identifications are recorded only
  on registered domains.
- Deciding in the webhook handler instead of at the action; forgetting to claim request IDs.
- Mixing production and test data without choosing isolation: inspect the parent domain and allow_subdomains before using an authorized staging hostname.

## Verification checklist

Apply server checks only when a backend is in scope. For a browser-only installation, verify the
first UUID and score through the selected path; report server enforcement as not configured.

- [ ] The build passes and no `sec_` or `whsec_` value appears in the frontend output (or, without
  a build step, in the folder the server serves).
- [ ] The app runs on a registered domain over HTTPS (not `localhost`).
- [ ] Triggering a protected action sends a `identificationId`, and the server log shows the verdict it
  read and the decision.
- [ ] The History API returns the row for that request ID (MCP tool
  `shieldlabs_get_identification`, a server SDK one-liner, or `curl`).
- [ ] Reusing the request ID is refused; an action without one takes the unverified path.
- [ ] Webhooks (if any): Verify and Test in the analytics dashboard get a 2xx; two Test clicks are two
  events, while replaying the exact same signed delivery has one business effect.
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
