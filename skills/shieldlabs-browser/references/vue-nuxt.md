# Vue and Nuxt with `@shieldlabs-ai/vue`

Vue 3.3 or later, Vue SSR and Nuxt 3.

## Install

```bash
npm install @shieldlabs-ai/vue @shieldlabs-ai/js@1.1.0
```

`vue` and `@shieldlabs-ai/js` are peer dependencies.

## Vue: install the plugin once

```ts
// src/main.ts
import { createShieldLabs } from '@shieldlabs-ai/vue';
import { createApp } from 'vue';
import App from './App.vue';

createApp(App)
  .use(createShieldLabs({ publicKey: import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY }))
  .mount('#app');
```

Options: `publicKey` (required), `environment`, `scriptUrl`, `timeout` (milliseconds, default
`10000`: the load limit and the default timeout of each call), `checkOnLoad` (`false` by default;
`true` or `{ userId }` runs one `check()` when the agent becomes ready, unless an `identify()` or
`check()` for the same User HID is in flight), `autoLoad` (`true` by default; `false` loads nothing
until `load()`, see [Consent](#consent-autoload-false)). The plugin loads the agent in the browser
after the app is mounted, never during server rendering.

## Identify on submit

```vue
<script setup lang="ts">
import { useIdentify } from '@shieldlabs-ai/vue';
import { ref } from 'vue';

const email = ref('');
const { identify, isLoading } = useIdentify();

async function onSubmit() {
  const result = await identify(); // null when there is no identification; never rejects
  await fetch('/api/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.value, identificationId: result?.identificationId ?? null }),
  });
}
</script>

<template>
  <form @submit.prevent="onSubmit">
    <input v-model="email" type="email" required />
    <button :disabled="isLoading">Sign up</button>
  </form>
</template>
```

`useIdentify({ userId?, runOnMount? })` returns `{ identify, result, isLoading, error, reset }` as
refs. `identify(options?)` resolves `{ identificationId, userId }` or `null` (the reason is in `error`)
and never rejects. While a call of the same helper with the same User HID and the same effective
timeout is in flight (a double click), `identify()` returns it instead of starting another
identification; a call without `timeout` counts as one with the plugin's `timeout`. The `timeout`
bounds the whole call: the wait for the agent to load and its answer. Composables must run in
`setup()` (or `app.runWithContext()`).

## Signed-in users

```vue
<script setup lang="ts">
import { useIdentify } from '@shieldlabs-ai/vue';

const props = defineProps<{ userHid: string }>(); // computed on the server
const { identify } = useIdentify({ userId: () => props.userHid });
</script>
```

`userId` accepts a string, a ref or a getter and is read when `identify()` runs. `null` and
`undefined` mean anonymous. Per-call options override it whenever they have the `userId` key, even
with the value `undefined` or `null`: `identify({ userId: undefined })` runs an anonymous
identification, and only a call without the `userId` key uses the composable's `userId`.

## Agent state

`useShieldLabs()` returns `{ status, error, identify, check, load, getAgent }`. `status` is
`'loading'`, `'ready'` or `'error'`, and stays `'loading'` during server rendering and a
component's first render. This `identify()` rejects with a `ShieldLabsError` (unlike
`useIdentify()`), and `check()` resolves `null` when the agent skipped the check. `load()` starts
loading the agent (and loads again after a failed load); `getAgent()` resolves the agent of
`@shieldlabs-ai/js` once it has loaded, and rejects with the load error when the load fails or times
out.

## Consent: `autoLoad: false`

```ts
// src/main.ts
import { createShieldLabs, useShieldLabs } from '@shieldlabs-ai/vue';
import { createApp } from 'vue';
import App from './App.vue';

const app = createApp(App).use(
  createShieldLabs({ publicKey: import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY, autoLoad: false }),
);
// A returning visitor who already gave consent (hasConsent() reads your consent storage). Call
// load() before mount(), so that identifications started on mount wait for the agent.
if (hasConsent()) app.runWithContext(() => useShieldLabs().load());
app.mount('#app');
```

Nothing loads until `load()` from `useShieldLabs()` is called, for example in the accept handler of
the consent banner (`const { load } = useShieldLabs();` in its `setup()`). Until then `status`
stays `'loading'`, `useIdentify().identify()` resolves `null` at once with a `not_initialized`
error (the action goes out unverified), `useShieldLabs().identify()` rejects with it, `check()`
resolves `null`, and `getAgent()` waits for `load()` with no timeout of its own. A `runOnMount`
identification ends with `not_initialized` unless `load()` was called before the component
mounted, ends with the load error when the load fails or times out, and does not run again after
`load()` or when the agent arrives later. `checkOnLoad` runs once the agent is ready.

## Start on the first interaction

To have the identification ready at submit time, arm the form with `identifyOnInteraction()` of
the agent from `getAgent()`. The plugin loads the agent once, and `getAgent()` waits for it (with
`autoLoad: false`, until `load()`):

```vue
<script setup lang="ts">
import { useShieldLabs, type InteractionIdentifier } from '@shieldlabs-ai/vue';
import { onBeforeUnmount, onMounted, ref } from 'vue';

const form = ref<HTMLFormElement | null>(null);
const { getAgent } = useShieldLabs();
let identifier: InteractionIdentifier | undefined;
let unmounted = false;

onMounted(() => {
  getAgent()
    .then((agent) => {
      if (!unmounted && form.value) identifier = agent.identifyOnInteraction(form.value);
    })
    .catch(() => {
      // No agent: the form is sent without a identificationId.
    });
});

onBeforeUnmount(() => {
  unmounted = true;
  identifier?.dispose();
});

async function onSubmit() {
  // The identification for this submission (none while the agent has not loaded); take()
  // re-arms for the next one.
  const result = await identifier?.take().catch(() => null);
  await fetch('/api/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identificationId: result?.identificationId ?? null }),
  });
}
</script>

<template>
  <form ref="form" @submit.prevent="onSubmit"><!-- fields --></form>
</template>
```

`take()` hands out the early identification only while it is fresh and otherwise starts a new one.
For a classic full-page post, write `result?.identificationId ?? ''` into a hidden `identificationId` field, wait
for `nextTick()` and call `form.value?.submit()` instead of `fetch()`.

## Nuxt 3

Expose the Public Key through the public runtime config:

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  runtimeConfig: {
    public: {
      shieldlabsPublicKey: '', // set by NUXT_PUBLIC_SHIELDLABS_PUBLIC_KEY
    },
  },
});
```

Install the plugin in the browser only:

```ts
// plugins/shieldlabs.client.ts
import { createShieldLabs } from '@shieldlabs-ai/vue';

