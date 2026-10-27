# Next.js with `@shieldlabs-ai/next`

Next.js 14 or later. `@shieldlabs-ai/next` has two entries:

| Import | Runs in | Exports |
|---|---|---|
| `@shieldlabs-ai/next` | the browser (client module, marked `"use client"`) | `ShieldLabsProvider`, `useIdentify`, `useShieldLabs`, `ShieldLabsError` (the React bindings) |
| `@shieldlabs-ai/next/server` | route handlers, Server Actions, Server Components, Pages Router API routes, Node.js and Edge runtimes | `getIdentification`, `createWebhookHandler`, and from `@shieldlabs-ai/node`: `ShieldLabs`, `evaluateIdentification`, `riskBand`, `isRateLimited`, `userHidAsync`, `NIL_UUID`, `SIGNALS`, `RISK_BANDS`, the error classes and the types |

## Install and configure

```bash
npm install @shieldlabs-ai/next @shieldlabs-ai/react @shieldlabs-ai/js @shieldlabs-ai/node
```

The last three are peer dependencies. Environment variables (`.env.local` in development, the
hosting provider's settings in production):

```bash
NEXT_PUBLIC_SHIELDLABS_PUBLIC_KEY=0123456789abcdef0123456789abcdef
SHIELDLABS_API_KEY=sec_your_private_key
SHIELDLABS_WEBHOOK_SECRET=whsec_your_signing_secret
```

Only the Public Key gets the `NEXT_PUBLIC_` prefix: Next.js copies those variables into the
JavaScript sent to the browser. `NEXT_PUBLIC_` values are inlined at build time, so set them
before `next build`.

## App Router

Render the provider in the root layout. The layout is a Server Component; the provider is a
client component, so this works as is:

```tsx
// app/layout.tsx
import type { ReactNode } from 'react';
import { ShieldLabsProvider } from '@shieldlabs-ai/next';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ShieldLabsProvider publicKey={process.env.NEXT_PUBLIC_SHIELDLABS_PUBLIC_KEY!}>
          {children}
        </ShieldLabsProvider>
      </body>
    </html>
  );
}
```

Identify in a client component when the form is submitted:

```tsx
// app/signup/signup-form.tsx
'use client';

import type { SyntheticEvent } from 'react';
import { useIdentify } from '@shieldlabs-ai/next';

export function SignupForm() {
  const { identify, isLoading } = useIdentify();

  async function onSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = new FormData(event.currentTarget).get('email');
    // null when there is no identification (a content blocker, a timeout): the signup goes out
    // anyway, and the route handler treats it as unverified.
    const result = await identify();
    await fetch('/api/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, identificationId: result?.identificationId ?? null }),
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

Read the verdict in the route handler:

```ts
// app/api/signup/route.ts
import {
  ShieldLabsError,
  evaluateIdentification,
  getIdentification,
  type Identification,
} from '@shieldlabs-ai/next/server';

export async function POST(request: Request) {
  const body = (await request.json()) as { email?: string; identificationId?: string | null };
  let identification: Identification | null = null;
  if (body.identificationId) {
    try {
      // Reads SHIELDLABS_API_KEY and waits (with backoff) until the identification is scored.
      identification = await getIdentification(body.identificationId);
    } catch (error) {
      if (!(error instanceof ShieldLabsError)) throw error; // the signup stays unverified
      console.warn('ShieldLabs lookup failed:', error.name);
    }
  }
  // claimRequestId: your atomic "first use" store (see the shieldlabs-server skill).
  const firstUse = identification ? await claimRequestId(identification.identification_id) : false;
  const verdict = evaluateIdentification(identification, { isReplay: () => !firstUse });
  if (!verdict.ok) {
    console.info('signup refused', verdict.reason, verdict.band);
    return Response.json({ error: 'signup_refused' }, { status: 403 });
  }
  // Create the account.
  return Response.json({ ok: true }, { status: 201 });
}
```

`getIdentification(identificationId, options?)` takes the options of `identifications.get` in
`@shieldlabs-ai/node` (`wait`, `timeout`, `pollInterval`, `signal`) plus `client`, and waits the same
way: `timeout` (default 10 000 ms) is the total budget, each poll is one HTTP attempt, a 429, a 5xx
or a network error keeps polling, 400, 401, 403 and 404 stop at once (and so does a 429 whose
`Retry-After`, capped at 10 s, is longer than the time left), and the last poll runs at the
deadline (shieldlabs-server skill). Without `client` it creates one client per process from
`SHIELDLABS_API_KEY` (and `SHIELDLABS_API_BASE_URL` when set), sends its requests with
`cache: 'no-store'`, and rejects with a `ValidationError` when the key is missing. Never wrap it in
a data cache: polling must see fresh answers.

### Server Actions

A Server Action (`'use server'`, for example `app/signup/actions.ts`) runs the same code as the
`POST` handler above: `getIdentification(input.identificationId)` in a `try`, the claim, then
`evaluateIdentification`, returning `{ ok }` instead of a `Response`. The client component calls
it after `identify()`:
`const { ok } = await signup({ email: String(email), identificationId: result?.identificationId ?? null });`.

### Early identification and consent

The provider and hooks are those of `@shieldlabs-ai/react` ([react.md](react.md)):

- To have the identification ready at submit time, arm the form in an effect with
  `useShieldLabs().getAgent()` and `agent.identifyOnInteraction(form)`, then call `take()` in the
  submit handler, as in [react.md](react.md#identify-earlier-start-on-the-first-interaction).
- Where consent is required, render `<ShieldLabsProvider publicKey={...} autoLoad={false}>` in the
  root layout and call `load()` from `useShieldLabs()` in a client component once the user agrees
  (or pass `autoLoad={consentGiven}` when the layout knows the choice). Until then `identify()`
  from `useIdentify()` resolves `null` at once with a `not_initialized` error, so forms go out
  unverified; a `runOnMount` identification ends the same way and does not run again after
  `load()`.

### Webhook route handler

```ts
// app/api/webhooks/shieldlabs/route.ts
import { createWebhookHandler } from '@shieldlabs-ai/next/server';

export const POST = createWebhookHandler({
  // Verifies X-Shield-Signature with SHIELDLABS_WEBHOOK_SECRET (several secrets separated by
  // commas while you rotate one). webhook.ping is acknowledged and never reaches onEvent.
  onEvent: async (event) => {
    if (event.event_type !== 'identification.scored') return; // a newer event type: acknowledge it
    await jobs.enqueueOnce(event.raw.event_id as string, event.raw); // atomic durable acceptance
  },
});
```

| Answer | When |
|---|---|
| 200 | `onEvent` resolved, or the event is a `webhook.ping` |
| 400 | The signature is valid, but the body is not a ShieldLabs event |
| 401 | The signature header is missing, malformed or matches no secret |
| 405 | Another method than `POST` |
| 413 | The body is larger than `maxBodySize` (default 1 MiB; a delivery is about 2 KB) |
| 500 | `onEvent` threw, or no signing secret is configured |

The handler reads the raw body only when the signature header is well formed. Keep `onEvent`
short and durably enqueue before acknowledging; sender/probe timeout budgets vary. `onError(error, { request,
status })` is called before a 400, 401, 413 or 500. More in the shieldlabs-webhooks skill.

## Pages Router

```tsx
// pages/_app.tsx
import type { AppProps } from 'next/app';
import { ShieldLabsProvider } from '@shieldlabs-ai/next';

export default function App({ Component, pageProps }: AppProps) {
  return (
    <ShieldLabsProvider publicKey={process.env.NEXT_PUBLIC_SHIELDLABS_PUBLIC_KEY!}>
      <Component {...pageProps} />
    </ShieldLabsProvider>
  );
}
```

Pages call `useIdentify()` from `@shieldlabs-ai/next` exactly as in the App Router form above. API
routes read the verdict with `getIdentification` from `@shieldlabs-ai/next/server`:

```ts
// pages/api/signup.ts
import type { NextApiRequest, NextApiResponse } from 'next';
import { ShieldLabsError, evaluateIdentification, getIdentification, type Identification } from '@shieldlabs-ai/next/server';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end();
  const identificationId = typeof req.body?.identificationId === 'string' ? req.body.identificationId : '';
  let identification: Identification | null = null;
  if (identificationId) {
    try {
      identification = await getIdentification(identificationId);
    } catch (error) {
      if (!(error instanceof ShieldLabsError)) throw error;
    }
  }
  const firstUse = identification ? await claimRequestId(identification.identification_id) : false;
  const verdict = evaluateIdentification(identification, { isReplay: () => !firstUse });
  if (!verdict.ok) return res.status(403).json({ error: 'signup_refused' });
  return res.status(201).json({ ok: true });
}
```

A webhook in the Pages Router needs the raw body, so turn off the body parser for that route and
verify with `webhooks.constructEvent` of `@shieldlabs-ai/node`:

```ts
// pages/api/webhooks/shieldlabs.ts
import type { NextApiRequest, NextApiResponse } from 'next';
import { SignatureVerificationError, webhooks, type WebhookEvent } from '@shieldlabs-ai/node';

