# Plain JavaScript with `@shieldlabs-ai/js`

For pages without a framework binding: plain JavaScript or TypeScript with any bundler, server
rendered pages (Rails, Django, Laravel, Express templates), static HTML served by any backend, and
pages without a bundler.

## Install

```bash
npm install @shieldlabs-ai/js
```

Without a bundler, load the IIFE build of the loader instead ([Without a bundler](#without-a-bundler)).

## Load the agent where you need it

```ts
// shieldlabs.ts
import { load, type LoadOptions, type ShieldLabsAgent } from '@shieldlabs-ai/js';

const options: LoadOptions = { publicKey: import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY };

/** load() is memoized: it returns the loaded agent at once and imports again after a failed load. */
export const getAgent = (): Promise<ShieldLabsAgent> => load(options);

getAgent().catch(() => {}); // start loading now; failures are handled where identify() is called
```

- Call `getAgent()` (that is, `load(options)`) wherever you need the agent. Keeping the first
  promise instead does not recover: after a network error or a slow load it stays rejected.
- `load()` is memoized per agent URL and Public Key; concurrent calls share one import.
- Options: `publicKey` (required), `environment` (`'production'` by default), `scriptUrl`
  (advanced override, `https` only), `timeout` (milliseconds, default `10000`, also the default for
  each call).
- Never `await load(...)` at the top level of a module: when the agent is blocked, the rest of the
  module never runs and the form handler is never attached.

## Send the request ID with a `fetch` submit

```ts
import { ShieldLabsError } from '@shieldlabs-ai/js';
import { getAgent } from './shieldlabs';

const form = document.querySelector<HTMLFormElement>('#signup')!;
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  let identificationId: string | null = null;
  try {
    ({ identificationId } = await (await getAgent()).identify());
  } catch (error) {
    if (error instanceof ShieldLabsError) console.warn('ShieldLabs:', error.code);
  }
  await fetch('/api/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: form.email.value, identificationId }),
  });
});
```

## Classic full-page form posts

For a form that posts and navigates (`action="/signup" method="post"`), start the identification
on the first interaction with the form so that it has finished posting by the time the user
submits. Put the request ID in a hidden field:

```html
<form id="signup" action="/signup" method="post">
  <input name="email" type="email" required />
  <input type="hidden" name="identificationId" />
  <button>Sign up</button>
</form>
```

```ts
import type { InteractionIdentifier } from '@shieldlabs-ai/js';
import { getAgent } from './shieldlabs';

const form = document.querySelector<HTMLFormElement>('#signup')!;

// One handle for the form, created once the agent has loaded. A submit after a failed load
// tries again, because getAgent() calls load() again.
let handle: InteractionIdentifier | undefined;
async function identifier(): Promise<InteractionIdentifier> {
  const agent = await getAgent();
  return (handle ??= agent.identifyOnInteraction(form));
}
identifier().catch(() => {});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const { identificationId } = await (await identifier()).take();
    (form.elements.namedItem('identificationId') as HTMLInputElement).value = identificationId;
  } catch {
    // No identification: submit without a identificationId. The server treats it as unverified.
  }
  form.submit();
});
```

- `identifyOnInteraction(target)` starts `identify()` on the first `focusin`, `pointerdown` or
  `keydown` inside `target`.
- `take()` returns the early identification while it is fresh, otherwise it starts a new one (when
  none runs, when the early one failed, or when it finished more than 4 minutes ago), so the request
  ID stays inside a 5-minute freshness window. Each `take()` re-arms the handle for the next
  submission.
- While users keep interacting with the form, a new identification starts at most every 4 minutes
  (after a failure, at most one attempt every 5 seconds), and each one is billed.
- Call `handle?.dispose()` and reset `handle` when the form goes away, for example when a
  single-page app leaves the route.
- When users can submit without interacting first (autofill and one click), prefer the `fetch`
  version above.

## Without a bundler

Load the IIFE build of the loader, which defines the global `ShieldLabsJS`. Pin the version and
confirm the current one on npm first, or serve the file yourself (next section):

```html
<form id="signup" action="/api/signup" method="post">
  <input name="email" type="email" required />
  <button>Sign up</button>
</form>

<script src="https://cdn.jsdelivr.net/npm/@shieldlabs-ai/js@1.0.0/dist/shieldlabs.iife.js"></script>
<script>
  const options = { publicKey: '0123456789abcdef0123456789abcdef' };

  // The loader file itself can be blocked (a content blocker, a network error): check that it
  // loaded, and never let a failure stop the form.
  async function getRequestId() {
    if (typeof ShieldLabsJS === 'undefined') return null;
    try {
      const agent = await ShieldLabsJS.load(options); // memoized; imports again after a failed load
      return (await agent.identify()).identificationId;
    } catch (error) {
      console.warn('ShieldLabs:', error && error.code);
      return null;
    }
  }

  document.querySelector('#signup').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget; // read it before the first await: it is null afterwards
    const identificationId = await getRequestId();
    await fetch(form.action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: form.email.value, identificationId }),
    });
  });
</script>
```

- Replace the placeholder with the Public Key of the domain, or have the server render it into
  the page (shieldlabs-setup skill, `references/environment.md`, "Static pages").
- `method="post"` on the form is a safety net: if the script never runs, the browser posts the
  form instead of sending its fields, passwords included, in the URL of a GET request.
- When you load the IIFE from a public npm CDN, add that origin to the `script-src` of your
  Content Security Policy.

## Serve the loader from your own origin

The package ships the IIFE as `dist/shieldlabs.iife.js`. Its `exports` map exposes only the entry
and `package.json`, so resolve the file through `package.json`:

```js
// Express
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);
const loaderFile = path.join(path.dirname(require.resolve('@shieldlabs-ai/js/package.json')), 'dist', 'shieldlabs.iife.js');

app.get('/assets/shieldlabs.iife.js', (req, res) => res.type('text/javascript').sendFile(loaderFile));
```

```js
// Fastify, with loaderFile resolved as above
import { createReadStream } from 'node:fs';

fastify.get('/assets/shieldlabs.iife.js', (request, reply) =>
  reply.type('text/javascript').send(createReadStream(loaderFile)));
```

Then use `<script src="/assets/shieldlabs.iife.js"></script>`; no extra CSP origin is needed. This
file is only the loader: the agent itself always comes from `https://cdn.shieldlabs.ai`. For ES
modules without a bundler, serve `dist/index.js` the same way and import `load` from it in a
`<script type="module">`.

## Signed-in users

Render the User HID computed on the server (shieldlabs-user-linking skill) into the page, for
example as a data attribute, and pass it as `userId`:

```html
<form id="checkout" data-user-hid="{{ user_hid }}">...</form>
```

```ts
// An empty attribute (no signed-in user) must become undefined: the SDK rejects "" with invalid_options.
const { identificationId, userId } = await (await getAgent()).identify({ userId: form.dataset.userHid || undefined });
```

Omit `userId` (or pass `undefined`) for visitors who are not signed in. The SDK rejects `""`,
`"anonymous"`, `"fail"`, `"-1"` and `"unknown"`, and logs a one-time warning for values that look
like an email address, contain `/`, `?`, `#` or `%`, or are `.` or `..`. The History API looks a
User HID up as a URL path segment: the server SDKs refuse a value that contains `/` or is `.` or
`..`, and the other characters are easy to escape wrongly. The 64 hex characters of the `userHid`
helpers always work.

## Background checks

`check(options?)` runs the agent's limited check: at most one identification per visit every five
minutes for the same user, shared across tabs. It resolves `null` when the agent skipped it. Use it
for passive monitoring, for example once after sign-in, and keep `identify()` for protected
actions:

```ts
const result = await (await getAgent()).check({ userId: hid });
```

## Multi-page sites

Each full page load runs the loader again, and `load()` is memoized only within one page. That is
expected: the browser caches the agent module. Call `identify()` only at protected actions, never
on every page view.
