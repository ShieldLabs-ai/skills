# Account-abuse helpers in Python

Built on `client.history.iter(type, value, page_size=100, max_items=None)` of the sync
`ShieldLabs` client, which yields `Identification` objects newest first and skips rows repeated
between pages. With `AsyncShieldLabs`, `history.iter` is an async iterator: use `async for` and
make the helpers `async`.

```python
# account_abuse.py
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Optional, Set

from shieldlabs import NIL_UUID, Identification, ShieldLabs

NOT_AN_ACCOUNT = {"anonymous", "fail", "-1", "unknown"}


def is_account(user_hid: Optional[str]) -> bool:
    return bool(user_hid) and user_hid not in NOT_AN_ACCOUNT


def accounts_on(
    client: ShieldLabs, lookup: Literal["device_id", "visitor_id"], value: str, max_items: int = 500
) -> Set[str]:
    """Multi-accounting: the distinct accounts (User HIDs) seen on one device or one visitor."""
    if value == NIL_UUID:
        return set()
    return {
        item.user_hid
        for item in client.history.iter(lookup, value, max_items=max_items)
        if item.user_hid is not None and is_account(item.user_hid)
    }


def devices_of_account(client: ShieldLabs, user_hid: str, since: datetime, max_items: int = 500) -> Set[str]:
    """Account sharing: the distinct devices of one account since `since` (timezone-aware)."""
    devices: Set[str] = set()
    for item in client.history.iter("user_hid", user_hid, max_items=max_items):
        if item.observed_at is not None and item.observed_at < since:
            break  # newest first: the rest is older
        if item.has_device_signals:
            devices.add(item.device_id)
    return devices


@dataclass
class TravelJump:
    from_country: str  # country of the earlier identification
    to_country: str  # country of the current identification
    minutes: int
    earlier_request_id: str


def _masked(item: Identification) -> bool:
    """A VPN, proxy, Tor or relay hides the real country."""
    f = item.detection_flags
    return f.vpn or f.proxy or f.tor or f.privacy_relay or f.browser_vpn_proxy


def impossible_travel(
    client: ShieldLabs, user_hid: str, current: Identification, within_minutes: int = 60, max_items: int = 100
) -> Optional[TravelJump]:
    """Impossible travel at an action: the current identification comes from another country than
    an identification of the same account less than `within_minutes` before it. Identifications
    without a country, through a VPN, proxy, Tor or relay, or with the Banned IP marker are skipped."""
    at = current.observed_at
    country = current.public_ip.country
    if not country or at is None or _masked(current) or current.is_rate_limited:
        return None
    for item in client.history.iter("user_hid", user_hid, max_items=max_items):
        if item.request_id == current.request_id or item.observed_at is None or item.observed_at > at:
            continue  # only identifications before the current one
        minutes = (at - item.observed_at).total_seconds() / 60
        if minutes > within_minutes:
            break  # newest first: the rest is older
        if not item.public_ip.country or _masked(item) or item.is_rate_limited:
            continue
        if item.public_ip.country != country:
            return TravelJump(item.public_ip.country, country, round(minutes), item.request_id)
    return None


@dataclass
class TakeoverCheck:
    known_account: bool
    new_device: bool
    new_country: bool

    @property
    def suspicious(self) -> bool:
        return self.known_account and self.new_device and self.new_country


def takeover_check(client: ShieldLabs, user_hid: str, current: Identification, max_items: int = 200) -> TakeoverCheck:
    """Account takeover at login: compare the login's identification with the account's history."""
    devices: Set[str] = set()
    countries: Set[str] = set()
    known = False
    for item in client.history.iter("user_hid", user_hid, max_items=max_items):
        if item.request_id == current.request_id or item.is_rate_limited:
            continue
        known = True
        if item.has_device_signals:
            devices.add(item.device_id)
        if item.public_ip.country:
            countries.add(item.public_ip.country)
    new_device = current.has_device_signals and current.device_id not in devices
    new_country = bool(current.public_ip.country) and current.public_ip.country not in countries
    return TakeoverCheck(known, new_device, new_country)


def linked_to_banned_account(
    client: ShieldLabs,
    identification: Identification,
    is_banned_device: Callable[[str], bool],
    is_banned_account: Callable[[str], bool],
) -> bool:
    """Ban evasion: the device is on your banned list, or another account on it is banned."""
    if not identification.has_device_signals:
        return False
    if is_banned_device(identification.device_id):
        return True
    return any(is_banned_account(hid) for hid in accounts_on(client, "device_id", identification.device_id))


def may_redeem(
    client: ShieldLabs,
    identification: Identification,
    account_hid: str,
    has_redemption_on_device: Callable[[str], bool],
) -> Optional[str]:
    """Promo, bonus and free-trial abuse. Returns None when the redemption may go ahead, else a reason.
    `account_hid` is the User HID of the redeeming account; `has_redemption_on_device` reads your
    redemptions table, which works without User HIDs."""
    if not identification.has_device_signals:
        return "no_device_signals"
    if has_redemption_on_device(identification.device_id):
        return "already_redeemed_on_device"
    # Accounts ShieldLabs saw on this device (only those whose signed-in pages passed a User HID),
    # plus the redeeming account, which may not be among them yet.
    accounts = accounts_on(client, "device_id", identification.device_id, max_items=200) | {account_hid}
    if len(accounts) >= 3:
        return "many_accounts_on_device"
    return None
```

## At the action

```python
from datetime import datetime, timedelta, timezone

from .account_abuse import accounts_on, devices_of_account, impossible_travel, takeover_check


def on_signup(client, identification, account):
    # The History API plus your own table of devices per account. The account being created is in
    # neither yet: count it, so 2 existing accounts + this one = 3.
    seen = accounts_on(client, "device_id", identification.device_id)
    if max(len(seen), account_devices.count_accounts(identification.device_id)) + 1 >= 3:
        hold_rewards(account, "many_accounts_on_device")
    account_devices.record(account.id, identification.device_id, identification.visitor_id)


def check_seat(client, identification, account):
    # The account's devices of the last 30 days, and this one.
    since = datetime.now(timezone.utc) - timedelta(days=30)
    devices = devices_of_account(client, user_hid_for(account), since)
    if identification.has_device_signals:
        devices.add(identification.device_id)
    if len(devices) >= 4:
        flag_for_review(account, "account_sharing")


def after_password_check(client, identification, account):
    # The login form identifies anonymously: compare the login's identification with the claimed
    # account's history.
    account_hid = user_hid_for(account)
    ato = takeover_check(client, account_hid, identification)
    travel = impossible_travel(client, account_hid, identification)
    if ato.suspicious or travel is not None:
        return require_second_factor(account)
    return start_session(account)


def on_ban(client, banned):
    # Store the banned account's devices, so that ban evasion checks stay cheap.
    since_ever = datetime.min.replace(tzinfo=timezone.utc)
    ban_store.add_devices(banned.id, devices_of_account(client, user_hid_for(banned), since_ever))
```

History calls raise the SDK errors (`RateLimitError`, `ServerError`, `APIConnectionError`,
`APITimeoutError`, `AuthenticationError`). On a request path, catch `ShieldLabsError` and fall back
to step-up or review.
