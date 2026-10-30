/** Runtime checks against installed public SDKs and the actual documented policy.
 * SHIELDLABS_SDK_QA_DIR points to a disposable npm prefix containing
 * @shieldlabs-ai/node@1.3.2, @shieldlabs-ai/js@1.1.0 and typescript.
 */
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import vm from 'node:vm';
const root = fileURLToPath(new URL('../', import.meta.url));
const qa = process.env.SHIELDLABS_SDK_QA_DIR;
assert.ok(qa, 'Set SHIELDLABS_SDK_QA_DIR to a clean npm install prefix');
const require = createRequire(join(qa, 'package.json'));
const sdk = await import(pathToFileURL(require.resolve('@shieldlabs-ai/node')));
const ts = require('typescript');
assert.equal(sdk.VERSION, '1.3.2');
const domainId = '11111111-1111-4111-8111-111111111111';
const id = '33333333-3333-4333-8333-333333333333';
const user = sdk.userHid('account-7', 'a-private-test-secret');
assert.match(user, /^[a-f0-9]{64}$/);
const card = {
  type: 'identification', id, domain_id: domainId, domain: 'example.com',
  risk: { state: 'ok', score: 15, band: 'trusted', as_of: new Date().toISOString() },
  signals: { state: 'ok', items: ['vpn'] }, created_at: new Date().toISOString(),
  device_id: '44444444-4444-4444-8444-444444444444', user_hid: user,
};
const urls = [];
const client = new sdk.ShieldLabs({
  apiKey: 'sec_test0000-test0000-test0000', maxRetries: 0,
  fetch: async (url, init) => {
    urls.push(new URL(url));
    assert.equal(init.headers.Authorization, 'Bearer sec_test0000-test0000-test0000');
    const pathname = new URL(url).pathname;
    let body = { data: card };
    if (pathname.endsWith('/domains')) body = { domains: [{ id: domainId, domain: 'example.com' }] };
    else if (pathname.endsWith('/identifications')) body = { data: [card], next_page_token: 'next-opaque' };
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
  },
});
assert.deepEqual(await client.entities.domains(), [{ id: domainId, domain: 'example.com' }]);
const result = await client.identifications.get(id, { domainId, wait: false });
assert.equal(result.identification_id, id);
assert.equal(result.raw.domain_id, domainId);
assert.equal(result.risk_score, 15);
assert.equal(result.detection_flags.vpn, true);
assert.equal(Object.keys(result.detection_flags).length, 20);
assert.ok('banned_ip' in result.detection_flags);
const page = await client.entities.list(domainId, 'identifications', {
  limit: 20, risk_bands: ['suspicious', 'dangerous'], is_proxy: false,
  risk_signals: ['vpn', 'banned_ip'], banned_ip: true,
});
assert.equal(page.next_page_token, 'next-opaque');
assert.deepEqual(urls.at(-1).searchParams.getAll('risk_bands'), ['suspicious', 'dangerous']);
assert.equal(urls.at(-1).searchParams.get('is_proxy'), 'false');
assert.equal(urls.at(-1).searchParams.get('banned_ip'), 'true');
await client.entities.get(domainId, 'identifications', id);
assert.equal(urls.at(-1).pathname, `/api/v1/domains/${domainId}/history/identifications/${id}`);
const sent = urls.length;
await assert.rejects(() => client.identifications.get(id), sdk.ValidationError);
await assert.rejects(() => client.entities.list(domainId, 'identifications', { rate_limited: true }), sdk.ValidationError);
await assert.rejects(() => client.entities.list(domainId, 'identifications', { filter: {} }), sdk.ValidationError);
await assert.rejects(() => client.history.search('user_hid', user), sdk.ValidationError);
assert.equal(urls.length, sent);
const unavailable = { ...card, risk: { state: 'unavailable', band: null, as_of: null }, signals: { state: 'unavailable', items: [] } };
assert.deepEqual(sdk.parseHistoryEntity(unavailable).risk, unavailable.risk);
const unknown = sdk.fromHistoryRow(unavailable);
assert.ok(!Number.isFinite(unknown.risk_score));
// Preserve missing-card and transport states exactly; do not infer billing from not_found.
const responseClient = (status, body, contentType = 'application/json') => new sdk.ShieldLabs({
  apiKey: 'sec_test0000-test0000-test0000', maxRetries: 0,
  fetch: async () => new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status, headers: { 'Content-Type': contentType },
  }),
});
assert.equal(await responseClient(404, { error: 'not_found' }).identifications.get(id, { domainId, timeout: 0 }), null);
await assert.rejects(() => responseClient(404, 'Not found', 'text/plain').identifications.get(id, { domainId, wait: false }), sdk.NotFoundError);
await assert.rejects(() => responseClient(429, { error: 'rate_limited' }).identifications.get(id, { domainId, wait: false }),
  (error) => error instanceof sdk.RateLimitError && error.body.error === 'rate_limited');
