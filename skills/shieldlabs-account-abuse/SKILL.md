---
name: shieldlabs-account-abuse
description: Builds account-abuse checks on the ShieldLabs History API with lookups by device_id, user_hid, visitor_id and ip. Covers multi-accounting (accounts per device or visitor), account sharing (devices per account), impossible travel (the action's country against the account's previous hour), account takeover (a known account on a new device and a new country), ban evasion, and promo, bonus or free-trial abuse, with helpers for the Node.js, Python, Go, PHP, Java and .NET SDKs, and explains the High-Risk Events that ShieldLabs detects in the analytics dashboard. Use when the user asks to block multi-accounting, stop duplicate or fake accounts, limit a promo, bonus or free trial to one per person, detect account sharing, flag impossible travel, catch account takeover at login, keep banned users from coming back, or count how many accounts use one device.
---

# Account-abuse checks

Before application integration, [check the installed SDK contract](../shieldlabs-server/references/sdk-contract.md).
Published SDKs can lag the current wire schema: an empty normalized identification ID is
unverified, never a valid key for replay protection or webhook deduplication. MCP uses its own
OAuth adapter; a successful MCP read does not validate an application SDK.


One identification describes one browser session. Abuse across accounts shows up in the
identifiers over time: many accounts on one device, one account on many devices, an account that
jumps between countries. ShieldLabs detects four **High-Risk Events** on your users
(Multi-accounting, Account sharing, Impossible travel, Account takeover), each with Medium or High
confidence, and shows them in the analytics dashboard. The recipes below read the same kind of
evidence from the History API, so that the backend can act at the moment of the action: signup,
login, reward claim, payout.

Build these checks only on fields the installed SDK actually supports. These are bounded
application-side History recipes, not backend High-Risk Event verdicts. Current webhook contracts
also expose HRE data/events; use their verified public schema when requested, and never infer
those verdicts from a sample count or invent fields for an older SDK.

## Workflow

1. Make sure signed-in pages pass a User HID (shieldlabs-user-linking skill,
   [../shieldlabs-user-linking/SKILL.md](../shieldlabs-user-linking/SKILL.md)): lookups by account
   depend on it.
2. At the action, read the current identification (shieldlabs-server skill) and apply the base
   policy first (shieldlabs-risk-decisions skill): replay, freshness, missing, `999`, automation.
3. Run the recipe for the abuse in question, with a bounded History window.
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
| `public_ip.ip` | Changes with the network; shared by offices and mobile carriers | Weak evidence only (IPv4) |

- Skip the all-zero device ID `00000000-0000-0000-0000-000000000000`: it groups identifications
  without usable device signals, not one device.
- Only real accounts count: exclude `user_hid` values `null`, `"anonymous"`, `"fail"`, `"-1"` and
  `"unknown"`.
- Lookups by `user_hid` are exact and case-sensitive. The SDKs refuse a User HID that contains `/`
  or is `.` or `..` with a validation error before any request: the History API cannot match it.
- Skip rate-limit markers (`risk_score` above 100) where they would distort a count.
- History lookups by device or visitor only find the accounts whose signed-in pages passed a User
  HID. Signup and login identifications are anonymous, so record `device_id` and `visitor_id` with
  every account in your own table (workflow step 5) and count there too: that table works from
  the first signup on, with or without User HIDs.

## Recipes

| Abuse | Lookup | Evidence | Starting threshold | Typical action |
|---|---|---|---|---|
| Multi-accounting | `device_id` or `visitor_id`, distinct `user_hid`; your own table of devices per account | Many accounts on one device or visitor | 3 or more accounts, counting the account of the action | Review the signup, hold rewards |
| Account sharing | `user_hid`, distinct `device_id` in a window (30 days) | One account on many devices | 4 or more devices, counting the device of the action | Re-authenticate, review the seat |
| Impossible travel | `user_hid` history just before the action's identification | The action comes from another country than the account in the hour before | Another country within 60 minutes (identifications through a VPN, proxy, Tor or relay are skipped) | Step-up |
| Account takeover | `user_hid` history against the login's identification | A known account on a new device and from a new country | New device and new country | Step-up with a second factor |
| Ban evasion | `device_id` against your banned accounts and banned devices | A banned person comes back | Any match | Block or review |
| Promo, bonus, free-trial abuse | `device_id` against your redemptions, plus accounts on the device | One person claiming many times | One redemption per device | Refuse the reward, keep the account |

The first two thresholds follow the defaults of the analytics dashboard: Multi-accounting from 3
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

## Helpers

Node.js; the references have the same helpers for every SDK:

```ts
import { NIL_UUID, type ShieldLabs } from '@shieldlabs-ai/node';

/** User HID values that do not name one of your accounts. */
const NOT_AN_ACCOUNT = new Set(['anonymous', 'fail', '-1', 'unknown']);

export function isAccount(userHid: string | null): userHid is string {
  return userHid !== null && userHid !== '' && !NOT_AN_ACCOUNT.has(userHid);
}

/** Multi-accounting: the distinct accounts (User HIDs) seen on one device or one visitor. */
export async function accountsOn(
  shieldlabs: ShieldLabs,
  lookup: 'device_id' | 'visitor_id',
  id: string,
  maxItems = 500,
): Promise<Set<string>> {
  const accounts = new Set<string>();
  if (id === NIL_UUID) return accounts; // no usable device signals: nothing to count on
  for await (const item of shieldlabs.history.iterate(lookup, id, { maxItems })) {
    if (isAccount(item.user_hid)) accounts.add(item.user_hid);
  }
  return accounts;
}
```

At signup, after the base policy passed (it already refused the all-zero device ID):

```ts
const seen = await accountsOn(shieldlabs, 'device_id', identification.device_id); // existing accounts with a User HID
const recorded = await accountDevices.countAccounts(identification.device_id); // existing accounts in your own table
// The account being created is in neither yet: count it, so 2 existing accounts + this one = 3.
if (Math.max(seen.size, recorded) + 1 >= 3) {
  await holdRewards(newAccount, { reason: 'many_accounts_on_device' });
}
await accountDevices.record(newAccount.id, identification.device_id, identification.visitor_id);
```

Full code for all six recipes: [node.md](references/node.md), [python.md](references/python.md),
[go.md](references/go.md), [php.md](references/php.md), [java.md](references/java.md),
[dotnet.md](references/dotnet.md).

## Cost and limits

- Rows come newest first, 100 per request by default. `history.iterate` (`history.iter` in
  Python, `History.All` in Go, `history().stream` in Java, `History.IterateAsync` in .NET) skips
  rows repeated between pages and stops at the total, at an empty page or after `maxItems`. A
  `maxItems` of 0 yields nothing, except in Go, where `MaxItems: 0` means no limit: always set it.
- Every page is one History API request, and the History API allows about 15 requests per second
  per domain, shared by every caller. Keep `maxItems` bounded (200 to 500) on request paths, stop
  early when a window is covered, and cache results for a few minutes per device or account.
- History reads do not use your included identifications.

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
