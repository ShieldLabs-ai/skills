---
name: shieldlabs-account-abuse
description: Integrates ShieldLabs backend High-Risk Events for multi-accounting, account sharing, impossible travel and account takeover, with optional bounded History recipes for application policy, promo abuse and ban evasion. Use when connecting account-abuse detection, consuming hre results or multi-account group webhooks, reviewing linked accounts, or protecting rewards and signed-in actions.
---

# Account-abuse checks

Read [current SDK and History contracts](../shieldlabs-server/references/current-history.md) for stack routing, public domain UUIDs, filters and availability before adding server reads.

Use the [backend High-Risk Event workflow](references/high-risk-events.md) first. The History recipes below are optional application policies and must not be reported as detector verdicts.

One identification describes one check by the browser agent. Abuse across accounts shows up in the
identifiers over time: many accounts on one device, one account on many devices, an account that
jumps between countries. ShieldLabs detects four **High-Risk Events** on your users
(Multi-accounting, Account sharing, Impossible travel, Account takeover), each with Medium or High
confidence, and shows them in the analytics dashboard. Read backend cards and High-Risk Event results for signup, login, reward claims and payouts.

Build these checks only on fields the installed SDK actually supports. These are bounded
application-side History recipes, not backend High-Risk Event verdicts. Current webhook contracts
also expose HRE data/events; use their verified public schema when requested, and never infer
those verdicts from a sample count or invent response fields.

## Workflow

1. Make sure signed-in pages pass a User HID (shieldlabs-user-linking skill,
   [../shieldlabs-user-linking/SKILL.md](../shieldlabs-user-linking/SKILL.md)): lookups by account
   depend on it.
2. At the action, read the current identification (shieldlabs-server skill) and apply the base
   policy first (shieldlabs-risk-decisions skill): replay, freshness, missing, `999`, automation.
3. Read the backend HRE result/status when available. Add a bounded History recipe only for a separately requested application requirement.
4. Map the result to an action (hold the reward, step-up, review, block) and log the evidence:
   counts, request IDs, countries.
5. Store `device_id` (and `visitor_id`) with accounts, rewards and bans in your own database, so
   that frequent checks query your data first and the History API second.

## Identifiers

| Identifier | Stays the same across | Good for |
|---|---|---|
| `device_id` | Cleared cookies, private windows, new cookie IDs | Counting accounts per device |
| `visitor_id` | Sticky to the device per site: a new cookie on a known device usually keeps it | Counting accounts per visitor |
| `user_hid` | Your account, when the page passes it | Devices and countries per account |
| `cookie_id` | One browser profile until its storage is cleared | Weak on its own |
| `public_ip` | Changes with the network; shared by offices and mobile carriers | Weak evidence only (IPv4) |

- Skip the all-zero device ID `00000000-0000-0000-0000-000000000000`: it groups identifications
  without usable device signals, not one device.
- Only real accounts count: exclude `user_hid` values `null`, `"anonymous"`, `"fail"`, `"-1"` and
  `"unknown"`.
- Lookups by `user_hid` are exact and case-sensitive. The SDKs refuse a User HID that contains `/`
  or is `.` or `..` with a validation error before any request: the History API cannot match it.
- Skip Banned IP markers (`risk_score` above 100) where they would distort a count.
- History lookups by device or visitor only find the accounts whose signed-in pages passed a User
  HID. Signup and login identifications are anonymous, so record `device_id` and `visitor_id` with
  every account in your own table (workflow step 5) and count there too: that table works from
  the first signup on, with or without User HIDs.

## Application policy examples

