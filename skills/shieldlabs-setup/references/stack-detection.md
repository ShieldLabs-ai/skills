# Stack detection

`scripts/detect_stack.py` automates this. Without Python, read the manifests yourself with the
rules below.

## Frontend (browser package)

Check `package.json` (`dependencies`, `devDependencies`) and take the first match:

| Order | Dependency | Framework | Install |
|---|---|---|---|
| 1 | `next` | Next.js (an `app/` folder: App Router; `pages/`: Pages Router) | `@shieldlabs-ai/next @shieldlabs-ai/react @shieldlabs-ai/js@1.1.0 @shieldlabs-ai/node` |
| 2 | `nuxt` | Nuxt 3 | `@shieldlabs-ai/vue @shieldlabs-ai/js@1.1.0` |
| 3 | `@sveltejs/kit` | SvelteKit | `@shieldlabs-ai/svelte @shieldlabs-ai/js@1.1.0` |
| 4 | `@angular/core` | Angular | `@shieldlabs-ai/angular @shieldlabs-ai/js@1.1.0` |
| 5 | `svelte` | Svelte | `@shieldlabs-ai/svelte @shieldlabs-ai/js@1.1.0` |
| 6 | `vue` | Vue | `@shieldlabs-ai/vue @shieldlabs-ai/js@1.1.0` |
| 7 | `react` | React (Vite, React Router, Remix) | `@shieldlabs-ai/react @shieldlabs-ai/js@1.1.0` |
| 8 | none of these | Plain JavaScript, server-rendered pages, or static HTML (`index.html`, `public/index.html`, `static/index.html`) | `@shieldlabs-ai/js@1.1.0` (npm, or the IIFE build without a bundler) |

Use the lock file for the command: `pnpm-lock.yaml` means `pnpm add`, `yarn.lock` means
`yarn add`, `bun.lock` or `bun.lockb` means `bun add`, otherwise `npm install`.

Server-rendered apps (Django or Jinja templates, Laravel Blade, Rails, Razor, Express views) and
static HTML served by a backend use `@shieldlabs-ai/js`: with their asset bundler when they have one,
otherwise the IIFE build. The server writes the Public Key and, for signed-in users, the User HID
into the page ([environment.md](environment.md#static-pages) shows it for static HTML).

## Backend (server SDK)

| Manifest | Look for | Server SDK |
|---|---|---|
| `package.json` | `express`, `fastify`, `koa`, `hono`, `@nestjs/core`, or a full-stack framework (`next`, `nuxt`, `@sveltejs/kit`, Remix) | `@shieldlabs-ai/node` (Next.js server routes: direct `@shieldlabs-ai/node@1.3.0`) |
| `pyproject.toml`, `requirements*.txt`, `Pipfile`, `setup.py`, `setup.cfg` | `django`, `fastapi`, `flask`, `starlette`, other web frameworks | `shieldlabs` (PyPI) |
| `go.mod` | the module; `gin`, `echo`, `fiber`, `chi` or plain `net/http` | `github.com/ShieldLabs-ai/shieldlabs-go` |
| `composer.json` | `laravel/framework`, `symfony/framework-bundle`, `slim/slim` | `shieldlabs/shieldlabs-php` |
| `pom.xml`, `build.gradle`, `build.gradle.kts` | `spring-boot`, Quarkus, Micronaut, Ktor | `ai.shieldlabs:shieldlabs-java` (also from Kotlin) |
| `*.csproj` | `Sdk="Microsoft.NET.Sdk.Web"` (ASP.NET Core) | `ShieldLabs` (NuGet) |

For a backend in another language, follow
[other-languages.md](../../shieldlabs-server/references/other-languages.md) of the shieldlabs-server
skill.

## Monorepos and split deployments

- Plan per app: `apps/web` gets the browser package, `apps/api` the server SDK.
- When the browser app and the API run on different origins, the request ID travels in the API
  request body like any other field; configure CORS for that route as usual.
- The Public Key belongs to the domain the **pages** run on. Identifications from a page served on
  another registered domain need that domain's Public Key, and its Private API Key reads them.

## Existing ShieldLabs code

Look for `@shieldlabs-ai/*` packages, `cdn.shieldlabs.ai` URLs, `window.Shield` and calls such as
`checkAnonymous`, `checkAuthenticatedUser`, `forceCheckAnonymous` and
`forceCheckAuthenticatedUser`. A project that loads the agent module directly can keep working, but
the browser SDK adds timeouts, option validation and SSR safety. When the user wants to move to it:

| Direct agent call | Browser SDK |
|---|---|
| `forceCheckAnonymous({ onInitialized })` at a protected action | `identify()` |
| `forceCheckAuthenticatedUser(hid, { onInitialized })` | `identify({ userId: hid })` |
| `checkAnonymous()` on page load | `check()` or `checkOnLoad: true` |
| `checkAuthenticatedUser(hid)` on signed-in pages | `check({ userId: hid })` or `checkOnLoad: { userId: hid }` |
| `result.requestID` in `onInitialized` | `(await identify()).identificationId` |

Keep one setup: remove the old script tag or import when the SDK takes over, so the agent loads
once.
