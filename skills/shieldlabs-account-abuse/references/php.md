# Account-abuse helpers in PHP

Built on `$shieldlabs->history->iterate(LookupType|string $type, string $value, ['max_items' => N])`,
a lazy generator of `Model\Identification` objects, newest first, that skips rows repeated
between pages.

```php
<?php

use ShieldLabs\LookupType;
use ShieldLabs\Model\Identification;
use ShieldLabs\ShieldLabs;

final class AccountAbuse
{
    private const NOT_AN_ACCOUNT = ['anonymous', 'fail', '-1', 'unknown'];
    private const NIL_UUID = '00000000-0000-0000-0000-000000000000';

    public function __construct(private readonly ShieldLabs $shieldlabs) {}

    private static function isAccount(string $userHid): bool
    {
        return $userHid !== '' && !in_array($userHid, self::NOT_AN_ACCOUNT, true);
    }

    /** A VPN, proxy, Tor or relay hides the real country. */
    private static function masked(Identification $row): bool
    {
        $f = $row->detection_flags;
        return $f->vpn || $f->proxy || $f->tor || $f->privacy_relay || $f->browser_vpn_proxy;
    }

    /**
     * Multi-accounting: the distinct accounts (User HIDs) seen on one device or one visitor.
     *
     * @param LookupType $lookup LookupType::DeviceId or LookupType::VisitorId
     * @return list<string>
     */
    public function accountsOn(LookupType $lookup, string $id, int $maxItems = 500): array
    {
        if ($id === self::NIL_UUID) {
            return [];
        }
        $accounts = [];
        foreach ($this->shieldlabs->history->iterate($lookup, $id, ['max_items' => $maxItems]) as $row) {
            $hid = $row->user_hid;
            if ($hid !== null && self::isAccount($hid)) {
                $accounts[] = $hid;
            }
        }
        return array_values(array_unique($accounts));
    }

    /**
     * Account sharing: the distinct devices of one account since $since.
     *
     * @return list<string>
     */
    public function devicesOfAccount(string $userHid, \DateTimeInterface $since, int $maxItems = 500): array
    {
        $devices = [];
        foreach ($this->shieldlabs->history->iterate(LookupType::UserHid, $userHid, ['max_items' => $maxItems]) as $row) {
            if ($row->observed_at !== null && $row->observed_at < $since) {
                break; // newest first: the rest is older
            }
            if ($row->hasDeviceSignals()) {
                $devices[] = $row->device_id;
            }
        }
        return array_values(array_unique($devices));
    }

    /**
     * Impossible travel at an action: the current identification comes from another country than
     * an identification of the same account less than $withinMinutes before it. Identifications
     * without a country, through a VPN, proxy, Tor or relay, or with the rate-limit marker are skipped.
     *
     * @return array{from: string, to: string, minutes: int, earlier_request_id: string}|null
     */
    public function impossibleTravel(string $userHid, Identification $current, int $withinMinutes = 60, int $maxItems = 100): ?array
    {
        $at = $current->observed_at;
        $country = $current->public_ip->country;
        if ($country === '' || $at === null || self::masked($current) || $current->isRateLimited()) {
            return null;
        }
        foreach ($this->shieldlabs->history->iterate(LookupType::UserHid, $userHid, ['max_items' => $maxItems]) as $row) {
            if ($row->request_id === $current->request_id || $row->observed_at === null || $row->observed_at > $at) {
                continue; // only identifications before the current one
            }
            $minutes = ($at->getTimestamp() - $row->observed_at->getTimestamp()) / 60;
            if ($minutes > $withinMinutes) {
                break; // newest first: the rest is older
            }
            if ($row->public_ip->country === '' || self::masked($row) || $row->isRateLimited()) {
                continue;
            }
            if ($row->public_ip->country !== $country) {
                return ['from' => $row->public_ip->country, 'to' => $country,
                    'minutes' => (int) round($minutes), 'earlier_request_id' => $row->request_id];
            }
        }
        return null;
    }

    /**
     * Account takeover at login: compare the login's identification with the account's history.
     *
     * @return array{known_account: bool, new_device: bool, new_country: bool, suspicious: bool}
     */
    public function takeoverCheck(string $userHid, Identification $current, int $maxItems = 200): array
    {
        $devices = [];
        $countries = [];
        $known = false;
        foreach ($this->shieldlabs->history->iterate(LookupType::UserHid, $userHid, ['max_items' => $maxItems]) as $row) {
            if ($row->request_id === $current->request_id || $row->isRateLimited()) {
                continue;
            }
            $known = true;
            if ($row->hasDeviceSignals()) {
                $devices[] = $row->device_id;
            }
            if ($row->public_ip->country !== '') {
                $countries[] = $row->public_ip->country;
            }
        }
        $newDevice = $current->hasDeviceSignals() && !in_array($current->device_id, $devices, true);
        $newCountry = $current->public_ip->country !== '' && !in_array($current->public_ip->country, $countries, true);
        return ['known_account' => $known, 'new_device' => $newDevice, 'new_country' => $newCountry,
            'suspicious' => $known && $newDevice && $newCountry];
    }

    /**
     * Ban evasion: a banned device, or a banned account on the same device.
     *
     * @param callable(string): bool $isBannedDevice
     * @param callable(string): bool $isBannedAccount
     */
    public function linkedToBannedAccount(Identification $identification, callable $isBannedDevice, callable $isBannedAccount): bool
    {
        if (!$identification->hasDeviceSignals()) {
            return false;
        }
        if ($isBannedDevice($identification->device_id)) {
            return true;
        }
        foreach ($this->accountsOn(LookupType::DeviceId, $identification->device_id) as $hid) {
            if ($isBannedAccount($hid)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Promo, bonus and free-trial abuse: null when the redemption may go ahead, else a reason.
     *
     * @param string $accountHid the User HID of the redeeming account
     * @param callable(string): bool $redeemedOnDevice reads your redemptions table
     */
    public function mayRedeem(Identification $identification, string $accountHid, callable $redeemedOnDevice): ?string
    {
        if (!$identification->hasDeviceSignals()) {
            return 'no_device_signals';
        }
        if ($redeemedOnDevice($identification->device_id)) {
            return 'already_redeemed_on_device';
        }
        // Accounts ShieldLabs saw on this device (only those whose signed-in pages passed a User HID),
        // plus the redeeming account, which may not be among them yet.
        $accounts = $this->accountsOn(LookupType::DeviceId, $identification->device_id, 200);
        $accounts[] = $accountHid;
        if (count(array_unique($accounts)) >= 3) {
            return 'many_accounts_on_device';
        }
        return null;
    }
}
```