export const config = { api: { bodyParser: false } };

const MAX_BODY_SIZE = 1024 * 1024; // a delivery is about 2 KB

/** The raw body, or null when it is larger than MAX_BODY_SIZE. */
async function readRawBody(req: NextApiRequest): Promise<Buffer | null> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    const bytes = typeof chunk === 'string' ? Buffer.from(chunk) : (chunk as Buffer);
    size += bytes.length;
    if (size > MAX_BODY_SIZE) return null;
    chunks.push(bytes);
  }
  return Buffer.concat(chunks);
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end();
  const secrets = (process.env.SHIELDLABS_WEBHOOK_SECRET ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  if (secrets.length === 0) return res.status(500).end(); // not configured: never a 401
  const body = await readRawBody(req);
  if (body === null) return res.status(413).end();
  let event: WebhookEvent;
  try {
    event = webhooks.constructEvent(body, req.headers['x-shield-signature'], secrets);
  } catch (error) {
    return res.status(error instanceof SignatureVerificationError ? 401 : 400).end();
  }
  if (event.event_type === 'identification.scored') await jobs.enqueueOnce(event.raw.event_id as string, event.raw);
  return res.status(200).json({ received: true });
}
```

## Edge runtime and middleware

`getIdentification`, `createWebhookHandler` and `userHidAsync` from `@shieldlabs-ai/next/server` work
in the Edge runtime (`export const runtime = 'edge'`) as well as in Node.js. The synchronous
`userHid` of `@shieldlabs-ai/node` needs Node.js crypto, so the server entry offers only the async
helper. When you host the app yourself with `next start`, keep the webhook route in the Node.js
runtime: an Edge route handler runs only after Next.js has read the whole body, so `maxBodySize`
cannot keep a large request out of memory there. Middleware runs on the server, so it never
identifies: identification always starts in the browser.

## Signed-in users

Compute the User HID in a Server Component, Server Action or route with `userHidAsync` from
`@shieldlabs-ai/next/server` (Node.js and Edge runtimes), pass it to the client component as a prop,
and call `useIdentify({ userId: userHid })` (shieldlabs-user-linking skill):

```tsx
// app/account/page.tsx (a Server Component)
import { userHidAsync } from '@shieldlabs-ai/next/server';
import { ChangeEmailForm } from './change-email-form'; // 'use client', calls useIdentify({ userId: userHid })

export default async function AccountPage() {
  const session = await getSession(); // your authentication
  const userHid = await userHidAsync(String(session.user.id), process.env.USER_HID_SECRET!);
  return <ChangeEmailForm userHid={userHid} />;
}
```

The Server Action behind the form checks `identification.user_hid` against the same value.

## Content Security Policy

Merge the ShieldLabs origins (see [../SKILL.md](../SKILL.md)) into the policy you already send
from `next.config.js` `headers()` or from middleware. The agent is loaded with a dynamic `import()`
from `https://cdn.shieldlabs.ai`, so that origin belongs in `script-src`.
