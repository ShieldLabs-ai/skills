# Keys and environment variables

These variables are for the application SDKs. The hosted MCP uses client OAuth and needs none
of them in its configuration. Keep application keys when migrating an old local MCP connection.

Domains can be configured through OAuth MCP or the ShieldLabs dashboard. For a new domain,
`shieldlabs_add_domain` returns the public key; an installer may request the needed one-time
server credential with `include_secret=true` and store it privately. Existing secrets stay masked.
Do not rotate to recover a missing key without explicit approval.

Every domain registered in the dashboard (https://app.shieldlabs.ai, Integration >
Domains) has its own keys under Integration > API keys. Each webhook endpoint has its own signing
secret under Integration > Webhooks.

| Variable | Holds | Where it lives |
|---|---|---|
| `SHIELDLABS_PUBLIC_KEY`, with the framework's public prefix (`VITE_`, `NEXT_PUBLIC_`, `NUXT_PUBLIC_`, `PUBLIC_`) | Public Key, 32 hex characters | Browser code (public by design) |
| `SHIELDLABS_API_KEY` | Private API Key, `sec_xxxxxxxx-xxxxxxxx-xxxxxxxx` | Server only |
| `SHIELDLABS_WEBHOOK_SECRET` | Endpoint signing secret, `whsec_...`; several comma-separated while rotating | Server only |
| `USER_HID_SECRET` | Your own random secret for User HIDs (`openssl rand -hex 32`) | Server only |
| `SHIELDLABS_SECRET_KEY`, `SHIELDLABS_DOMAIN` | Secret Key and registered domain, for the Management API (optional) | Server only |
| `SHIELDLABS_API_BASE_URL`, `SHIELDLABS_MANAGEMENT_BASE_URL` | Origin overrides for tests against a local mock (optional) | Server only |

## `.env.example`

Commit placeholders only, one comment line per group (some `.env` parsers do not support comments
after a value):

```bash
# ShieldLabs: analytics dashboard > Integration > API keys
# Browser: use your framework's public prefix (VITE_, NEXT_PUBLIC_, NUXT_PUBLIC_ or PUBLIC_)
VITE_SHIELDLABS_PUBLIC_KEY=0123456789abcdef0123456789abcdef
# Server only: never give these a public prefix
SHIELDLABS_API_KEY=sec_your_private_key
SHIELDLABS_WEBHOOK_SECRET=whsec_your_signing_secret
USER_HID_SECRET=replace_with_the_output_of_openssl_rand_hex_32
```

With separate frontend and backend folders, each tool reads `.env` files from its own root: Vite
from the folder of its config (or its `envDir`), the backend from where it starts. Put
`VITE_SHIELDLABS_PUBLIC_KEY` in `frontend/.env.example` and the server keys in
`backend/.env.example`.

Make sure `.gitignore` keeps real values out of git:

```gitignore
.env
.env.*
!.env.example
```

When a real key was ever committed, rotate it in the analytics dashboard: removing the file does
not remove it from the history.

## Public Key per framework

| Framework | Define | Read |
|---|---|---|
| Vite (React, Vue, Svelte, plain) | `VITE_SHIELDLABS_PUBLIC_KEY` in `.env` | `import.meta.env.VITE_SHIELDLABS_PUBLIC_KEY` |
| Next.js | `NEXT_PUBLIC_SHIELDLABS_PUBLIC_KEY` in `.env.local` (inlined at build time) | `process.env.NEXT_PUBLIC_SHIELDLABS_PUBLIC_KEY` |
| Nuxt | `runtimeConfig.public.shieldlabsPublicKey`, set by `NUXT_PUBLIC_SHIELDLABS_PUBLIC_KEY` | `useRuntimeConfig().public.shieldlabsPublicKey` |
| SvelteKit | `PUBLIC_SHIELDLABS_PUBLIC_KEY` in `.env` | `import { PUBLIC_SHIELDLABS_PUBLIC_KEY } from '$env/static/public'` |
| Angular | `shieldlabsPublicKey` in `src/environments/environment*.ts`, or the CLI `define` option | `environment.shieldlabsPublicKey` |
| Server-rendered and static pages | `SHIELDLABS_PUBLIC_KEY` on the server | the server writes it into the page ([Static pages](#static-pages)) |

`VITE_` and `NEXT_PUBLIC_` values are copied into the JavaScript when the frontend is built: set
them before the build, and build once per environment. A value that only exists at run time never
reaches the page.

### Static pages

For static HTML without a template engine, or when one frontend build must work with the Public
Key of each environment, let the server write the key into the page when it serves `index.html`:

```html
<meta name="shieldlabs-public-key" content="%SHIELDLABS_PUBLIC_KEY%">
```

```js
// Express; Fastify: fastify.get('/', (request, reply) => reply.type('text/html').send(indexHtml))
import { readFileSync } from 'node:fs';

const indexHtml = readFileSync(new URL('./public/index.html', import.meta.url), 'utf8')
  .replace('%SHIELDLABS_PUBLIC_KEY%', process.env.SHIELDLABS_PUBLIC_KEY ?? '');
app.get('/', (req, res) => res.type('html').send(indexHtml));
app.use(express.static('public', { index: false })); // after the route, without its own index.html
```

```js
// In the page, or before rendering the provider of a framework package
const publicKey = document.querySelector('meta[name="shieldlabs-public-key"]')?.getAttribute('content') ?? '';
```

The Public Key is public by design; never write any other ShieldLabs key into a page.

## Server keys

- Read them from the process environment or the platform's secret store (Vercel, Netlify,
  Cloudflare, Fly, Render, Heroku, Kubernetes secrets, AWS or GCP secret managers, CI secrets).
- Load `.env` in development with the framework's own loader or `dotenv`; never read keys from a
  file inside a public or static folder.
- Never log keys, never send them to the browser, never put them in URLs.
- Next.js: never prefix server keys with `NEXT_PUBLIC_`. SvelteKit: read them from
  `$env/static/private` or `$env/dynamic/private`. Vite: never prefix them with `VITE_`.

## Development and staging

Use an authorized development or staging hostname with the registered domain's keys. Inspect
`allow_subdomains` before using a child hostname; do not assume each subdomain needs separate registration. The hosts are the same everywhere.
Identifications from pages on `localhost` are not recorded, even though the page receives a
request ID.

## Check a build for leaked keys

After building the frontend, search the output for server credentials; there must be no match:

```bash
grep -rEl "sec_[a-z0-9]{8}-[a-z0-9]{8}-[a-z0-9]{8}|whsec_[0-9a-f]{32}" dist build .next/static .output/public public static 2>/dev/null
```

Without a build step, search the folder the server serves to browsers.

## Rotation

| Key | Where | After rotating |
|---|---|---|
| Public Key | Integration > API keys, Rotate | Deploy the frontend with the new value |
| Private API Key | Integration > API keys, Rotate | Update `SHIELDLABS_API_KEY`; History calls answer 401 until then |
| Secret Key | Integration > API keys, Rotate | Update `SHIELDLABS_SECRET_KEY` |
| Webhook signing secret | Integration > Webhooks, Rotate secret | Put the new secret first in `SHIELDLABS_WEBHOOK_SECRET` right away; the old one stops working at once |
