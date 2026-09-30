# Risk decisions in Python

The `decide()` function of the skill on `evaluate_identification` from the `shieldlabs` package.

```python
# risk_policy.py
from datetime import datetime
from typing import Dict, Literal, Optional, Tuple

from shieldlabs import Identification, evaluate_identification

Sensitivity = Literal["low", "medium", "high"]
Decision = Literal["allow", "step_up", "review", "block"]

BY_BAND: Dict[str, Dict[Sensitivity, Decision]] = {
    "trusted": {"low": "allow", "medium": "allow", "high": "allow"},
    "suspicious": {"low": "allow", "medium": "step_up", "high": "review"},
    "dangerous": {"low": "step_up", "medium": "block", "high": "block"},
}
UNVERIFIED: Dict[Sensitivity, Decision] = {"low": "allow", "medium": "step_up", "high": "review"}
USER_MISMATCH: Dict[Sensitivity, Decision] = {"low": "step_up", "medium": "step_up", "high": "block"}
STRICTNESS: Dict[Decision, int] = {"allow": 0, "step_up": 1, "review": 2, "block": 3}


def decide(
    identification: Optional[Identification],
    sensitivity: Sensitivity,
    *,
    first_use: bool,
    expected_user_hid: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Tuple[Decision, str]:
    verdict = evaluate_identification(
        identification,
        is_replay=lambda _rid: not first_use,
        block_bands=(),  # bands are mapped per sensitivity below
        now=now,
    )
    reason = verdict.reason
    if reason is not None:
        if reason in ("missing", "no_device_signals"):
            return UNVERIFIED[sensitivity], reason
        if reason == "rate_limited":
            return ("review" if sensitivity == "high" else "step_up"), reason
        return "block", reason  # replayed, stale, blocked_flag
    assert identification is not None and verdict.band is not None
    # Map the band first: a User HID mismatch can only make the decision stricter, never softer.
    by_band = BY_BAND[verdict.band][sensitivity]
    if expected_user_hid is not None and identification.user_hid != expected_user_hid:
        mismatch = USER_MISMATCH[sensitivity]
        if STRICTNESS[mismatch] > STRICTNESS[by_band]:
            return mismatch, "user_mismatch"
    return by_band, f"band_{verdict.band}"
```

## In a view

```python
from shieldlabs import user_hid

from .risk_policy import decide


def payout(request):
    identification = read_identification(request.POST.get("requestId", ""))  # None on any failure
    first_use = claim_request_id(identification.request_id) if identification else False
    decision, reason = decide(
        identification,
        "high",
        first_use=first_use,
        expected_user_hid=user_hid(str(request.user.id), settings.USER_HID_SECRET),
    )
    logger.info("payout decision=%s reason=%s request_id=%s", decision, reason,
                identification.request_id if identification else None)
    if decision == "allow":
        return create_payout(request)
    if decision == "step_up":
        return JsonResponse({"next": "verify_second_factor"}, status=202)
    if decision == "review":
        return hold_payout_for_review(request, reason)
    return JsonResponse({"error": "request_refused"}, status=403)
```

## Extra flag rules and tests

```python
def stricter_for_high_value(identification: Identification, sensitivity: Sensitivity) -> Optional[Decision]:
    flags = identification.detection_flags
    if flags.anti_detect_browser or flags.tor:
        return "block" if sensitivity == "high" else ("step_up" if sensitivity == "medium" else None)
    return None
```

In tests, pass `now=` to `decide()` to exercise the freshness window, and build identifications
from recorded webhook bodies with `webhooks.construct_event(body, signature, secret)` or from
stored dicts with `Identification.from_dict()`.

Helpers: `risk_band(score)`, `is_rate_limited(score)`, `NIL_UUID`, `identification.risk_band`,
`identification.has_device_signals`, `identification.detection_flags.active()`, and `SignalName`
for the known signal names (an open set).