await assert.rejects(() => responseClient(402, { error: 'billing_state_unavailable' }).identifications.get(id, { domainId, wait: false }),
  (error) => error instanceof sdk.QuotaExceededError && error.body.error === 'billing_state_unavailable');
// Execute the exact policy code a customer agent reads, rather than a copied test implementation.
const text = await readFile(join(root, 'skills/shieldlabs-risk-decisions/SKILL.md'), 'utf8');
const code = text.match(/```ts\n([\s\S]*?)```/)[1];
const output = ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const policyPath = join(qa, 'documented-policy.mjs');
await writeFile(policyPath, output);
const { decide } = await import(pathToFileURL(policyPath));
assert.deepEqual(decide(result, 'high', { firstUse: true, expectedUserHid: user }), { decision: 'allow', reason: 'band_trusted' });
assert.equal(decide(result, 'high', { firstUse: false }).decision, 'block');
assert.equal(decide(result, 'high', { firstUse: true, expectedUserHid: 'different' }).decision, 'block');
assert.equal(decide(unknown, 'high', { firstUse: true }).decision, 'review');
assert.equal(decide({ ...result, raw: { ...card, signals: { state: 'unavailable', items: [] } } }, 'medium', { firstUse: true }).decision, 'step_up');
assert.equal(decide({ ...result, observed_at: new Date(Date.now() - 600_000).toISOString() }, 'high', { firstUse: true }).reason, 'stale');
// Execute the published IIFE with a controlled agent module and verify the real return shape.
const module = new vm.SyntheticModule(['checkAnonymous', 'checkAuthenticatedUser', 'forceCheckAnonymous', 'forceCheckAuthenticatedUser'], function () {
  this.setExport('checkAnonymous', ({ onInitialized }) => onInitialized({ status: 'skipped' }));
  this.setExport('forceCheckAnonymous', ({ onInitialized }) => onInitialized({ status: 'initialized', requestID: id }));
  this.setExport('checkAuthenticatedUser', (_hid, { onInitialized }) => onInitialized({ status: 'initialized', requestID: id }));
  this.setExport('forceCheckAuthenticatedUser', (_hid, { onInitialized }) => onInitialized({ status: 'initialized', requestID: id }));
});
await module.link(() => {}); await module.evaluate();
const context = vm.createContext({ window: { isSecureContext: true, location: { protocol: 'https:', hostname: 'example.com' } }, document: {}, URL, console, setTimeout, clearTimeout });
const iife = await readFile(join(qa, 'node_modules/@shieldlabs-ai/js/dist/shieldlabs.iife.js'), 'utf8');
new vm.Script(iife, { importModuleDynamically: async (url) => { assert.equal(new URL(url).origin, 'https://cdn.shieldlabs.ai'); return module; } }).runInContext(context);
const agent = await context.ShieldLabsJS.load({ publicKey: '0123456789abcdef0123456789abcdef' });
const browser = await agent.identify();
assert.equal(browser.identificationId, id);
assert.equal(browser.requestId, undefined);
assert.equal(await agent.check(), null);
const linked = await agent.check({ userId: user });
assert.equal(linked.identificationId, id); assert.equal(linked.userId, user);
console.log('Current SDK examples passed: Node1.3 entity reads, flat filters, 20 flags, retired-input rejection, exact policy, JS1.1 IIFE identify/check/User HID.');
