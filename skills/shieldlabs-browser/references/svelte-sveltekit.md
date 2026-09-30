# Svelte and SvelteKit with `@shieldlabs/svelte`

Svelte 5 (components with and without runes) and SvelteKit 2 with any adapter, including
prerendering and server-side rendering.

## Install

```bash
npm install @shieldlabs/svelte @shieldlabs/js
npm install @shieldlabs/node   # for the SvelteKit server code below
```

`.env`:

```bash
PUBLIC_SHIELDLABS_PUBLIC_KEY=0123456789abcdef0123456789abcdef
SHIELDLABS_API_KEY=sec_your_private_key
```

Keep the Private API Key in server-only modules (`$env/static/private`, `+page.server.ts`,
`+server.ts`). Only the Public Key belongs in `$env/static/public`.

## Set up once in the root layout

```svelte
<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import { PUBLIC_SHIELDLABS_PUBLIC_KEY } from '$env/static/public';
  import { setShieldLabs } from '@shieldlabs/svelte';

  let { children } = $props();

  setShieldLabs({ publicKey: PUBLIC_SHIELDLABS_PUBLIC_KEY });
</script>

{@render children()}
```

In a Svelte app built with Vite, call `setShieldLabs({ publicKey: import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY })`
in `App.svelte`. Options: `publicKey` (required), `environment`, `scriptUrl`, `timeout`
(milliseconds, default `10000`: the load limit and the default timeout of each call),
`checkOnLoad`, `autoLoad` (`true` by default; `false` loads nothing until `load()`, see
[Consent](#consent)). The agent loads in `onMount`, once per page, and client-side navigation never
loads it again. `setShieldLabs()` returns the same context as `getShieldLabs()`. To read props such
as `data` without the "initial value" warning, pass a function:
`setShieldLabs(() => ({ publicKey, checkOnLoad: { userId: data.userHid } }))`.

## Identify on submit with `use:enhance`

```svelte
<!-- src/routes/signup/+page.svelte -->
<script lang="ts">
  import { enhance } from '$app/forms';
  import { useIdentify } from '@shieldlabs/svelte';
  import type { SubmitFunction } from '@sveltejs/kit';

  const { identify, isLoading } = useIdentify();

  const protect: SubmitFunction = async ({ formData }) => {
    const result = await identify(); // null when no identification was possible; never rejects
    formData.set('requestId', result?.requestId ?? '');
  };
</script>

<form method="POST" use:enhance={protect}>
  <input name="email" type="email" required />
  <button disabled={$isLoading}>Sign up</button>
</form>
```

`use:enhance` sends the form with `fetch`, so the page stays alive while the agent posts. Without
JavaScript, or when the agent cannot load, the form is still sent without a `requestId`.

```ts
// src/routes/signup/+page.server.ts
import { fail } from '@sveltejs/kit';
import { SHIELDLABS_API_KEY } from '$env/static/private';
import { ShieldLabs, ShieldLabsError, evaluateIdentification, type Identification } from '@shieldlabs/node';
import type { Actions } from './$types';

const shieldlabs = new ShieldLabs({ apiKey: SHIELDLABS_API_KEY });

export const actions = {
  default: async ({ request }) => {
    const data = await request.formData();
    const requestId = String(data.get('requestId') ?? '');
    let identification: Identification | null = null;
    if (requestId) {
      try {
        identification = await shieldlabs.identifications.get(requestId); // waits until scored
      } catch (error) {
        if (!(error instanceof ShieldLabsError)) throw error; // stays unverified
      }
    }
    const firstUse = identification ? await claimRequestId(identification.request_id) : false;
    const verdict = evaluateIdentification(identification, { isReplay: () => !firstUse });
    if (!verdict.ok) return fail(403, { message: 'We could not verify this signup.' });
    // Create the account.
  },
} satisfies Actions;
```

`claimRequestId` is your atomic "first use" store (shieldlabs-server skill).

## `useIdentify()`

`useIdentify(options?)` must run during component initialisation. `options` is
`{ userId?, timeout?, runOnMount? }` or a function that returns it (read when each identification
starts, so it follows sign-in and sign-out). It returns `{ result, isLoading, error, identify,
reset }`: readable stores plus `identify(options?)`, which resolves `{ requestId, userId }` or
`null` (the reason is in `$error`) and never rejects. A second call of the same helper while one
runs with the same User HID and the same effective timeout returns the running one (a call without
its own `timeout` counts with the helper's, else the setup's). The `timeout` covers the whole call:
the wait for the agent to load and its answer. A `userId` key in the call options overrides the
helper's User HID even when it is `undefined` or `null`, which both mean anonymous.

With a plain `fetch` instead of `use:enhance`:

```svelte
<script lang="ts">
  import { useIdentify } from '@shieldlabs/svelte';

  const { identify, isLoading } = useIdentify();

  async function onsubmit(event: SubmitEvent) {
    event.preventDefault();
    const form = event.currentTarget as HTMLFormElement;
    const result = await identify();
    await fetch('/api/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: form.email.value, requestId: result?.requestId ?? null }),
    });
  }
</script>

<form {onsubmit}>
  <input name="email" type="email" required />
  <button disabled={$isLoading}>Sign up</button>
</form>
```

## Signed-in users

Compute the User HID in `+layout.server.ts` (shieldlabs-user-linking skill) and pass it through
`data`:

```svelte
<script lang="ts">
  import { useIdentify } from '@shieldlabs/svelte';

  let { data } = $props();
  const { identify } = useIdentify(() => ({ userId: data.userHid }));
</script>
```

## Agent state and background checks

`getShieldLabs()` returns `{ status, error, identify, check, load, getAgent }` of the nearest
`setShieldLabs()`: `status` and `error` are readable stores; `identify()` rejects with a
`ShieldLabsError`; `check()` resolves `null` when the agent skipped it; `load()` starts loading the
agent; `getAgent()` resolves the agent of `@shieldlabs/js` once it has loaded, and rejects with
the load error when the load fails or times out. `checkOnLoad: true` (or `{ userId }`) runs one
background check when the agent is ready, unless an identification for the same User HID is
already running. `runOnMount: true` on `useIdentify()` runs one identification per mount; use it
only where opening the page is the protected action (with `autoLoad: false`, see
[Consent](#consent)). When the load fails or times out, that identification resolves `null` with
the load error and does not run again when the agent arrives later.

## Start when the user begins the action

To have the identification finished by the time the user submits (for example before a classic
full-page form post), arm the form with `identifyOnInteraction()` of the agent from `getAgent()`:

```svelte
<!-- src/routes/signup/+page.svelte: a full-page form post, without use:enhance -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { getShieldLabs, type InteractionIdentifier } from '@shieldlabs/svelte';

  const { getAgent } = getShieldLabs();
  let form: HTMLFormElement;
  let requestIdField: HTMLInputElement;
  let early: InteractionIdentifier | undefined;

  onMount(() => {
    let active = true;
    // Arms the form once the agent is loaded. The submit handler never waits for this.
    getAgent().then(
      (agent) => {
        if (active) early = agent.identifyOnInteraction(form);
      },
      () => {}, // no agent: the form is sent without a requestId
    );
    return () => {
      active = false;
      early?.dispose();
    };
  });

  async function onsubmit(event: SubmitEvent) {
    event.preventDefault();
    try {
      // The early identification while it is fresh, otherwise a new one.
      if (early) requestIdField.value = (await early.take()).requestId;
    } catch {
      // No identification: the form is sent without a requestId, and the server treats it as unverified.
    }
    form.submit();
  }
</script>

<form bind:this={form} method="POST" {onsubmit}>
  <input name="email" type="email" required />
  <input bind:this={requestIdField} type="hidden" name="requestId" />
  <button>Sign up</button>
</form>
```

`getAgent()` has no timeout of its own: it resolves once the agent has loaded (with
`autoLoad: false`, after `load()`), and rejects with the load error when the load fails or times
out, so the submit handler does not wait for it. With `use:enhance`, call `take()` in the submit
function the same way and put the request ID in `formData`.

## Consent

Where consent is required before the agent runs, pass `autoLoad: false` and call `load()` once
consent is given:

```svelte
<!-- src/routes/+layout.svelte -->
<script lang="ts">
  import { PUBLIC_SHIELDLABS_PUBLIC_KEY } from '$env/static/public';
  import { setShieldLabs } from '@shieldlabs/svelte';
  import { consent } from '$lib/consent'; // your consent state, for example a store your banner sets

  let { children } = $props();

  const { load } = setShieldLabs({ publicKey: PUBLIC_SHIELDLABS_PUBLIC_KEY, autoLoad: false });

  // Loads the agent once, after consent.
  $effect(() => {
    if ($consent) load();
  });
</script>

{@render children()}
```

`load()` returns nothing and does nothing while the agent loads, once it is loaded and during
server-side rendering. Until it is called, `status` stays `'loading'`, `useIdentify().identify()`
resolves `null` at once with a `not_initialized` error (the form goes out unverified), a
`runOnMount` identification that starts before `load()` ends the same way and does not run again
after `load()`, `getShieldLabs().identify()` rejects with `not_initialized`, `check()` resolves
`null`, and `getAgent()` waits for `load()`. When consent is already stored, call `load()` during
initialisation of the root layout, before the pages mount.

## Content Security Policy in SvelteKit

Add the ShieldLabs origins (see [../SKILL.md](../SKILL.md)) to `kit.csp.directives` in
`svelte.config.js`: `'script-src'` gets `https://cdn.shieldlabs.ai`, and `'connect-src'` gets the
`rest.shieldlabs.ai`, `webrtc.shieldlabs.ai` and `ice.shieldlabs.ai` entries.

## Runes and stores

The state comes as `svelte/store` readables, so `$status`, `$result` and the other stores work in
runes components and in components that use `export let`. In runes code outside the markup, wrap
a store with `fromStore()` from `svelte/store` and read `.current`.
