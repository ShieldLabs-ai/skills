---
name: shieldlabs-browser
description: Adds the ShieldLabs browser SDK to a web frontend so that each protected action (signup, login, checkout, payout, password change) runs one fresh identification and sends its request ID to the backend. Covers @shieldlabs-ai/js for plain JavaScript and pages without a bundler, @shieldlabs-ai/react, @shieldlabs-ai/next, @shieldlabs-ai/vue with Nuxt, @shieldlabs-ai/angular and @shieldlabs-ai/svelte with SvelteKit, plus Content Security Policy, consent, server-side rendering and the call budget. Use when the user asks to install or load the ShieldLabs agent or snippet, get a requestId in the browser, call identify() on a form, add ShieldLabsProvider, provideShieldLabs, createShieldLabs or setShieldLabs, load the agent only after consent (autoLoad, load()), identify early with getAgent(), fix load_failed, timeout, not_initialized or unsupported_environment errors, or wire the ShieldLabs Public Key into a frontend.
---

# ShieldLabs in the browser

Before application integration, [check the installed SDK contract](../shieldlabs-server/references/sdk-contract.md).
Published SDKs can lag the current wire schema: an empty normalized identification ID is
unverified, never a valid key for replay protection or webhook deduplication. MCP uses its own
OAuth adapter; a successful MCP read does not validate an application SDK.


The browser half of a ShieldLabs integration. The ShieldLabs agent runs an identification in the
visitor's browser and hands the page a **request ID**. The page sends that request ID to the
backend in the same request as the protected action. The browser never receives a Risk Score, a
visitor ID or a device ID: the backend reads the verdict (shieldlabs-server skill,
[../shieldlabs-server/SKILL.md](../shieldlabs-server/SKILL.md)).

## Workflow

1. Detect the frontend framework and pick the package from the table below. Read its reference
   file before writing code.
2. Install the package and put the Public Key in the framework's public environment variable.
3. Set the agent up once, at the root of the app (provider, plugin or setup call).
4. At each protected action, call `identify()` in the submit handler and send the `requestId` in
   the same request as the action.
5. When there is no identification (the identify helper resolves `null`, or the agent's
   `identify()` rejects), send the action anyway without a `requestId`. The backend treats it as
   unverified, never as clean.
6. Add the Content Security Policy origins, load the agent only after consent where consent is
   required (`autoLoad: false`, then `load()`), and test on a registered domain over HTTPS.

## Pick the package

| Frontend | Install | Set up once | Identify at the action | Reference |
|---|---|---|---|---|
| Plain JavaScript, any bundler, or a page without a bundler | `@shieldlabs-ai/js` | `load({ publicKey })` | `agent.identify()`, rejects on failure | [vanilla.md](references/vanilla.md) |
| React 18 or 19 (Vite, React Router) | `@shieldlabs-ai/react @shieldlabs-ai/js` | `<ShieldLabsProvider publicKey>` | `useIdentify()`, resolves `null` on failure | [react.md](references/react.md) |
| Next.js 14 or later, App Router or Pages Router | `@shieldlabs-ai/next @shieldlabs-ai/react @shieldlabs-ai/js @shieldlabs-ai/node` | `<ShieldLabsProvider>` from `@shieldlabs-ai/next` in the root layout | `useIdentify()` in a client component, resolves `null` on failure | [nextjs.md](references/nextjs.md) |
| Vue 3.3 or later, Nuxt 3 | `@shieldlabs-ai/vue @shieldlabs-ai/js` | `app.use(createShieldLabs({ publicKey }))` | `useIdentify()`, resolves `null` on failure | [vue-nuxt.md](references/vue-nuxt.md) |
| Angular 17 or later | `@shieldlabs-ai/angular @shieldlabs-ai/js` | `provideShieldLabs({ publicKey })` | `injectIdentify()`, resolves `null` on failure | [angular.md](references/angular.md) |
| Svelte 5, SvelteKit 2 | `@shieldlabs-ai/svelte @shieldlabs-ai/js` | `setShieldLabs({ publicKey })` in the root layout | `useIdentify()`, resolves `null` on failure | [svelte-sveltekit.md](references/svelte-sveltekit.md) |

