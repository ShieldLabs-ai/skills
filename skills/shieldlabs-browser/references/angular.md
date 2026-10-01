# Angular with `@shieldlabs-ai/angular`

Angular 17 or later: standalone and NgModule applications, zone-based and zoneless, Angular SSR
and hydration. The package exposes functions, not services: `provideShieldLabs()`,
`injectShieldLabs()` and `injectIdentify()`.

## Install

```bash
npm install @shieldlabs-ai/angular @shieldlabs-ai/js
```

## Provide once

Add the provider next to the providers the application already has:

```ts
// src/app/app.config.ts
import { ApplicationConfig } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { provideShieldLabs } from '@shieldlabs-ai/angular';
import { environment } from '../environments/environment';

export const appConfig: ApplicationConfig = {
  providers: [
    // ...existing providers
    provideHttpClient(), // skip when the app already provides HttpClient
    provideShieldLabs({ publicKey: environment.shieldlabsPublicKey }),
  ],
};
```

In an NgModule application, put `provideShieldLabs({ ... })` in the root module's `providers`.
Options: `publicKey` (required), `environment`, `scriptUrl`, `timeout` (milliseconds, default
`10000`: the time a call without its own `timeout` may take in all, and the load limit),
`checkOnLoad` (`false` by default; `true` or `{ userId }` runs one `check()` when the agent becomes
ready), `autoLoad` (`true` by default: the agent loads after the first render in the browser, or
on an earlier call; `false` loads nothing until `load()`, see [Consent](#consent)).

The Public Key can also come from the CLI `define` option, for example
`ng build --define "SHIELDLABS_PUBLIC_KEY='0123456789abcdef0123456789abcdef'"` with
`declare const SHIELDLABS_PUBLIC_KEY: string;` in a `.d.ts` file. Register a separate domain with
its own keys for development and staging.

## Identify on submit

```ts
// src/app/signup-form.ts
import { HttpClient } from '@angular/common/http';
import { Component, inject } from '@angular/core';
import { injectIdentify } from '@shieldlabs-ai/angular';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'app-signup-form',
  template: `
    <form (submit)="submit($event)">
      <input name="email" type="email" required />
      <button [disabled]="identification.isLoading()">Sign up</button>
    </form>
  `,
})
export class SignupForm {
  private readonly http = inject(HttpClient);
  protected readonly identification = injectIdentify();

  protected async submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const email = new FormData(event.target as HTMLFormElement).get('email');
    // null when there is no identification: send the signup anyway, the server treats it as unverified.
    const result = await this.identification.identify();
    await firstValueFrom(this.http.post('/api/signup', { email, requestId: result?.requestId ?? null }));
  }
}
```

In Angular 17 and 18, add `standalone: true` to the component. `injectIdentify({ userId?,
runOnMount? })` must run in an injection context (a field initializer or the constructor). It
returns `{ result, isLoading, error, identify, reset }`: signals plus `identify(options?)`, which
resolves `{ requestId, userId }`, or `null` with the `ShieldLabsError` in `error()`, and never
rejects. While a call of the same helper with the same User HID and the same effective timeout
runs, `identify()` returns that call, so a double click creates one identification; a call without
`timeout` counts as one with the provider's. The call's `timeout` (else the provider's, else 10
seconds) covers the wait for the agent and its answer.

## Signed-in users

`userId` accepts a string, or a signal (or any function) read when `identify()` runs:

```ts
export class CheckoutForm {
  private readonly session = inject(SessionStore); // your own service; userHid computed on the server
  protected readonly identification = injectIdentify({ userId: this.session.userHid }); // Signal<string | null>
}
```

`null` or `undefined` means anonymous. The options of one `identify()` call override the helper's
`userId` whenever they have the `userId` key, even with the value `undefined` or `null`:
`identify({ userId: undefined })` runs one anonymous call, and only a call without the `userId` key
uses the helper's User HID.

## Start the identification early

To have the identification finished by the time the user submits, arm the form after the first
render with `identifyOnInteraction(form)` of the agent from `getAgent()`:

```ts
// src/app/signup-form.ts
import { HttpClient } from '@angular/common/http';
import { afterNextRender, Component, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { injectShieldLabs, type InteractionIdentifier } from '@shieldlabs-ai/angular';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'app-signup-form',
  template: `
    <form #form (submit)="submit($event)">
      <input name="email" type="email" required />
      <button [disabled]="submitting()">Sign up</button>
    </form>
  `,
})
export class SignupForm {
  private readonly http = inject(HttpClient);
  private readonly shieldlabs = injectShieldLabs();
  private readonly form = viewChild.required<ElementRef<HTMLFormElement>>('form');
  private early: Promise<InteractionIdentifier> | undefined;
  protected readonly submitting = signal(false);

  constructor() {
    afterNextRender(() => {
      // Starts an identification on the first focus, click or key press in the form.
      this.early = this.shieldlabs.getAgent().then((agent) => agent.identifyOnInteraction(this.form().nativeElement));
      this.early.catch(() => undefined); // no agent: submit() sends the signup as unverified
    });
    inject(DestroyRef).onDestroy(() => {
      void this.early?.then((early) => early.dispose(), () => undefined);
    });
  }

  protected async submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (this.submitting()) return;
    this.submitting.set(true);
    const email = new FormData(event.target as HTMLFormElement).get('email');
    // take(): the identification started by the first interaction while it is fresh, or a new one.
    const result = await this.early?.then((early) => early.take()).catch(() => null);
    try {
      await firstValueFrom(this.http.post('/api/signup', { email, requestId: result?.requestId ?? null }));
    } finally {
      this.submitting.set(false);
    }
  }
}
```

`take()` never reuses an identification that failed or finished more than four minutes ago, and
it re-arms the form for the next submission. An identification started by an interaction is
billable even when the user leaves without submitting. With `autoLoad: false`, `getAgent()` waits
for `load()`, so the form is armed only once the agent may load.

## Agent state

```ts
import { Component } from '@angular/core';
import { injectShieldLabs } from '@shieldlabs-ai/angular';

@Component({
  selector: 'app-agent-status',
  template: `
    @if (shieldlabs.status() === 'error') {
      <p>Device check unavailable ({{ shieldlabs.error()?.code }}). You can continue.</p>
    }
  `,
})
export class AgentStatus {
  protected readonly shieldlabs = injectShieldLabs();
}
```

`injectShieldLabs()` returns `{ status, error, identify, check, load, getAgent }`: `status` and
`error` are signals; `identify()` rejects with a `ShieldLabsError`; `check()` resolves `null` when
the agent skipped it; `load()` starts loading the agent; `getAgent()` resolves the agent of
`@shieldlabs-ai/js`, whose calls run outside the Angular zone, and rejects with the load error when
the load fails or times out. Outside an injection context, wrap the call in
`runInInjectionContext(injector, () => injectIdentify())`. Without `provideShieldLabs()` in scope,
both functions throw a `ShieldLabsError` with the code `invalid_options`.

## `runOnMount` and `checkOnLoad`

- `injectIdentify({ runOnMount: true })` calls `identify()` once after the component first renders
  in the browser. A component created again (its route visited again) runs it again. Use it only
  where viewing the page is the protected action. With `autoLoad: false`, a run that starts before
  `load()` resolves `null` with `not_initialized` and does not run again after `load()`. When the
  load fails or times out, the run resolves `null` with the load error and does not run again when
  the agent arrives later.
- `provideShieldLabs({ publicKey, checkOnLoad: true })` (or `{ userId }`) runs one background
  `check()` when the agent is ready, unless an `identify()` or `check()` for the same user is still
  running. An `identify()` that starts while that check still runs can get `not_initialized`: keep
  `checkOnLoad` for pages without a protected action, or retry once.

## Consent

```ts
provideShieldLabs({ publicKey: environment.shieldlabsPublicKey, autoLoad: false });
```

Nothing loads until `load()` of `injectShieldLabs()` is called, for example in the accept handler of
the consent banner, or at startup (in the constructor of the root component) when consent is
already stored. Until then nothing waits for it: `identify()` rejects at once with
`not_initialized`, `injectIdentify().identify()` resolves `null` with that error (so a protected
action goes ahead unverified), a `runOnMount` identification ends the same way and does not run
again after `load()`, `check()` resolves `null`, `getAgent()` waits for `load()`, and `status`
stays `'loading'`. `checkOnLoad` runs once the agent is ready after `load()`.

## SSR and hydration

Nothing loads on the server. During server rendering `status` stays `'loading'`, `runOnMount`,
`checkOnLoad` and `load()` do nothing, `injectIdentify().identify()` resolves `null`, and
`identify()`, `check()` and `getAgent()` of `injectShieldLabs()` reject with
`unsupported_environment` without changing any signal. The agent and its timers run outside the
Angular zone, so they neither trigger change detection nor keep the app from becoming stable.

## Unit tests

TestBed does not use the application config: add `provideShieldLabs({ publicKey, autoLoad: false })`
to the spec's providers, so that nothing loads from the CDN unless a test calls `load()`. To test
what a component does with the result, mock `@shieldlabs-ai/angular` itself (with `vi.mock` or
`jest.mock`) and return an `injectIdentify` whose `identify` resolves a fixed
`{ requestId, userId: null }`, or `null` for the unverified path. A mock of `@shieldlabs-ai/js` does
not reach the import inside `@shieldlabs-ai/angular` under the Angular CLI test runner.
