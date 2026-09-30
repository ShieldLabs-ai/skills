# Account-abuse helpers in Node.js

Built on `history.iterate(type, value, { pageSize?, maxItems? })` of `@shieldlabs/node`, which
yields `Identification` objects newest first and skips rows repeated between pages. Start
`account-abuse.ts` with `isAccount` and `accountsOn` from the skill's [Helpers](../SKILL.md#helpers)
block, add `isRateLimited` and `type Identification` to its import, then add the other recipes:

```ts
// account-abuse.ts, after isAccount and accountsOn
const time = (item: Identification): number => (item.observed_at ? Date.parse(item.observed_at) : Number.NaN);

/** A VPN, proxy, Tor or relay hides the real country. */
const masked = (item: Identification): boolean => {
  const f = item.detection_flags;
  return f.vpn || f.proxy || f.tor || f.privacy_relay || f.browser_vpn_proxy;
};

/** Account sharing: the distinct devices of one account since `sinceMs` (epoch milliseconds). */
export async function devicesOfAccount(shieldlabs: ShieldLabs, userHid: string, sinceMs: number, maxItems = 500): Promise<Set<string>> {
  const devices = new Set<string>();
  for await (const item of shieldlabs.history.iterate('user_hid', userHid, { maxItems })) {
    if (time(item) < sinceMs) break; // newest first: the rest is older
    if (item.device_id !== NIL_UUID) devices.add(item.device_id);
  }
  return devices;
}

export interface TravelJump {
  from: string; // country of the earlier identification
  to: string; // country of the current identification
  minutes: number;
  earlierRequestId: string;
}

/**
 * Impossible travel at an action: the current identification comes from another country than an
 * identification of the same account less than `withinMinutes` before it. Identifications without
 * a country, through a VPN, proxy, Tor or relay, or with the rate-limit marker are skipped.
 */
export async function impossibleTravel(
  shieldlabs: ShieldLabs,
  userHid: string,
  current: Identification,
  withinMinutes = 60,
  maxItems = 100,
): Promise<TravelJump | null> {
  const at = time(current);
  const country = current.public_ip.country;
  if (!country || Number.isNaN(at) || masked(current) || isRateLimited(current.risk_score)) return null;
  for await (const item of shieldlabs.history.iterate('user_hid', userHid, { maxItems })) {
    const t = time(item);
    if (item.request_id === current.request_id || Number.isNaN(t) || t > at) continue; // only earlier ones
    const minutes = (at - t) / 60_000;
    if (minutes > withinMinutes) break; // newest first: the rest is older
    if (!item.public_ip.country || masked(item) || isRateLimited(item.risk_score)) continue;
    if (item.public_ip.country !== country) {
      return { from: item.public_ip.country, to: country, minutes: Math.round(minutes), earlierRequestId: item.request_id };
    }
  }
  return null;
}

export interface TakeoverCheck {
  knownAccount: boolean; // the account has earlier identifications
  newDevice: boolean;
  newCountry: boolean;
  suspicious: boolean; // known account, new device and new country
}

/** Account takeover at login: compare the login's identification with the account's history. */
export async function takeoverCheck(shieldlabs: ShieldLabs, userHid: string, current: Identification, maxItems = 200): Promise<TakeoverCheck> {
  const devices = new Set<string>();
  const countries = new Set<string>();
  let knownAccount = false;
  for await (const item of shieldlabs.history.iterate('user_hid', userHid, { maxItems })) {
    if (item.request_id === current.request_id || isRateLimited(item.risk_score)) continue;
    knownAccount = true;
    if (item.device_id !== NIL_UUID) devices.add(item.device_id);
    if (item.public_ip.country) countries.add(item.public_ip.country);
  }
  const newDevice = current.device_id !== NIL_UUID && !devices.has(current.device_id);
  const newCountry = current.public_ip.country !== '' && !countries.has(current.public_ip.country);
  return { knownAccount, newDevice, newCountry, suspicious: knownAccount && newDevice && newCountry };
}

/** Ban evasion: the device is on your banned list, or another account on it is banned. */
export async function linkedToBannedAccount(
  shieldlabs: ShieldLabs,
  identification: Identification,
  store: { isBannedDevice(deviceId: string): Promise<boolean>; isBannedAccount(userHid: string): Promise<boolean> },
): Promise<boolean> {
  if (identification.device_id === NIL_UUID) return false;
  if (await store.isBannedDevice(identification.device_id)) return true;
  for (const hid of await accountsOn(shieldlabs, 'device_id', identification.device_id)) {
    if (await store.isBannedAccount(hid)) return true;
  }
  return false;
}

/** Promo, bonus and free-trial abuse: one redemption per device, and no crowded devices. */
export async function mayRedeem(
  shieldlabs: ShieldLabs,
  identification: Identification,
  accountHid: string, // the User HID of the account that redeems
  hasRedemptionOnDevice: (deviceId: string) => Promise<boolean>, // your redemptions table
): Promise<{ ok: boolean; reason?: string }> {
  if (identification.device_id === NIL_UUID) return { ok: false, reason: 'no_device_signals' };
  if (await hasRedemptionOnDevice(identification.device_id)) return { ok: false, reason: 'already_redeemed_on_device' };
  // Accounts ShieldLabs saw on this device (only those whose signed-in pages passed a User HID),
  // plus the redeeming account, which may not be among them yet.
  const accounts = await accountsOn(shieldlabs, 'device_id', identification.device_id, 200);
  accounts.add(accountHid);
  if (accounts.size >= 3) return { ok: false, reason: 'many_accounts_on_device' };
  return { ok: true };
}
```

