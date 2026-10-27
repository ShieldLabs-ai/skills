# Webhooks in Node.js, Next.js and edge runtimes

Use the verified raw envelope for current deliveries. Its `event_id` is the delivery key;
`data.identification_id` correlates the visit. The older typed SDK model can omit these fields.
The application-provided enqueue-once service must reject an empty key and atomically persist
its dedup record and job (transaction/outbox). Roll back on failure and commit before 2xx.
This queue API is application code, not a ShieldLabs SDK method.
Do not enqueue only the old normalized data model.


All examples use `@shieldlabs-ai/node` (or `@shieldlabs-ai/next/server`, which wraps it). They read
`SHIELDLABS_WEBHOOK_SECRET` once at startup, as a comma-separated list while you rotate a secret,
and answer 500 when it is empty:

```ts
const secrets = (process.env.SHIELDLABS_WEBHOOK_SECRET ?? '').split(',').map((s) => s.trim()).filter(Boolean);
if (secrets.length === 0) console.error('SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500');
```


## Express

The Express receiver is in the skill ([The receiver shape](../SKILL.md#the-receiver-shape)).
`constructEvent(payload, header, secret)` takes the payload as a `Buffer`, `Uint8Array`,
`ArrayBuffer` or string, the header as a string or string array, and one secret or a list. It
throws `SignatureVerificationError` (missing, malformed or wrong signature, or no secret) or
`WebhookParseError` (a verified body that is not an event). `webhooks.verifySignature(...)` returns
a boolean instead.

## `node:http`

```ts
import { createServer } from 'node:http';
import { SignatureVerificationError, webhooks, type WebhookEvent } from '@shieldlabs-ai/node';

const MAX_BODY = 1024 * 1024; // a delivery is a few kilobytes

createServer(async (req, res) => {
  if (req.method !== 'POST' || req.url !== '/webhooks/shieldlabs') return res.writeHead(404).end();
  if (secrets.length === 0) return res.writeHead(500).end();
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    size += (chunk as Buffer).length;
    if (size > MAX_BODY) return res.writeHead(413).end();
    chunks.push(chunk as Buffer);
  }
  let event: WebhookEvent;
  try {
    event = webhooks.constructEvent(Buffer.concat(chunks), req.headers['x-shield-signature'], secrets);
  } catch (error) {
    return res.writeHead(error instanceof SignatureVerificationError ? 401 : 400).end();
  }
  if (event.event_type === 'identification.scored') {
    await jobs.enqueueOnce(event.raw.event_id as string, event.raw);
  }
  res.writeHead(200).end(); // after atomic durable acceptance
}).listen(3000);
```

## NestJS

```ts
// main.ts
const app = await NestFactory.create(AppModule, { rawBody: true });
```

```ts
// shieldlabs-webhook.controller.ts
import { BadRequestException, Controller, Headers, HttpCode, InternalServerErrorException, Post, Req, UnauthorizedException, type RawBodyRequest } from '@nestjs/common';
import type { Request } from 'express';
import { SignatureVerificationError, webhooks, type WebhookEvent } from '@shieldlabs-ai/node';

@Controller('webhooks')
export class ShieldLabsWebhookController {
  constructor(private readonly jobs: JobQueue) {} // your queue service

  @Post('shieldlabs')
  @HttpCode(200)
  async receive(@Req() req: RawBodyRequest<Request>, @Headers('x-shield-signature') signature?: string) {
    if (secrets.length === 0) throw new InternalServerErrorException();
    let event: WebhookEvent;
    try {
      event = webhooks.constructEvent(req.rawBody ?? '', signature, secrets);
    } catch (error) {
      if (error instanceof SignatureVerificationError) throw new UnauthorizedException();
      throw new BadRequestException();
    }
    if (event.event_type === 'identification.scored') {
      await this.jobs.enqueue(event.raw);
    }
    return { received: true };
  }
}
```

## Fastify

Keep the raw buffer only for the webhook route by registering the parser in its own scope:

```ts
fastify.register(async (scope) => {
  scope.addContentTypeParser('application/json', { parseAs: 'buffer' }, (_request, body, done) => done(null, body));
  scope.post('/webhooks/shieldlabs', async (request, reply) => {
    if (secrets.length === 0) return reply.code(500).send();
    let event: WebhookEvent;
    try {
      event = webhooks.constructEvent(request.body as Buffer, request.headers['x-shield-signature'], secrets);
    } catch (error) {
      return reply.code(error instanceof SignatureVerificationError ? 401 : 400).send();
    }
    if (event.event_type === 'identification.scored') {
      await jobs.enqueueOnce(event.raw.event_id as string, event.raw);
    }
    return reply.code(200).send();
  });
});
```

## Next.js App Router

```ts
// app/api/webhooks/shieldlabs/route.ts
import { createWebhookHandler } from '@shieldlabs-ai/next/server';

export const POST = createWebhookHandler({
  onEvent: async (event) => {
    if (event.event_type !== 'identification.scored') return;
    await jobs.enqueueOnce(event.raw.event_id as string, event.raw);
  },
  // secret: optional; default SHIELDLABS_WEBHOOK_SECRET, comma-separated while you rotate
  // maxBodySize: optional; default 1 MiB
  // onError: optional; called before answering 400, 401, 413 or 500
});
```

It answers 200 after `onEvent` resolves (and for `webhook.ping`, which never reaches `onEvent`),
401 for a missing or bad signature, 400 for a body that is not an event, 405 for other methods,
413 for a body larger than `maxBodySize`, and 500 when `onEvent` throws or no secret is configured.
It works in the Node.js and Edge runtimes. For the Pages Router, see the shieldlabs-browser skill,
`references/nextjs.md`.

## Edge runtimes (Cloudflare Workers, Vercel Edge, Deno)

Edge builds of `@shieldlabs-ai/node` use WebCrypto, so use the async helpers:

```ts
import { SignatureVerificationError, webhooks, type WebhookEvent } from '@shieldlabs-ai/node';

export default {
  async fetch(request: Request, env: { SHIELDLABS_WEBHOOK_SECRET?: string }, ctx: ExecutionContext): Promise<Response> {
    const secrets = (env.SHIELDLABS_WEBHOOK_SECRET ?? '').split(',').map((s) => s.trim()).filter(Boolean);
    if (secrets.length === 0) return new Response(null, { status: 500 }); // not configured
    const body = new Uint8Array(await request.arrayBuffer());
    let event: WebhookEvent;
    try {
      event = await webhooks.constructEventAsync(body, request.headers.get('x-shield-signature'), secrets);
    } catch (error) {
      return new Response(null, { status: error instanceof SignatureVerificationError ? 401 : 400 });
    }
    if (event.event_type === 'identification.scored') {
      await processOnce(event.raw); // atomic durable enqueue before acknowledging
    }
    return new Response(null, { status: 200 });
  },
};
```

With Hono, read the bytes with `new Uint8Array(await c.req.arrayBuffer())` and the header with
`c.req.header('x-shield-signature')`.

## Typed data

`event.data` is an `Identification`: `request_id`, `visitor_id`, `device_id`, `session_id`,
`cookie_id`, `user_hid` (`string | null`), `domain`, `public_ip` and `local_ip` (`{ ip, country }`),
`connection_type`, `os`, `browser`, `device_type`, `traffic_source`, `risk_score`, `signals`
(`{ name, weight, description: null }`), `detection_flags` (19 booleans), `observed_at`,
`source: 'webhook'` and `raw`. Use `riskBand(event.data.risk_score)` for the band.