## At the action

```php
$abuse = new AccountAbuse($shieldlabs);

// Signup: the History API plus your own table of devices per account. The account being created is
// in neither yet: count it, so 2 existing accounts + this one = 3.
$seen = count($abuse->accountsOn(LookupType::DeviceId, $identification->device_id));
if (max($seen, $this->accountDevices->countAccounts($identification->device_id)) + 1 >= 3) {
    $this->holdRewards($account, 'many_accounts_on_device');
}

// Seat check: the account's devices of the last 30 days, and this one.
$since = new DateTimeImmutable('-30 days', new DateTimeZone('UTC'));
$devices = $abuse->devicesOfAccount($userHid, $since);
if ($identification->hasDeviceSignals()) {
    $devices[] = $identification->device_id;
}
if (count(array_unique($devices)) >= 4) {
    $this->flagForReview($account, 'account_sharing');
}

// Login, after the password check: the form identified anonymously.
$ato = $abuse->takeoverCheck($userHid, $identification);
if ($ato['suspicious'] || $abuse->impossibleTravel($userHid, $identification) !== null) {
    return $this->requireSecondFactor($account);
}
```

History calls throw the SDK exceptions (`RateLimitException`, `ServerException`,
`ApiConnectionException`, `ApiTimeoutException`, `AuthenticationException`). On a request path,
catch `ShieldLabsException` and fall back to step-up or review.
