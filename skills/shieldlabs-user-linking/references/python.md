# User HID in Python

`user_hid(user_id, secret)` from `shieldlabs` returns HMAC-SHA256 as 64 lowercase hex characters
and raises `ValidationError` on empty input. `secret` can be `str` or `bytes`.

```python
import os

from shieldlabs import user_hid

USER_HID_SECRET = os.environ["USER_HID_SECRET"]

def user_hid_for(user) -> str:
    return user_hid(str(user.pk), USER_HID_SECRET)
```

## Django templates

A context processor makes the User HID available to every template of a signed-in user:

```python
# myapp/context_processors.py
def shieldlabs(request):
    if request.user.is_authenticated:
        return {"shieldlabs_user_hid": user_hid_for(request.user)}
    return {}
```

Add `"myapp.context_processors.shieldlabs"` to `TEMPLATES[0]["OPTIONS"]["context_processors"]`,
then render it where the page script reads it:

```html
<form id="checkout" data-user-hid="{{ shieldlabs_user_hid }}">...</form>
```

Django renders the missing value as an empty attribute. The page script passes `form.dataset.userHid || undefined` to `identify({ userId })`: for a visitor who is not signed in the attribute is empty, and an empty `userId` is rejected with `invalid_options`, while `undefined` runs an anonymous identification.

## Flask

```python
from flask_login import current_user

@app.context_processor
def shieldlabs_context():
    if current_user.is_authenticated:
        return {"shieldlabs_user_hid": user_hid(str(current_user.id), USER_HID_SECRET)}
    return {}
```

## FastAPI (single-page apps)

```python
@app.get("/api/session")
async def session(user=Depends(current_user_or_none)):
    if user is None:
        return {"user": None}
    return {"user": {"name": user.name, "userHid": user_hid(str(user.id), USER_HID_SECRET)}}
```

## Check it on the server

```python
expected = user_hid_for(request.user)
if identification is not None and identification.user_hid != expected:
    ...  # treat as unverified: another account's identification, or an anonymous one
```

## Read the account's History card

Read the `user` card with the exact generated HID, in the selected public domain UUID.
Preserve risk, signals, High-Risk Events and nullable related counts. Use card relations for
linked devices, visitors and countries; follow relation_page_token without changing scope.
See [current History](../../shieldlabs-server/references/current-history.md) and the
[account-abuse workflow](../../shieldlabs-account-abuse/references/high-risk-events.md).
