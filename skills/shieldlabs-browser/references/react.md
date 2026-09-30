# React with `@shieldlabs/react`

React 18 and 19, with Vite, React Router or any other setup. For Next.js use `@shieldlabs/next`
([nextjs.md](nextjs.md)).

## Install

```bash
npm install @shieldlabs/react @shieldlabs/js
```

`@shieldlabs/js` (1.x) and `react` are peer dependencies.

## Provider at the root

Render `ShieldLabsProvider` once, above the router, so that navigation never remounts it:

```tsx
// src/main.tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { ShieldLabsProvider } from '@shieldlabs/react';
import { App } from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ShieldLabsProvider publicKey={import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY}>
      <App />
    </ShieldLabsProvider>
  </StrictMode>,
);
```

Props: `publicKey` (required), `environment`, `scriptUrl`, `timeout` (milliseconds, default
`10000`: the load limit and the default timeout of each call), `autoLoad` (`true` by default;
`false` loads nothing until `load()`, see [Consent](#consent)), `checkOnLoad` (`false` by default;
`true` or `{ userId }` runs one `check()` when the agent is ready, unless a call for the same User
HID is running). The agent loads in an effect after the first render, once per app, also in
StrictMode.

Vite replaces `import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY` when it builds the app: set the variable
before `npm run build` and build once per environment. When one build serves several environments
(for example a single-page app served by its own backend), have the backend put the Public Key
into the page at run time instead, in a `<meta name="shieldlabs-public-key">` tag of `index.html`
(shieldlabs-setup skill, `references/environment.md`), and pass
`document.querySelector('meta[name="shieldlabs-public-key"]')?.getAttribute('content') ?? ''` as
`publicKey`.

## Identify on submit

```tsx
// src/SignupForm.tsx
import type { SyntheticEvent } from 'react';
import { useIdentify } from '@shieldlabs/react';

export function SignupForm() {
  const { identify, isLoading } = useIdentify();

  async function onSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = new FormData(event.currentTarget).get('email'); // read before any await
    // null when there is no identification (the reason is in `error`): send the signup anyway,
    // the server treats it as unverified.
    const result = await identify();
    await fetch('/api/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, requestId: result?.requestId ?? null }),
    });
  }

  return (
    <form onSubmit={onSubmit}>
      <input name="email" type="email" required />
      <button disabled={isLoading}>Sign up</button>
    </form>
  );
}
```

`useIdentify({ userId?, runOnMount? })` returns `{ identify, result, isLoading, error, reset }`.
`identify(options?)` resolves `{ requestId, userId }`, or `null` with the `ShieldLabsError` in
`error`, and never rejects. While a call of the same hook with the same User HID and the same
effective timeout runs, it returns that call, so a double submit costs one identification; a call
without `timeout` counts as one with the provider `timeout`. The call's `timeout` (default: the
provider `timeout`) covers the wait for the agent and its answer. The hook must be called inside
the provider; outside it throws an `Error` that names the hook.

## React Router or Remix actions

Add the request ID to the form data before submitting. `useSubmit` sends it with `fetch`, so the
page stays alive while the agent posts:

```tsx
import type { SyntheticEvent } from 'react';
import { useSubmit } from 'react-router';
import { useIdentify } from '@shieldlabs/react';

export function SignupForm() {
  const submit = useSubmit();
  const { identify } = useIdentify();

  async function onSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const result = await identify(); // null: submit without a requestId, the action treats it as unverified
    if (result) formData.set('requestId', result.requestId);
    submit(formData, { method: 'post' });
  }

  return <form method="post" onSubmit={onSubmit}>{/* fields */}</form>;
}
```

Import `useSubmit` from `react-router-dom` or `@remix-run/react` in older versions. The server
action reads `requestId` from the form data (shieldlabs-server skill).

## Signed-in users

Hand the User HID computed on the server to the page (session payload, loader data) and pass it
to the hook:

```tsx
const { identify } = useIdentify({ userId: session.userHid });
const result = await identify(); // result?.userId is the User HID that was sent
```

`identify({ userId })` overrides the hook's User HID for one call. The `userId` key decides, even
with the value `undefined` or `null` (both mean anonymous): `identify({ userId: undefined })` runs
an anonymous identification, and only a call without the `userId` key uses the hook's User HID.

## Identify earlier: start on the first interaction

`identify()` on submit is enough for most single-page apps. To have the identification finished
by the time the user submits (or before a classic full-page post), start it on the first
interaction with the form: `getAgent()` from `useShieldLabs()` resolves the loaded agent of
`@shieldlabs/js`, and its `identifyOnInteraction(form)` starts `identify()` on the first
`focusin`, `pointerdown` or `keydown` inside the form:

