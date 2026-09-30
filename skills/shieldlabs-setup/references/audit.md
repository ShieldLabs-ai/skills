# Audit an existing integration

## Contents

- Run the scan
- Checks
- What a scan cannot see
- Report

## Run the scan

```bash
python3 <shieldlabs-setup skill directory>/scripts/audit_scan.py <project root>
python3 <shieldlabs-setup skill directory>/scripts/audit_scan.py <project root> --json
```

The scan is read-only and offline, masks keys in its output and prints each finding with a check
ID, a file and line, and a fix. It is heuristic: read the code around every finding and drop false
positives before reporting. Without Python, use the search patterns in the table.

## Checks

| ID | Severity | Problem | Search for | Why it matters | Fix |
|---|---|---|---|---|---|
| SL01 | high | A Private API Key or signing secret in the source | `sec_[a-z0-9]{8}-[a-z0-9]{8}-[a-z0-9]{8}`, `whsec_[0-9a-f]{32}` outside test files | Anyone with the repository or the bundle reads your History API or forges webhooks | Environment variable, rotate the key |
| SL02 | high | A server key with a public prefix | `(NEXT_PUBLIC_\|VITE_\|NUXT_PUBLIC_\|PUBLIC_\|REACT_APP_)SHIELDLABS_(API_KEY\|SECRET_KEY\|WEBHOOK_SECRET)` | The build copies it into the JavaScript sent to browsers | Rename it, read it server-side only, rotate it |
| SL03 | high | A server key or the server SDK in client code | `SHIELDLABS_API_KEY`, `@shieldlabs/node` or `@shieldlabs/next/server` in `'use client'` files, `.vue`, `.svelte`, `public/` | Same as SL02; the verdict must be read on the server | Move the read to a route handler or action |
| SL04 | high | A webhook parsed before verification | `express.json()` without `express.raw()`, `request.json()`, `$request->all()`, `[FromBody]`, `@RequestBody` DTOs near `constructEvent` | Parsing and re-serializing changes the bytes, so verification fails or gets skipped | Verify the raw bytes first (shieldlabs-webhooks) |
| SL05 | low | A hand-written signature check | `createHmac`, `hash_hmac`, `hmac.new` next to `X-Shield-Signature`, outside test files | Easy to get the key, the comparison or rotation wrong | The SDK's `constructEvent` |
| SL06 | high | No replay guard | `identifications.get` (or its equivalent) without a replay check in the file or elsewhere in the project | One identification could authorize many actions | Claim each request ID once (shieldlabs-server) |
| SL07 | medium | No freshness guard | the same, without the policy helper or an `observed_at` check in the file, and no policy helper call anywhere in the project | An old request ID could authorize a new action | The SDK policy helper, 5-minute window |
| SL08 | high | "Not found" treated as clean | `risk_score ?? 0`, `risk_score \|\| 0`, `?.risk_score >=`, `?.risk_score ?? 10`, `getattr(..., 'risk_score', 0)`, `if (!identification) return next()` (a fallback to `null` is fine) | A blocked agent or a timeout becomes a free pass | Missing means unverified: step-up, review or refuse |
| SL09 | high | Email, phone or username as User HID | `userId:` with `email`, `phone`, `username` near `identify(` or `useIdentify(` | Personal data leaves your system and the value can change | `userHid` helper on the server (shieldlabs-user-linking) |
| SL10 | medium | Raw account ID as User HID | `userId: user.id`, `userId: session.user.id` | Guessable and not pseudonymous | `userHid` helper on the server |
| SL11 | medium | Identify on render or route change | `identify(` inside `useEffect`, `watch`, `$effect`; router event listeners; `runOnMount: true` in a layout | Burns the call budget, triggers the per-IP limit (`999`), bills every page view | `identify()` in the action's handler |
| SL12 | high | Agent self-hosted, proxied or bundled | a copied `snippet.js`, a static `import` from `cdn.shieldlabs.ai`, rewrites or proxies to it, `scriptUrl` pointing elsewhere | Only the agent served from `https://cdn.shieldlabs.ai` works and stays current | Load it through a browser package |
| SL13 | medium | Webhook not idempotent | a verified event handled without a `request_id` check | A later release resends identical bytes | Atomic insert on `data.request_id` |
| SL14 | medium | CSP without ShieldLabs origins | `script-src` or `connect-src` without `cdn.shieldlabs.ai` or `rest.shieldlabs.ai` | The browser blocks the agent (`load_failed`) or its network check | Add the origins (shieldlabs-browser) |
| SL15 | high | `.env` with keys committed or not ignored | `git ls-files .env*`, `git check-ignore .env` | Keys in the repository | `.gitignore`, rotate |
| SL16 | low | `localStorage.clear()` | `localStorage.clear()` | Clearing the agent's cookie ID raises the browser automation signal | Remove only your own keys |
| SL17 | low | Management API on a request path | `getProfile(` in route handlers | About 15 calls per minute per IP, then a 10-minute block | Cache the profile |
| SL18 | medium | Request ID cached in browser storage | `localStorage.setItem(` with a request ID | Reuse is refused, and stale IDs fail the freshness check | One identification per action |

SL01 and SL05 skip test files and folders (`test/`, `tests/`, `__tests__/`, `spec/`, `e2e/`,
`testdata/`, `fixtures/`, `*.test.*`, `*_test.*`, `*.spec.*`, `*_spec.*`): tests use key-shaped
fakes and sign deliveries themselves to exercise the webhook receiver.

## What a scan cannot see

Check these by reading the code and the deployed app:

- **Every protected action gets its own identification**, sent in the same request as the action,
  and the backend handler of each one reads and checks it. SL06 and SL07 accept guards anywhere in
  the project, so a handler that skips them next to one that runs them is only found by reading.
- **The policy matches each action**: missing, `999` and all-zero device IDs lead to step-up or
  review; the dangerous band and automation flags are handled; signed-in actions check
  `user_hid` against the session user (shieldlabs-risk-decisions).
- **Webhook handlers answer within one second**, keep their deduplication store separate from the
  request IDs that authorized actions, and do not gate user actions.
- **Consent**: where required, the agent loads only after consent.
- **The deployed Content Security Policy** (response headers, not only config files) allows the
  ShieldLabs origins; the browser console shows no CSP errors.
- **Testing happens on a registered domain**, not on `localhost`.
- **Logs** record request IDs, reasons and bands, not raw personal data or full webhook bodies.
- **History iteration is bounded** (`maxItems`) on request paths, and results are cached.
- **Keys are per environment**: development and staging use their own registered domain and keys.

## Report

```text
ShieldLabs integration audit: <project>

High
1. [SL06] No replay guard: api/signup.ts:42
   Why: one identification could authorize several signups.
   Fix: claim the request ID with an insert on a unique key and pass the result to isReplay.

Medium
...

Low
...

Checked by hand: <what you verified from the list above, and what you could not verify>
Next step: <offer to fix the findings, starting with High>
```
