---
name: shieldlabs-risk-decisions
description: Turns a ShieldLabs identification into an allow, step-up, review or block decision for each protected action. Explains the Risk Score and its three bands (trusted 0-29, suspicious 30-59, dangerous 60-100), detection flags versus risk signals, the 999 Banned IP marker, the all-zero device ID, missing identifications, replay and freshness guards and account binding, and builds a per-action policy on the SDK policy helpers for Node.js, Python, Go, PHP, Java and .NET. Use when the user asks what Risk Score to block at, how to treat VPN, proxy, Tor, anti-detect browsers or browser automation, how to block risky signups, add step-up or 2FA for suspicious logins or payouts, tune evaluateIdentification, or explain a ShieldLabs verdict in code.
---

# Decide on a ShieldLabs verdict

Read [current SDK and History contracts](../shieldlabs-server/references/current-history.md) for stack routing, public domain UUIDs, filters and availability before adding server reads.

For crawlers and AI traffic, use [client identity and proof scope](references/client-identity.md). Missing attribution is unknown; claimed names do not authorize protected actions.

The backend has an `Identification` for the request ID of a protected action (shieldlabs-server
skill, [../shieldlabs-server/SKILL.md](../shieldlabs-server/SKILL.md)), or knows that it has none.
This skill maps that verdict to one of four actions: **allow**, **step-up** (a check the user can
pass: an email or SMS code, a second factor, re-authentication), **review** (hold the action, for
example a payout, for a person or a later job) or **block** (refuse with a generic message).

For a current entity card, use `risk.state`, `risk.score`/`risk.band` and `signals.state`/`items`.
Require available risk and signals, check domain/ID/freshness/replay and account binding, then
apply this action policy. The SDK helpers below accept their normalized Identification model,
not a raw entity card. Node 1.3.2 normalizes `identifications.get` results; guard unavailable
risk/signals before calling the helper. Other language helpers can evaluate a verified scored
webhook model; use the current server reference for raw History cards.

## Workflow

1. List the protected actions and give each a sensitivity (table below).
2. Run the SDK policy helper with the replay result, with `blockBands` empty so that bands are
   mapped per action, and with the default blocked flags.
3. Map the result to an action with the decision table.
4. For actions by signed-in users, check that `identification.user_hid` equals the User HID of the
   session user.
5. Log `request_id`, the decision, `reason`, band and set flags. Answer the browser generically.
6. For signup, rewards and payouts, add the account-level checks of the shieldlabs-account-abuse
   skill ([../shieldlabs-account-abuse/SKILL.md](../shieldlabs-account-abuse/SKILL.md)).

## What to branch on

| Field | Use it for | Notes |
|---|---|---|
| `risk_score` | The band, through `riskBand(score)` | 0-100. `999` is the Banned IP marker, never a score. Never recompute it from signals |
| `detection_flags` | Specific conditions in the installed SDK model | Stable names: `browser_automation`, `anti_detect_browser`, `tor`, `vpn`, `proxy`, ... |
| `signals` | Display and logging | The weighted risk signals behind the score. An open set: weights can be negative and names can repeat |
| `device_id`, `visitor_id`, `user_hid`, `public_ip` | Account binding and account-level checks | The all-zero device ID means no usable device signals |
| `observed_at` | Freshness | The policy helper checks it against the freshness window |

## Action sensitivity

| Sensitivity | Examples |
|---|---|
| Low | Newsletter signup, comment, search, content view |
| Medium | Account signup, login, free trial start, promo code redemption |
| High | Payout or withdrawal, payment method change, email or password change, large checkout |

## Decision table

A starting point to tune per action with your own traffic:

| Verdict | Low | Medium | High |
|---|---|---|---|
| trusted (0-29) | allow | allow | allow |
| suspicious (30-59) | allow | step-up | review |
| dangerous (60-100) | step-up | block | block |
| `missing`: no request ID, not found in time, or an API error | allow with limits, log as unverified | step-up | review |
| `banned_ip`: the `999` marker | step-up | step-up | review |
| `no_device_signals`: the all-zero device ID | allow with limits, log | step-up | review |
| `replayed` or `stale` | block; the page runs a fresh identification on retry | block | block |
| `blocked_flag`: `browser_automation` or `javascript_disabled` | block | block | block |
| `user_hid` differs from the session's User HID | step-up | step-up | block |

"Allow with limits" still means unverified: no rewards, lower quotas, extra monitoring. Never
treat it as clean.

**User HID mismatch.** Map the band first, then apply the mismatch row only when it is stricter:
a mismatch never softens a verdict, so a dangerous identification stays blocked on a medium
action.

**Step-up at signup.** A new account has no second factor yet. Create it in a pending state and
hold what the signup unlocks (the trial, a bonus, invitations) until the user confirms the email
address or phone number: that confirmation is the step-up. When the product has no such check,
step-up becomes allow with limits.

## The policy in code

Node.js uses the normalized model below. Other references apply the same decision table to current raw entity cards, without assuming an SDK adapter.

