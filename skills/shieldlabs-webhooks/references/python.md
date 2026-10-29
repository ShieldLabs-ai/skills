# Webhooks in Python

Use the verified raw envelope for current deliveries. Its `event_id` is the delivery key;
`data.identification_id` correlates the visit. Use the verified envelope for these identifiers.
The application-provided enqueue-once service must reject an empty key and atomically persist
its dedup record and job (transaction/outbox). Roll back on failure and commit before 2xx.
This queue API is application code, not a ShieldLabs SDK method.
Do not enqueue only the old normalized data model.
Route by the verified raw `event_type`, including `hre.multi_account.changed` even when the SDK
represents it as an unknown event. Validate known current shapes against the bundled
[wire schema](../assets/webhook-event.schema.json) before enqueueing; reject an invalid known
payload with 400. Require a nonempty signed `event_id`. Use the
[High-Risk Event consumer](high-risk-events.md) for the queued group transition.
Queue failures must return a retryable non-2xx; never acknowledge a lost job.



`from shieldlabs import webhooks`. `webhooks.construct_event(payload, signature_header, secret)`
takes the raw body as `bytes` (or `str`), the header value (or `None`), and one secret or a list.
It returns `IdentificationScoredEvent`, `WebhookPingEvent` or `UnknownWebhookEvent`, and raises
`SignatureVerificationError` or `WebhookParseError`. `webhooks.verify_signature(...)` returns a
`bool`. `webhooks.SIGNATURE_HEADER` is `"X-Shield-Signature"`.


```python
import logging
import os
import os

# Several secrets, comma-separated, while you rotate one. Read them once at startup.
WEBHOOK_SECRETS = [s.strip() for s in os.environ.get("SHIELDLABS_WEBHOOK_SECRET", "").split(",") if s.strip()]
if not WEBHOOK_SECRETS:
    logging.getLogger(__name__).error("SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500")
```

Every handler answers 500 while the list is empty: a missing secret is a configuration error, and a
401 would look like a wrong secret.

## FastAPI

```python
from fastapi import FastAPI, Request, Response
from shieldlabs import (
    IdentificationScoredEvent,
    SignatureVerificationError,
    WebhookParseError,
    webhooks,
)

app = FastAPI()


@app.post("/webhooks/shieldlabs")
async def shieldlabs_webhook(request: Request) -> Response:
    if not WEBHOOK_SECRETS:
        return Response(status_code=500)
    payload = await request.body()  # the raw bytes: verify before parsing anything
    try:
        event = webhooks.construct_event(payload, request.headers.get(webhooks.SIGNATURE_HEADER), WEBHOOK_SECRETS)
    except SignatureVerificationError:
        return Response(status_code=401)
    except WebhookParseError:
        return Response(status_code=400)

    if event.raw.get("event_type") in ("identification.scored", "hre.multi_account.changed"):
        await queue.enqueue_once(event.raw["event_id"], dict(event.raw))  # fast; acknowledge promptly after durable acceptance
    return Response(status_code=200)  # webhook.ping and unknown event types: acknowledge
```

## Flask

```python
from flask import Flask, request
from shieldlabs import IdentificationScoredEvent, SignatureVerificationError, WebhookParseError, webhooks

app = Flask(__name__)


@app.post("/webhooks/shieldlabs")
def shieldlabs_webhook():
    if not WEBHOOK_SECRETS:
        return "", 500
    payload = request.get_data()  # raw bytes; do not touch request.json before this
    try:
        event = webhooks.construct_event(payload, request.headers.get(webhooks.SIGNATURE_HEADER), WEBHOOK_SECRETS)
    except SignatureVerificationError:
        return "", 401
    except WebhookParseError:
        return "", 400
    if event.raw.get("event_type") in ("identification.scored", "hre.multi_account.changed"):
        queue.enqueue_once(event.raw["event_id"], dict(event.raw))
    return "", 200
```

## Django

```python
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from shieldlabs import IdentificationScoredEvent, SignatureVerificationError, WebhookParseError, webhooks


@csrf_exempt  # the signature authenticates the request
@require_POST
def shieldlabs_webhook(request):
    if not WEBHOOK_SECRETS:
        return HttpResponse(status=500)
    try:
        event = webhooks.construct_event(request.body, request.headers.get(webhooks.SIGNATURE_HEADER), WEBHOOK_SECRETS)
    except SignatureVerificationError:
        return HttpResponse(status=401)
    except WebhookParseError:
        return HttpResponse(status=400)
    if event.raw.get("event_type") in ("identification.scored", "hre.multi_account.changed"):
        queue.enqueue_once(event.raw["event_id"], dict(event.raw))
    return HttpResponse(status=200)
```

## Event data

`event.data` is an `Identification` (frozen dataclass): `request_id`, `device_id`, `user_hid`
(`None` or a string, `"anonymous"` for anonymous checks), `public_ip.country`, `risk_score`,
`risk_band`, `signals`, `detection_flags` (`.active()` lists the set flags), `observed_at`,
`source` (`"webhook"`) and `raw`. `to_dict()` returns a JSON-ready dict for queues, and
`Identification.from_dict()` reads it back. `event.event_type`, `event.schema_version` and
`event.created_at` come from the envelope; an unknown `schema_version` is parsed with a
`ShieldLabsWarning`.