export default defineNuxtPlugin((nuxtApp) => {
  const config = useRuntimeConfig();
  nuxtApp.vueApp.use(createShieldLabs({ publicKey: config.public.shieldlabsPublicKey }));
});
```

Pages use the composables as in Vue. On the server they render the initial state and never load
the agent:

```vue
<!-- pages/signup.vue -->
<script setup lang="ts">
import { useIdentify } from '@shieldlabs-ai/vue';

const email = ref('');
const { identify, isLoading } = useIdentify();

async function onSubmit() {
  const result = await identify();
  await $fetch('/api/signup', { method: 'POST', body: { email: email.value, identificationId: result?.identificationId ?? null } });
}
</script>
```

The server route reads the verdict with `@shieldlabs-ai/node` (shieldlabs-server skill):

```ts
// server/api/signup.post.ts
import { ShieldLabs, ShieldLabsError, evaluateIdentification, type Identification } from '@shieldlabs-ai/node';

const shieldlabs = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY! });

export default defineEventHandler(async (event) => {
  const { identificationId } = await readBody<{ email: string; identificationId: string | null }>(event);
  let identification: Identification | null = null;
  if (identificationId) {
    try {
      identification = await shieldlabs.identifications.get(identificationId, { domainId: process.env.SHIELDLABS_DOMAIN_ID! });
      if (identification && (identification.identification_id !== identificationId || !Number.isFinite(identification.risk_score) || identification.raw.domain_id !== process.env.SHIELDLABS_DOMAIN_ID || (identification.raw.signals as { state?: string } | undefined)?.state !== "ok")) identification = null;
    } catch (error) {
      if (!(error instanceof ShieldLabsError)) throw error; // stays unverified
    }
  }
  const firstUse = identification ? await claimRequestId(identification.identification_id) : false;
  const verdict = evaluateIdentification(identification, { isReplay: () => !firstUse });
  if (!verdict.ok) throw createError({ statusCode: 403, statusMessage: 'Signup refused' });
  // Create the account.
  return { ok: true };
});
```

A webhook route needs the raw bytes:

```ts
// server/api/webhooks/shieldlabs.post.ts
import { SignatureVerificationError, webhooks, type WebhookEvent } from '@shieldlabs-ai/node';

// Several secrets, comma-separated, while you rotate one.
const secrets = (process.env.SHIELDLABS_WEBHOOK_SECRET ?? '').split(',').map((s) => s.trim()).filter(Boolean);

export default defineEventHandler(async (event) => {
  if (secrets.length === 0) throw createError({ statusCode: 500 }); // not configured: never a 401
  const body = (await readRawBody(event, false)) ?? new Uint8Array();
  let delivery: WebhookEvent;
  try {
    delivery = webhooks.constructEvent(body, getHeader(event, 'x-shield-signature'), secrets);
  } catch (error) {
    throw createError({ statusCode: error instanceof SignatureVerificationError ? 401 : 400 });
  }
  if (delivery.event_type === 'identification.scored') await saveIdentificationOnce(delivery.data);
  return { received: true };
});
```

On edge presets (for example Cloudflare), use `await webhooks.constructEventAsync(...)` instead.

## Component tests

Provide a stand-in context under `shieldLabsKey` so that tests never load the agent:

```ts
import { shieldLabsKey, type ShieldLabsContext, type ShieldLabsStatus } from '@shieldlabs-ai/vue';
import { mount } from '@vue/test-utils';
import { vi } from 'vitest';
import { ref } from 'vue';
import SignupForm from './SignupForm.vue';

const shieldlabs: ShieldLabsContext = {
  status: ref<ShieldLabsStatus>('ready'),
  error: ref(null),
  identify: vi.fn(async () => ({ identificationId: '6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a', userId: null })),
  check: vi.fn(async () => null),
  load: vi.fn(),
  getAgent: vi.fn(() => Promise.reject(new Error('No agent in component tests.'))),
};

mount(SignupForm, { global: { provide: { [shieldLabsKey as symbol]: shieldlabs } } });
```
