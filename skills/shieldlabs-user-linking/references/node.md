# User HID in Node.js

`userHid(userId, secret)` from `@shieldlabs-ai/node` returns HMAC-SHA256 as 64 lowercase hex
characters and throws `ValidationError` on empty input. It needs Node.js crypto; in edge runtimes
(Cloudflare Workers, Vercel Edge, Next.js `runtime = 'edge'`) use `await userHidAsync(userId, secret)`.

```ts
// user-hid.ts
import { userHid } from '@shieldlabs-ai/node';

const secret = process.env.USER_HID_SECRET ?? '';
if (!secret) throw new Error('USER_HID_SECRET is not set');

export function userHidFor(user: { id: string | number }): string {
  return userHid(String(user.id), secret);
}
```

## Server-rendered pages (Express)

```ts
app.get('/checkout', requireLogin, (req, res) => {
  res.render('checkout', { userHid: userHidFor(req.user) });
});
```

```html
<!-- checkout.ejs -->
<form id="checkout" data-user-hid="<%= userHid %>">...</form>
```

The page script passes `form.dataset.userHid || undefined` to `identify({ userId })`: for a visitor who is not signed in the attribute is empty, and an empty `userId` is rejected with `invalid_options`, while `undefined` runs an anonymous identification.

## Single-page apps: a session endpoint

```ts
app.get('/api/session', (req, res) => {
  if (!req.user) return res.json({ user: null });
  return res.json({ user: { name: req.user.name, userHid: userHidFor(req.user) } });
});
```

The app keeps `userHid` with its session state and passes it to the hooks, for example
`useIdentify({ userId: session.user?.userHid })`.

## Next.js

`@shieldlabs-ai/next/server` exports `userHidAsync`, which works in Server Components, Server Actions
and route handlers, in the Node.js and Edge runtimes:

```tsx
// app/checkout/page.tsx (a Server Component)
import { userHidAsync } from '@shieldlabs-ai/next/server';
import { CheckoutForm } from './checkout-form'; // 'use client', calls useIdentify({ userId: userHid })

export default async function CheckoutPage() {
  const session = await getSession(); // your auth library
  const hid = session ? await userHidAsync(String(session.user.id), process.env.USER_HID_SECRET!) : undefined;
  return <CheckoutForm userHid={hid} />;
}
```

## SvelteKit

```ts
// src/routes/+layout.server.ts
import { USER_HID_SECRET } from '$env/static/private';
import { userHid } from '@shieldlabs-ai/node';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = ({ locals }) => ({
  userHid: locals.user ? userHid(String(locals.user.id), USER_HID_SECRET) : undefined,
});
```

## Check it on the server

```ts
const expected = userHidFor(req.user);
if (identification && identification.user_hid !== expected) {
  // treat as unverified: another account's identification, or an anonymous one
}
```

## Read the account's History card

Read the `user` card with the exact generated HID, in the selected public domain UUID.
Preserve risk, signals, High-Risk Events and nullable related counts. Fetch additional cards
only when their IDs are known. Use the application database for its account/device associations.
See [current History](../../shieldlabs-server/references/current-history.md) and the
[account-abuse workflow](../../shieldlabs-account-abuse/references/high-risk-events.md).

```ts
const card = await shieldlabs.entities.get(process.env.SHIELDLABS_DOMAIN_ID!, "user", userHidFor(user));
// No numeric score is required for an aggregate card. Read its returned band only when available.
```
