import type { IdentifyResult } from '@shieldlabs-ai/js';
import { useIdentify as reactIdentify } from '@shieldlabs-ai/react';
import { useIdentify as nextIdentify } from '@shieldlabs-ai/next';
import { useIdentify as vueIdentify } from '@shieldlabs-ai/vue';
import { injectIdentify } from '@shieldlabs-ai/angular';
import { useIdentify as svelteIdentify } from '@shieldlabs-ai/svelte';
import { ShieldLabs, type DetectionFlags } from '@shieldlabs-ai/node';

type ReactResult = NonNullable<Awaited<ReturnType<ReturnType<typeof reactIdentify>['identify']>>>;
type NextResult = NonNullable<Awaited<ReturnType<ReturnType<typeof nextIdentify>['identify']>>>;
type VueResult = NonNullable<Awaited<ReturnType<ReturnType<typeof vueIdentify>['identify']>>>;
type AngularResult = NonNullable<Awaited<ReturnType<ReturnType<typeof injectIdentify>['identify']>>>;
type SvelteResult = NonNullable<Awaited<ReturnType<ReturnType<typeof svelteIdentify>['identify']>>>;
function identificationIds(js: IdentifyResult, react: ReactResult, next: NextResult,
  vue: VueResult, angular: AngularResult, svelte: SvelteResult): string[] {
  // These are the fields used by the actual installation snippets in each framework reference.
  return [js.identificationId, react.identificationId, next.identificationId,
    vue.identificationId, angular.identificationId, svelte.identificationId];
}
declare const result: ReactResult;
// @ts-expect-error JS1.1 and every wrapper now share identificationId rather than requestId.
result.requestId;
const client = new ShieldLabs({ apiKey: 'sec_test0000-test0000-test0000' });
client.identifications.get('33333333-3333-4333-8333-333333333333', { domainId: '11111111-1111-4111-8111-111111111111' });
// @ts-expect-error Domain UUID belongs in read options and is required.
client.identifications.get('33333333-3333-4333-8333-333333333333');
const banned: keyof DetectionFlags = 'banned_ip';
// @ts-expect-error Transport error code is not a normalized detection flag.
const transport: keyof DetectionFlags = 'rate_limited';
void identificationIds; void banned; void transport;