## At the action

```ts
import { NIL_UUID, type Identification, type ShieldLabs } from '@shieldlabs/node';
import { devicesOfAccount, impossibleTravel, mayRedeem, takeoverCheck } from './account-abuse';

// Seat check for a subscription account: its devices of the last 30 days, and this one.
export async function checkSeat(shieldlabs: ShieldLabs, identification: Identification, account: Account) {
  const devices = await devicesOfAccount(shieldlabs, userHidFor(account), Date.now() - 30 * 24 * 3600_000);
  if (identification.device_id !== NIL_UUID) devices.add(identification.device_id);
  if (devices.size >= 4) await flagForReview(account.id, 'account_sharing', devices.size);
}

// Login: the form identifies anonymously. After the password check, compare the login's
// identification with the claimed account's history.
export async function afterPasswordCheck(shieldlabs: ShieldLabs, identification: Identification, account: Account) {
  const accountHid = userHidFor(account);
  const ato = await takeoverCheck(shieldlabs, accountHid, identification);
  const travel = await impossibleTravel(shieldlabs, accountHid, identification);
  if (ato.suspicious || travel) return requireSecondFactor(account);
  return startSession(account);
}

// Ban: when you ban an account, store its devices so that ban evasion checks stay cheap.
export async function onBan(shieldlabs: ShieldLabs, bannedAccount: Account) {
  const bannedDevices = await devicesOfAccount(shieldlabs, userHidFor(bannedAccount), 0);
  await banStore.addDevices(bannedAccount.id, [...bannedDevices]);
}

// Promo: record (promo, device_id, visitor_id, user_hid) with every successful redemption. That
// table answers "one redemption per device" even when no page passes a User HID.
export async function redeemPromo(shieldlabs: ShieldLabs, identification: Identification, account: Account, promo: Promo) {
  const check = await mayRedeem(shieldlabs, identification, userHidFor(account), (deviceId) =>
    redemptions.existsForDevice(promo.id, deviceId));
  if (!check.ok) return refuseReward(check.reason);
  return grantReward(account, promo);
}
```

The signup check is in the skill ([Helpers](../SKILL.md#helpers)).

## Errors

History calls throw the SDK errors (`RateLimitError`, `ServerError`, `ConnectionError`,
`TimeoutError`, `AuthenticationError`). On a request path, catch `ShieldLabsError` and fall back to
step-up or review instead of allowing the action silently.