`@shieldlabs-ai/js` is the shared loader: the framework packages list it as a peer dependency, so
install it next to them. The Public Key is the only ShieldLabs credential that belongs in browser
code. Copy it from the analytics dashboard at https://app.shieldlabs.ai (Integration > API keys;
the Install tab shows a ready snippet with it) and expose it with the framework's public prefix:

| Framework | Variable |
|---|---|
| Vite (React, Vue, Svelte, plain) | `VITE_SHIELDLABS_PUBLIC_KEY` |
| Next.js | `NEXT_PUBLIC_SHIELDLABS_PUBLIC_KEY` |
| Nuxt | `NUXT_PUBLIC_SHIELDLABS_PUBLIC_KEY` through `runtimeConfig.public` |
| SvelteKit | `PUBLIC_SHIELDLABS_PUBLIC_KEY` from `$env/static/public` |
| Angular | an environment file, or `SHIELDLABS_PUBLIC_KEY` through the CLI `define` option |

## The core pattern

Every framework package wraps this `@shieldlabs-ai/js` flow:

```ts
import { load, ShieldLabsError, type LoadOptions } from '@shieldlabs-ai/js';

const options: LoadOptions = { publicKey: import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY };

// Start loading early, but never make the form depend on it: a content blocker or a network
// error must not break signup.
load(options).catch(() => {}); // handled in the submit handler

const form = document.querySelector<HTMLFormElement>('#signup')!;
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  let requestId: string | null = null;
  try {
    // load() again: memoized, it returns the loaded agent at once and retries a failed load.
    const agent = await load(options);
    ({ requestId } = await agent.identify()); // one fresh identification per submission
  } catch (error) {
    if (error instanceof ShieldLabsError) console.warn('ShieldLabs:', error.code);
  }
  // Same request as the protected action. Without a requestId the server treats it as unverified.
  await fetch('/api/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: form.email.value, requestId }),
  });
});
```

`identify()` resolves `{ requestId, userId }`. `userId` is the User HID that was sent, or `null`
for an anonymous identification.

## The framework packages

They load the agent once for the app and give each component an identify helper (`useIdentify()`,
or `injectIdentify()` in Angular) with `result`, `isLoading` and `error` state:

```ts
const result = await identify(); // never rejects: null when there is no identification
await fetch('/api/signup', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, requestId: result?.requestId ?? null }),
});
```

- The helper's `identify(options?)` resolves `{ requestId, userId }` or `null`, and puts the reason
  (a `ShieldLabsError`) in `error`. No `try`/`catch` is needed.
- While an identification of the same helper with the same User HID and the same effective timeout
  runs, `identify()` returns it instead of starting another: a double submit costs one
  identification. A call without `timeout` counts as one with the default timeout.
- `timeout` (from the call, else the provider, plugin or setup `timeout`, 10 000 ms by default)
  bounds the whole call: the wait for the agent to load, then the agent's answer in the time left.
- The state access object (`useShieldLabs()`, `injectShieldLabs()`, `getShieldLabs()`) gives
  `status`, `error`, the low-level `identify()` and `check()`, `load()` and `getAgent()`. Its
  `identify()` rejects with a `ShieldLabsError`, like the agent's. `getAgent()` resolves the agent
  of `@shieldlabs-ai/js`, for example for `agent.identifyOnInteraction(form)`, and rejects with the
  load error when the load fails or times out.