```tsx
import { useEffect, useRef, type SyntheticEvent } from 'react';
import { useIdentify, useShieldLabs, type InteractionIdentifier } from '@shieldlabs/react';

export function SignupForm() {
  const { getAgent } = useShieldLabs();
  const { identify } = useIdentify();
  const formRef = useRef<HTMLFormElement>(null);
  const early = useRef<InteractionIdentifier | null>(null);

  useEffect(() => {
    const form = formRef.current;
    if (!form) return;
    let active = true;
    getAgent().then(
      (agent) => {
        if (active) early.current = agent.identifyOnInteraction(form);
      },
      () => {}, // the agent could not load: the submit handler tries again
    );
    return () => {
      active = false;
      early.current?.dispose();
      early.current = null;
    };
  }, [getAgent]);

  async function onSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = new FormData(event.currentTarget).get('email');
    // The early identification while it is fresh, otherwise a new one. Without an early handle,
    // identify() loads the agent again; both give null when there is no identification.
    const result = early.current ? await early.current.take().catch(() => null) : await identify();
    await fetch('/api/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, requestId: result?.requestId ?? null }),
    });
  }

  return (
    <form ref={formRef} onSubmit={onSubmit}>
      <input name="email" type="email" required />
      <button>Sign up</button>
    </form>
  );
}
```

`take()` hands out the early identification only while it is fresh; when it failed, or finished
more than 4 minutes ago, it starts a new one, and it re-arms the handle for the next submission.
While users keep interacting with the form, a new identification starts at most every 4 minutes
(after a failure, at most one attempt every 5 seconds), and each is billed. The effect's cleanup
removes the listeners. With `autoLoad={false}`, `getAgent()` waits for `load()`, so the form is
armed once `load()` has been called and the agent has loaded. When the load fails or times out,
`getAgent()` rejects with the load error and the form stays unarmed: the submit handler then calls
`identify()`, which loads again. For a classic full-page post, put `result?.requestId ?? ''` in a
hidden `requestId` field and call `form.submit()` instead of `fetch()`.

## Identify when a component mounts

`useIdentify({ runOnMount: true })` runs `identify()` once per mount, as soon as the agent is
ready. When the load fails or times out, it resolves `null` with the load error in `error` and
does not run again when the agent arrives later. Use it only in a component that is itself the
protected step (for example an account recovery page), never in a layout, a list item or a
component that mounts on every route. Send `result?.requestId` with the single request that the
step protects. With `autoLoad={false}`, a `runOnMount` identification that starts before `load()`
resolves `null` at once with a `not_initialized` error and does not run again after `load()`: when
consent is known at the first render, pass it as `autoLoad={consentGiven}` ([Consent](#consent)).

## Agent status

```tsx
import { useShieldLabs } from '@shieldlabs/react';

function AgentStatus() {
  const { status, error } = useShieldLabs(); // 'loading' | 'ready' | 'error'
  return status === 'error' ? <small>Identification unavailable ({error?.code})</small> : null;
}
```

`useShieldLabs()` returns `{ status, error, identify, check, load, getAgent }`. Its `identify()`
is the call of `@shieldlabs/js` and rejects with a `ShieldLabsError`; `check()` resolves `null`
when the agent skipped it. Never block a protected action on `status`: calls wait for the agent
within their timeout, and a failed load is tried again by the next `identify()`, `check()`,
`getAgent()` or `load()`.

## Consent

Where consent is required before the agent loads, render the provider with `autoLoad={false}`:
nothing loads until `load()` from `useShieldLabs()` is called, or until `autoLoad` becomes `true`.

```tsx
import { ShieldLabsProvider, useShieldLabs } from '@shieldlabs/react';
import { SignupForm } from './SignupForm';

export function App() {
  return (
    <ShieldLabsProvider publicKey={import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY} autoLoad={false}>
      <ConsentBanner />
      <SignupForm />
    </ShieldLabsProvider>
  );
}

function ConsentBanner() {
  const { load } = useShieldLabs();
  // Record the choice as your consent tool requires, then load the agent.
  return <button onClick={load}>Accept</button>;
}
```

When the consent state already lives in React, pass it instead:
`<ShieldLabsProvider publicKey={publicKey} autoLoad={consentGiven}>`. Until the agent may load,
the rest of the app works unchanged: `identify()` from `useIdentify()` resolves `null` at once
with a `not_initialized` error (forms go out without a `requestId`, unverified), and so does a
`runOnMount` identification, which does not run again after `load()`;
`useShieldLabs().identify()` rejects with `not_initialized` and `useShieldLabs().check()` resolves
`null`; `getAgent()` waits; `status` stays `'loading'`. `checkOnLoad` runs once the agent is ready.
Setting `autoLoad` back to `false` does not unload an agent that has loaded.

## Tests

Mock `@shieldlabs/react` with your test runner (for example `vi.mock` or `jest.mock`) so that unit
tests never load the agent from the CDN: return a `useIdentify` whose `identify` resolves a fixed
`{ requestId, userId: null }` (or `null` to test the unverified path), and a `ShieldLabsProvider`
that renders its children.
