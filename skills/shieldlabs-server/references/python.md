# Python with `shieldlabs`

Python 3.9 or later. The only dependency is `httpx`. Sync (`ShieldLabs`) and async
(`AsyncShieldLabs`) clients with the same methods.

## Install and create the client

```bash
pip install shieldlabs
```

```python
from shieldlabs import ShieldLabs

client = ShieldLabs()  # reads SHIELDLABS_API_KEY (and SHIELDLABS_API_BASE_URL when set)
```

Options: `api_key` (default `SHIELDLABS_API_KEY`), `base_url` (default
`SHIELDLABS_API_BASE_URL`, else `https://account.shieldlabs.ai`), `timeout` (seconds per attempt,
default `10.0`), `max_retries` (default `2`), `http_client` (your own `httpx.Client` or
`httpx.AsyncClient`, not closed for you). Create one client per process; it is safe to share
across threads (sync) or tasks (async). Close it with `close()` / `aclose()` or use it as a
context manager.

## FastAPI (async)

```python
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from shieldlabs import AsyncShieldLabs, ShieldLabsError, evaluate_identification

logger = logging.getLogger(__name__)
app = FastAPI()
shieldlabs = AsyncShieldLabs()  # one per process; await shieldlabs.aclose() on shutdown
redis = Redis()


async def claim_request_id(request_id: str) -> bool:
    """True the first time a request ID is claimed; an unreachable store refuses."""
    try:
        return bool(await redis.set(f"shieldlabs:used:{request_id}", 1, nx=True, ex=86400))
    except Exception:
        logger.exception("request ID store unavailable")
        return False


class SignupForm(BaseModel):
    email: str
    request_id: Optional[str] = Field(default=None, alias="requestId")


@app.post("/api/signup", status_code=201)
async def signup(form: SignupForm) -> dict:
    identification = None
    if form.request_id:
        try:
            identification = await shieldlabs.identifications.get(form.request_id)
        except ShieldLabsError:
            logger.warning("ShieldLabs lookup failed", exc_info=True)  # unverified, never clean

    # is_replay must answer synchronously: claim first, then pass the result.
    first_use = await claim_request_id(identification.request_id) if identification else False
    verdict = evaluate_identification(identification, is_replay=lambda _rid: not first_use)
    if not verdict.ok:
        logger.info("signup refused: reason=%s band=%s flag=%s", verdict.reason, verdict.band, verdict.flag)
        raise HTTPException(status_code=403, detail="signup_refused")
    # Create the account here.
    return {"ok": True}
```

## Django (sync)

```python
import logging

from django.db import IntegrityError, models, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from shieldlabs import ShieldLabs, ShieldLabsError, evaluate_identification

logger = logging.getLogger(__name__)
shieldlabs = ShieldLabs()  # module level: one client per process


class UsedRequestId(models.Model):  # in models.py
    request_id = models.CharField(max_length=36, unique=True)
    used_at = models.DateTimeField(auto_now_add=True)


def claim_request_id(request_id: str) -> bool:
    """True the first time a request ID is claimed."""
    try:
        with transaction.atomic():
            UsedRequestId.objects.create(request_id=request_id)
        return True
    except IntegrityError:
        return False


@require_POST
def signup(request):
    request_id = request.POST.get("requestId", "")
    identification = None
    if request_id:
        try:
            identification = shieldlabs.identifications.get(request_id)
        except ShieldLabsError:
            logger.warning("ShieldLabs lookup failed", exc_info=True)
    verdict = evaluate_identification(
        identification,
        is_replay=lambda rid: not claim_request_id(rid),  # sync code can claim inside the callback
    )
    if not verdict.ok:
        logger.info("signup refused: reason=%s band=%s", verdict.reason, verdict.band)
        return JsonResponse({"error": "signup_refused"}, status=403)
    # Create the account here.
    return JsonResponse({"ok": True}, status=201)
```

Flask works the same way with `request.form` or `request.get_json()`. The wait can take up to
`timeout` seconds (10 by default) plus up to 1 second for the last poll, so keep the worker timeout
of your WSGI server above it, or pass a shorter `timeout=`.

## `identifications.get` options

```python
client.identifications.get(request_id)                       # wait up to 10 s in total
client.identifications.get(request_id, timeout=5)            # a 5-second budget; the last poll runs at the deadline
client.identifications.get(request_id, poll_interval=0.25)   # waits of p, 2p, 4p, 6p, then 8p, each at most max(2 s, p)
client.identifications.get(request_id, wait=False)           # one lookup with the usual retries
```

It returns an `Identification` or `None`. Each poll is one HTTP request, and a `429`, a 5xx, a
connection error or a timeout keeps it polling; at the deadline the error of a failed last poll is
raised instead of returning `None`. A `400`, `401`, `403` or `404` raises at once, and so does a
`429` whose `Retry-After` (capped at 10 seconds) is longer than the time left; after any other
`429` the next poll waits the longest of the scheduled wait, 1 second and the capped `Retry-After`
(0 when missing), cut short at the deadline.

## `evaluate_identification`

```python
from datetime import timedelta

verdict = evaluate_identification(
    identification,
    max_age=timedelta(minutes=5),          # or seconds as a number (default 300.0)
    block_bands=["dangerous"],
    block_flags=["browser_automation", "javascript_disabled"],
    is_replay=lambda rid: not claim_request_id(rid),
)
# Evaluation(ok=False, reason='blocked_flag', band='dangerous', flag='browser_automation')
```

Helpers: `risk_band(score)`, `is_rate_limited(score)`, `NIL_UUID`, and the properties
`identification.risk_band`, `identification.is_rate_limited`, `identification.has_device_signals`
and `identification.detection_flags.active()`.

## The `Identification` model

A frozen dataclass with the webhook field names: `request_id`, `visitor_id`, `device_id`,
`session_id`, `cookie_id`, `user_hid` (`None` when empty, `"anonymous"` for anonymous checks),
`domain`, `public_ip` and `local_ip` (`IpInfo(ip, country)`, English country names),
`connection_type`, `os`, `browser`, `device_type`, `traffic_source`, `risk_score`, `signals`,
`detection_flags` (19 booleans), `observed_at` (timezone-aware UTC `datetime` or `None`),
`source` and `raw`.

## Errors

All exceptions extend `ShieldLabsError`: `ValidationError` (also a `ValueError`; nothing sent),
`ApiError` with `status`, `message`, `body`, `headers`, and its subclasses `BadRequestError`,
`AuthenticationError` (401, 403), `QuotaExceededError` (402), `NotFoundError` (404),
`RateLimitError` (429, `retry_after`), `ServerError` (5xx); plus `APIConnectionError` and
`APITimeoutError`. GET requests are retried on connection errors, timeouts, 429 and 5xx with
exponential backoff. `Retry-After` is followed as sent, capped at 10 seconds (`0` or a date in the
past retries at once), and a `429` without it waits at least 1 second. Inside
`identifications.get` a poll is never retried: the schedule polls again instead.

## Management API

```python
from shieldlabs import ShieldLabsManagement

management = ShieldLabsManagement()       # reads SHIELDLABS_SECRET_KEY and SHIELDLABS_DOMAIN
profile = management.get_profile()        # cache it: about 15 calls per minute per IP
print(profile.remaining_identifications)  # negative when the account is over its included volume
```