- `autoLoad` (default `true`) loads the agent after the first render. With `autoLoad: false`
  nothing loads until `load()` is called (see [Consent](#consent)).

## Rules

- **The agent comes only from `https://cdn.shieldlabs.ai`.** The npm packages are loaders that
  import the hosted agent at runtime. Never download, self-host, mirror, proxy or bundle the agent
  (`snippet.js`), and never add a static `import` or `<script>` for it next to the SDK.
- **One identification per protected action.** Call `identify()` when the user submits the
  action. Every call is a billable identification with a new request ID, and the backend accepts
  each request ID once, within a freshness window (5 minutes in the examples).
- **Never identify on render, in a layout, or on client-side route changes.** The agent already
  runs its own limited background checks on clicks and navigation.
- **Keep the page alive until your request is sent.** The agent posts the identification right
  after `identify()` resolves. Send the action with `fetch` or the framework's HTTP client. For a
  classic full-page form post, start early with `identifyOnInteraction()` (see
  [vanilla.md](references/vanilla.md); the framework references get the agent with
  `getAgent()`). Never navigate inside the callback that receives the ID.
- **Only the Public Key goes to the browser.** The Private API Key (`sec_...`), the Secret Key and
  webhook signing secrets (`whsec_...`) stay on the server. The SDKs refuse a `sec_` or `whsec_`
  value as `publicKey` with `invalid_options`: rotate such a key in the analytics dashboard.
- **Signed-in users get a User HID.** Pass `userId` computed on the server with the `userHid`
  helpers, never a raw email address, phone number or database ID (shieldlabs-user-linking skill,
  [../shieldlabs-user-linking/SKILL.md](../shieldlabs-user-linking/SKILL.md)). The values
  `"anonymous"`, `"fail"`, `"-1"` and `"unknown"` are reserved, and the server SDKs cannot look up
  a User HID that contains `/` or is `.` or `..`: the hex output of the helpers avoids both.
- **Server-side rendering is safe.** The packages touch no browser globals during render and load
  the agent after mount. `load()` rejects with `unsupported_environment` on the server.
- **No identification is not an error for the user.** Send the action without a `requestId` and
  let the backend policy handle "unverified" (step-up or review, never "clean").

## Which call to use

| Situation | Call |
|---|---|
| A form or button the backend protects (signup, login, checkout, payout) | `identify()` in the submit handler |
| A classic full-page form post, or an identification that should be ready when the user submits | `agent.identifyOnInteraction(form)`, then `take()` in the submit handler. The agent comes from `load()` in `@shieldlabs-ai/js` and from `getAgent()` in the framework packages |
| Opening the page is the protected step (for example an account recovery page) | `runOnMount: true` on the identify helper, only in that page's component. It runs once: when the load fails or times out, it resolves `null` with the load error and does not run again when the agent arrives later. With `autoLoad: false` it identifies only when `load()` came first (see [Consent](#consent)) |
| Passive monitoring of a visit, for example once after sign-in | `check()` or the `checkOnLoad` option, which runs once when the agent becomes ready unless an identification for the same User HID is already running. The agent runs at most one check per visit every 5 minutes, and `check()` resolves `null` when it skipped |
| The agent may only run after consent | `autoLoad: false` on the provider, plugin or setup (`autoLoad={false}` in React and Next.js), then `load()` from the state access object once consent is given. With `@shieldlabs-ai/js`, call `load()` only after consent |

## Errors

Every error is a `ShieldLabsError` with a `code`:

| `code` | Cause | What to do |
|---|---|---|
| `invalid_options` | A bad option: missing or malformed `publicKey` (often an unset environment variable), a server secret as `publicKey`, a reserved `userId` | Fix the configuration. Retrying does not help |
| `unsupported_environment` | Server-side rendering, a worker, or a page that is not a secure context | Identify in the browser. Serve the page over HTTPS (the SDK also accepts `localhost`, but identifications are recorded only on registered domains) |
| `load_failed` | The agent could not be imported: network error, content blocker, Content Security Policy | Send the action without a `requestId`. The next call loads again |
| `not_initialized` | `identify()` only (`check()` resolves `null` instead): the agent did not start an identification, for example because another one runs in this or another tab, or `autoLoad: false` and `load()` has not been called yet | Retry once later, or send the action without a `requestId` |
| `timeout` | No answer within `timeout` (default 10 000 ms; in the framework packages it covers the wait for the agent to load and its answer) | Send the action without a `requestId`. A late answer is ignored |

The identify helpers (`useIdentify()` in React, Next.js, Vue and Svelte, `injectIdentify()` in
Angular) never reject: they resolve `null` and put the error in their `error` state. The
`identify()` of the state access objects and of the `@shieldlabs-ai/js` agent rejects, so wrap it in
`try`/`catch`.

## Content Security Policy

If the site sends a `Content-Security-Policy` header, merge these origins into it:

```text
script-src  'self' https://cdn.shieldlabs.ai;
connect-src 'self' https://rest.shieldlabs.ai wss://rest.shieldlabs.ai https://webrtc.shieldlabs.ai stun:ice.shieldlabs.ai:3478;
```

The agent loads with a dynamic `import()`, so no `'unsafe-eval'` is needed. A blocked
`https://webrtc.shieldlabs.ai` still lets identifications arrive, but they can carry the
`stun_not_checked` risk signal. When the `@shieldlabs-ai/js` IIFE build is loaded from a public npm
CDN, add that origin to `script-src` too. Details: https://docs.shieldlabs.ai/setup/csp.

## Consent

The agent does not read consent banners. Where your policy or applicable law requires consent
before identification, set up the framework package with `autoLoad: false` and call `load()` from
the state access object once consent is given (with `@shieldlabs-ai/js`, call `load()` only then).
Until `load()`, nothing waits for consent: the helper's `identify()` resolves `null` at once with a
`not_initialized` error, so the action goes out unverified; a `runOnMount` identification that
starts before `load()` ends the same way and does not run again after `load()`; the low-level
`identify()` of the state access object rejects with `not_initialized`, and its `check()` resolves
`null`; and `getAgent()` waits for `load()` and the agent, with no timeout of its own. `load()`
returns nothing: `status` and `error` report the load. The agent keeps a first-party cookie ID
(`cookieID`, in `localStorage` and a first-party cookie): list it in the cookie notice with its
fraud prevention purpose.

## Test on a registered domain

ShieldLabs records identifications only for the domains registered in the account (analytics
dashboard, Integration > Domains). On `localhost` the page still receives a request ID, but the
identification is rejected and the backend never finds it. Test on a development or staging domain
that resolves in public DNS, served over HTTPS, with that domain's own keys
(https://docs.shieldlabs.ai/setup/environments). In the browser's network panel, expect
`snippet.js` from `cdn.shieldlabs.ai` and posts to `rest.shieldlabs.ai`.

## Call budget

- The ingest accepts about 15 requests per minute per visitor IP, and one identification uses 4 to
  5 of them. An IP over the limit is blocked for 10 minutes: `identify()` still returns a request
  ID, but the identification is rejected and the backend finds nothing for it (unverified). The
  block itself can show up once as a separate identification with the marker `999`.
- `check()` and `checkOnLoad` run at most once per visit every 5 minutes. `identify()` always
  runs.
- In a fresh visit, an identification can be accompanied by one automatic background check from
  the agent (on the first click, key press, form submit or navigation), with a request ID the page
  never receives. Count it in the call budget: a protected action early in a visit can cost two
  identifications, especially when you test repeatedly from one IP.
- Never clear the agent's storage (`cookieID`). Several fresh cookie IDs from one device in a short
  time raise the browser automation risk signal.
- The agent patches `history.pushState` and `history.replaceState` and runs limited background
  checks on clicks and navigation. The page never receives those request IDs, so the backend can
  see extra identifications for the same user and session.

## Pitfalls

- A top-level `await load(...)`: when the agent is blocked, the rest of the module never runs and
  the form handler is never attached. Start loading without awaiting it at the top level.
- Keeping the first `load()` promise and awaiting it on every submit: after a failed load it stays
  rejected. Call `load(options)` where you need the agent; it is memoized and retries.
- Calling `ShieldLabsJS.load()` on a page without a bundler when the IIFE file did not load (a
  blocker, a network error): the `ReferenceError` stops the script, the submit handler is never
  attached and the browser submits the form itself. Check `typeof ShieldLabsJS` first and give the
  form `method="post"` ([vanilla.md](references/vanilla.md)).
- Passing an empty string as `userId` (an empty data attribute or session field): the SDK rejects
  it with `invalid_options`. Pass `value || undefined`.
- Wrapping the helper's `identify()` in `try`/`catch` and reading `result.requestId`: the helper
  resolves `null` instead of rejecting. Send `result?.requestId ?? null`.
- Reading `event.currentTarget` after an `await` in React: it is `null` by then. Read the form
  data first.
- Awaiting `identify()` and then doing a full-page navigation or `form.submit()` in the same tick
  on a slow network: prefer `fetch`, or start early with `identifyOnInteraction()`.
- Reusing one `requestId` for several actions, or caching it in `localStorage`: the backend
  rejects reused and stale request IDs.
- A provider inside a route component, which remounts on every navigation: keep it above the
  router.
- Testing on `localhost` and concluding that the backend is broken because it finds nothing.

## Versions

This skill targets the 1.x packages. Before pinning a version, confirm the current one on npm and
at https://docs.shieldlabs.ai.