```ts
import { evaluateIdentification, type Identification } from '@shieldlabs-ai/node';

export type Sensitivity = 'low' | 'medium' | 'high';
export type Decision = 'allow' | 'step_up' | 'review' | 'block';

const BY_BAND: Record<'trusted' | 'suspicious' | 'dangerous', Record<Sensitivity, Decision>> = {
  trusted: { low: 'allow', medium: 'allow', high: 'allow' },
  suspicious: { low: 'allow', medium: 'step_up', high: 'review' },
  dangerous: { low: 'step_up', medium: 'block', high: 'block' },
};
const UNVERIFIED: Record<Sensitivity, Decision> = { low: 'allow', medium: 'step_up', high: 'review' };
const USER_MISMATCH: Record<Sensitivity, Decision> = { low: 'step_up', medium: 'step_up', high: 'block' };
const STRICTNESS: Record<Decision, number> = { allow: 0, step_up: 1, review: 2, block: 3 };

export function decide(
  identification: Identification | null,
  sensitivity: Sensitivity,
  context: { firstUse: boolean; expectedUserHid?: string; now?: number },
): { decision: Decision; reason: string } {
  if (identification && (!Number.isFinite(identification.risk_score)
      || (identification.source === 'history'
        && (identification.raw.signals as { state?: string } | undefined)?.state !== 'ok'))) {
    return { decision: UNVERIFIED[sensitivity], reason: 'unavailable' };
  }
  const verdict = evaluateIdentification(identification, {
    isReplay: () => !context.firstUse, // from your atomic claim of the request ID
    blockBands: [], // bands are mapped per sensitivity below
    now: context.now, // tests only; default: the current time
    // blockFlags keeps its default: browser_automation, javascript_disabled
  });
  switch (verdict.reason) {
    case 'replayed':
    case 'stale':
    case 'blocked_flag':
      return { decision: 'block', reason: verdict.reason };
    case 'missing':
    case 'no_device_signals':
      return { decision: UNVERIFIED[sensitivity], reason: verdict.reason };
    case 'banned_ip':
      return { decision: sensitivity === 'high' ? 'review' : 'step_up', reason: verdict.reason };
  }
  // Map the band first: a User HID mismatch can only make the decision stricter, never softer.
  const band = verdict.band as 'trusted' | 'suspicious' | 'dangerous';
  const byBand = BY_BAND[band][sensitivity];
  if (context.expectedUserHid !== undefined && identification?.user_hid !== context.expectedUserHid) {
    const mismatch = USER_MISMATCH[sensitivity];
    if (STRICTNESS[mismatch] > STRICTNESS[byBand]) return { decision: mismatch, reason: 'user_mismatch' };
  }
  return { decision: byBand, reason: `band_${band}` };
}
```

References with the matching action policy: [node.md](references/node.md), [python.md](references/python.md),
[go.md](references/go.md), [php.md](references/php.md), [java.md](references/java.md),
[dotnet.md](references/dotnet.md). The meaning of every flag, signal and connection type is in
[flags-and-signals.md](references/flags-and-signals.md).

## Flags worth a rule of their own

Use the [20 detection flags](references/flags-and-signals.md) alongside the Risk Score.
Missing values are unknown. AI flags are booleans; identity and proof are separate fields.

| Flag | Meaning | Starting point |
|---|---|---|
| `browser_automation`, `javascript_disabled` | Automated or scripted browsing | Block on protected actions (the SDK default) |
| `anti_detect_browser` | A browser that masks its real configuration | Step-up on medium actions, block on high |
| `tor` | A Tor exit node | Step-up on medium actions, review or block on high |
| `vpn`, `private_relay`, `proxy`, `tor` | A masked or hosted network | Already in the score. Many legitimate users (companies, privacy tools) use them: step-up on high-value actions instead of blocking outright |
| `incognito`, `ip_mismatch`, `check_incomplete`, `network_check_incomplete` | Context | Log only |

## Rules that keep decisions sound

- Branch on the band and on `detection_flags`. Use signal names for display and logs only, and
  never add up weights yourself: weights can be negative (a late network check corrects an earlier
  one) and a name can appear twice.
- `999` is not a dangerous score. The visitor IP sent too many identifications and was blocked for
  10 minutes; busy shared IPs (offices, mobile carriers) can hit it too. Treat it as unverified.
- A missing identification is unverified, never clean.
- Current entity cards return `risk.band`. Normalized scored webhook models derive the band from `risk_score`; do not assume one shape for both.
- The Risk Score grades one identification. Patterns across an account (multi-accounting, account
  sharing, impossible travel, account takeover) are the High-Risk Events that ShieldLabs shows in
  the analytics dashboard; for checks in code, see the shieldlabs-account-abuse skill.
- Never show risk signals, flags or scores to the end user. Say "we could not verify this request"
  and offer the step-up.

## Tune it

- Log every decision with `request_id`, and open the identification in the analytics dashboard
  (https://app.shieldlabs.ai) to see the risk signals behind a score.
- Watch step-up completion and review outcomes per action: a high pass rate on step-ups for one
  band means that band can move to allow for that action.
- Change thresholds per action, never globally, and pass `now` to the policy helper in unit tests.

## Pitfalls

- Blocking every VPN or proxy outright: many legitimate users have one. Let the band carry it and
  step up on high-value actions.
- Treating `999` as a dangerous score, or a missing identification as trusted.
- One global threshold for every action instead of a sensitivity per action.
- Leaving the SDK default `blockBands: ['dangerous']` in place while also mapping bands yourself:
  pass an empty list when the decision table handles the bands.
- Branching on signal descriptions or on the sum of signal weights.
- Telling users which signal or flag refused them.

## Versions

This skill targets the 1.x SDKs. Before pinning, confirm the current version on the package
registry and at https://docs.shieldlabs.ai.