| Abuse | Lookup | Evidence | Starting threshold | Typical action |
|---|---|---|---|---|
| Multi-accounting | `device_id` or `visitor_id`, distinct `user_hid`; your own table of devices per account | Many accounts on one device or visitor | 3 or more accounts, counting the account of the action | Review the signup, hold rewards |
| Account sharing | `user_hid`, distinct `device_id` in a window (30 days) | One account on many devices | 4 or more devices, counting the device of the action | Re-authenticate, review the seat |
| Impossible travel | `user_hid` history just before the action's identification | The action comes from another country than the account in the hour before | Another country within 60 minutes (identifications through a VPN, proxy, Tor or relay are skipped) | Step-up |
| Account takeover | `user_hid` history against the login's identification | A known account on a new device and from a new country | New device and new country | Step-up with a second factor |
| Ban evasion | `device_id` against your banned accounts and banned devices | A banned person comes back | Any match | Block or review |
| Promo, bonus, free-trial abuse | `device_id` against your redemptions, plus accounts on the device | One person claiming many times | One redemption per device | Refuse the reward, keep the account |

Backend High-Risk Event thresholds are: Multi-accounting from 3
accounts on one visitor, Account sharing from 4 devices on one account. Both counts include the
action itself: at signup the account being created is in neither the History API nor your table
yet, so the check is "existing accounts + 1 >= 3" (two accounts already on the device); a reward
claim counts the claiming account, and a seat check adds the device of the current
identification. Count by `visitor_id` to match the analytics dashboard, or by `device_id`, which
also holds when a browser gets new cookie IDs. Tune the thresholds against your traffic. Lookups by
`ip` (IPv4 only) are weak evidence on their own: offices and mobile carriers put many people behind
one address.

Impossible travel compares the action's own identification with the account's identifications
in the window before it. The login form identifies anonymously, so that identification never
appears in the account's history: pass it to the helper instead of scanning the history alone.

## Read backend evidence

Node.js 1.3.2 reads the account, visitor or device card directly:

```ts
const card = await shieldlabs.entities.get(domainId, "user", accountHid);
// Preserve card.high_risk_events, card.related_counts, card.risk and card.signals.
```

Use the backend's HRE status and confidence. For a separately requested reward or ban policy,
join the application's own accounts/redemptions/bans using domain and identification UUIDs.
A card and its related counts do not provide a complete list of linked account/device IDs.
Use the application's own stored associations when the requested policy needs those IDs.
Read [Node.js](references/node.md), [Python](references/python.md), [Go](references/go.md),
[PHP](references/php.md), [Java](references/java.md) or [.NET](references/dotnet.md) for the matching
server read and policy boundary. Do not implement detector rules by counting one History page.

## Cost and limits

Each card or list page is a History API request. Keep windows and page budgets explicit,
follow opaque cursors with unchanged constraints, and cache investigative evidence when appropriate.
History reads do not use included browser identifications. Do not poll with new identify() calls.

## Legitimate explanations

Families and shared computers (multi-accounting, account sharing), offices and mobile carriers
behind one IP, travellers and VPN users (impossible travel), a new phone (account takeover). Prefer
step-up or review to a block on the first match, and weigh the evidence together with the Risk
Score band and the detection flags of the current identification.

## High-Risk Events in the analytics dashboard

ShieldLabs detects Multi-accounting, Account sharing, Impossible travel and Account takeover on
your users out of the box and grades each at Medium or High confidence, a separate axis from the
Risk Score. In the analytics dashboard (https://app.shieldlabs.ai) they appear on the Overview,
as a filter in Analytics, and as pills on the user card next to the user's devices, visitors and
IP addresses. They are built on User HIDs, so pass them on every signed-in page. To investigate an
account from an AI assistant, use the shieldlabs-investigate skill
([../shieldlabs-investigate/SKILL.md](../shieldlabs-investigate/SKILL.md)).

## Pitfalls

- Counting `"anonymous"` (or `null`) as an account, or the all-zero device ID as a device.
- Treating a shared IP address as proof of anything.
- Unbounded iteration on a request path, or one History call per page view.
- Running the recipes before the base policy: a replayed or stale request ID must be refused first.
- Blocking on one weak signal. Combine the count with the band and flags.
- Logging raw personal data next to the evidence: log User HIDs and request IDs.

## Versions

This skill targets the 1.x SDKs. Before pinning, confirm the current version on the package
registry and at https://docs.shieldlabs.ai.
