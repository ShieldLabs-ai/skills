# Account-abuse helpers in Go

Built on `client.History.All(ctx, lookup, value, opts)`, an `iter.Seq2[*shieldlabs.Identification,
error]` that yields identifications newest first and skips rows repeated between pages.

```go
package abuse

import (
	"context"
	"math"
	"time"

	shieldlabs "github.com/ShieldLabs-ai/shieldlabs-go"
)

var notAnAccount = map[string]bool{"anonymous": true, "fail": true, "-1": true, "unknown": true}

func accountOf(ident *shieldlabs.Identification) (string, bool) {
	if ident.UserHID == nil || *ident.UserHID == "" || notAnAccount[*ident.UserHID] {
		return "", false
	}
	return *ident.UserHID, true
}

func upTo(maxItems int) *shieldlabs.HistoryIterateOptions {
	return &shieldlabs.HistoryIterateOptions{MaxItems: maxItems}
}

// AccountsOn returns the distinct accounts (User HIDs) seen on one device or one visitor
// (multi-accounting). lookup is shieldlabs.LookupDeviceID or shieldlabs.LookupVisitorID.
func AccountsOn(ctx context.Context, c *shieldlabs.Client, lookup shieldlabs.LookupType, id string, maxItems int) (map[string]bool, error) {
	accounts := map[string]bool{}
	if id == shieldlabs.NilUUID {
		return accounts, nil
	}
	for ident, err := range c.History.All(ctx, lookup, id, upTo(maxItems)) {
		if err != nil {
			return nil, err
		}
		if hid, ok := accountOf(ident); ok {
			accounts[hid] = true
		}
	}
	return accounts, nil
}

// DevicesOfAccount returns the distinct devices of one account since a point in time (account sharing).
func DevicesOfAccount(ctx context.Context, c *shieldlabs.Client, userHID string, since time.Time, maxItems int) (map[string]bool, error) {
	devices := map[string]bool{}
	for ident, err := range c.History.All(ctx, shieldlabs.LookupUserHID, userHID, upTo(maxItems)) {
		if err != nil {
			return nil, err
		}
		if !ident.ObservedAt.IsZero() && ident.ObservedAt.Before(since) {
			break // newest first: the rest is older
		}
		if ident.DeviceID != shieldlabs.NilUUID {
			devices[ident.DeviceID] = true
		}
	}
	return devices, nil
}

// TravelJump is a change of country between an earlier identification of the account and the
// current one.
type TravelJump struct {
	From, To         string // countries of the earlier and the current identification
	Minutes          int
	EarlierRequestID string
}

// masked reports a VPN, proxy, Tor or relay, which hides the real country.
func masked(i *shieldlabs.Identification) bool {
	f := i.DetectionFlags
	return f.VPN || f.Proxy || f.Tor || f.PrivacyRelay || f.BrowserVPNProxy
}

// ImpossibleTravel reports when the current identification comes from another country than an
// identification of the same account less than `within` before it. Identifications without a
// country, through a VPN, proxy, Tor or relay, or with the rate-limit marker are skipped. It
// returns nil when there is no such jump.
func ImpossibleTravel(ctx context.Context, c *shieldlabs.Client, userHID string, current *shieldlabs.Identification, within time.Duration, maxItems int) (*TravelJump, error) {
	at, country := current.ObservedAt, current.PublicIP.Country
	if country == "" || at.IsZero() || masked(current) || current.IsRateLimited() {
		return nil, nil
	}
	for ident, err := range c.History.All(ctx, shieldlabs.LookupUserHID, userHID, upTo(maxItems)) {
		if err != nil {
			return nil, err
		}
		if ident.RequestID == current.RequestID || ident.ObservedAt.IsZero() || ident.ObservedAt.After(at) {
			continue // only identifications before the current one
		}
		gap := at.Sub(ident.ObservedAt)
		if gap > within {
			break // newest first: the rest is older
		}
		if ident.PublicIP.Country == "" || masked(ident) || ident.IsRateLimited() {
			continue
		}
		if ident.PublicIP.Country != country {
			return &TravelJump{From: ident.PublicIP.Country, To: country,
				Minutes: int(math.Round(gap.Minutes())), EarlierRequestID: ident.RequestID}, nil
		}
	}
	return nil, nil
}

// TakeoverCheck compares the login's identification with the account's history (account takeover).
type TakeoverCheck struct {
	KnownAccount, NewDevice, NewCountry bool
}

// Suspicious reports a known account on a new device and from a new country.
func (t TakeoverCheck) Suspicious() bool { return t.KnownAccount && t.NewDevice && t.NewCountry }

func CheckTakeover(ctx context.Context, c *shieldlabs.Client, userHID string, current *shieldlabs.Identification, maxItems int) (TakeoverCheck, error) {
	devices, countries := map[string]bool{}, map[string]bool{}
	var result TakeoverCheck
	for ident, err := range c.History.All(ctx, shieldlabs.LookupUserHID, userHID, upTo(maxItems)) {
		if err != nil {
			return TakeoverCheck{}, err
		}
		if ident.RequestID == current.RequestID || ident.IsRateLimited() {
			continue
		}
		result.KnownAccount = true
		if ident.DeviceID != shieldlabs.NilUUID {
			devices[ident.DeviceID] = true
		}
		if ident.PublicIP.Country != "" {
			countries[ident.PublicIP.Country] = true
		}
	}
	result.NewDevice = current.DeviceID != shieldlabs.NilUUID && !devices[current.DeviceID]
	result.NewCountry = current.PublicIP.Country != "" && !countries[current.PublicIP.Country]
	return result, nil
}

// BanStore is your own record of banned accounts and their devices.
type BanStore interface {
	IsBannedDevice(ctx context.Context, deviceID string) (bool, error)
	IsBannedAccount(ctx context.Context, userHID string) (bool, error)
}

// LinkedToBannedAccount reports ban evasion: a banned device, or a banned account on the same device.
func LinkedToBannedAccount(ctx context.Context, c *shieldlabs.Client, ident *shieldlabs.Identification, bans BanStore) (bool, error) {
	if ident.DeviceID == shieldlabs.NilUUID {
		return false, nil
	}
	if banned, err := bans.IsBannedDevice(ctx, ident.DeviceID); err != nil || banned {
		return banned, err
	}
	accounts, err := AccountsOn(ctx, c, shieldlabs.LookupDeviceID, ident.DeviceID, 500)
	if err != nil {
		return false, err
	}
	for hid := range accounts {
		if banned, err := bans.IsBannedAccount(ctx, hid); err != nil || banned {
			return banned, err
		}
	}
	return false, nil
}

// MayRedeem enforces one redemption per device (redeemedOnDevice reads your redemptions table) and
// refuses crowded devices (promo, bonus, trial abuse), counting the redeeming account (accountHID,
// its User HID). It returns "" when the redemption may go ahead, otherwise a reason.
func MayRedeem(ctx context.Context, c *shieldlabs.Client, ident *shieldlabs.Identification, accountHID string, redeemedOnDevice func(string) (bool, error)) (string, error) {
	if ident.DeviceID == shieldlabs.NilUUID {
		return "no_device_signals", nil
	}
	done, err := redeemedOnDevice(ident.DeviceID)
	if err != nil {
		return "", err
	}
	if done {
		return "already_redeemed_on_device", nil
	}
	// Accounts ShieldLabs saw on this device (only those whose signed-in pages passed a User HID),
	// plus the redeeming account, which may not be among them yet.
	accounts, err := AccountsOn(ctx, c, shieldlabs.LookupDeviceID, ident.DeviceID, 200)
	if err != nil {
		return "", err
	}
	accounts[accountHID] = true
	if len(accounts) >= 3 {
		return "many_accounts_on_device", nil
	}
	return "", nil
}
```

## At the action

```go
// Signup: the History API plus your own table of devices per account. The account being created is
// in neither yet: count it, so 2 existing accounts + this one = 3.
seen, err := abuse.AccountsOn(ctx, client, shieldlabs.LookupDeviceID, ident.DeviceID, 500)
recorded := accountDevices.CountAccounts(ctx, ident.DeviceID)
if err != nil || max(len(seen), recorded)+1 >= 3 {
	holdRewards(account, "many_accounts_on_device") // an error holds the reward too
}

// Seat check: the account's devices of the last 30 days, and this one.
devices, err := abuse.DevicesOfAccount(ctx, client, hid, time.Now().AddDate(0, 0, -30), 500)
if err == nil && ident.DeviceID != shieldlabs.NilUUID {
	devices[ident.DeviceID] = true
}
if err != nil || len(devices) >= 4 {
	flagForReview(account, "account_sharing") // an error flags the seat for review too
}

// Login, after the password check: the form identified anonymously.
ato, err := abuse.CheckTakeover(ctx, client, hid, ident, 200)
if err != nil || ato.Suspicious() {
	return requireSecondFactor(account) // an error falls back to step-up, never to allow
}
travel, err := abuse.ImpossibleTravel(ctx, client, hid, ident, time.Hour, 100)
if err != nil || travel != nil {
	return requireSecondFactor(account)
}
```

History calls return SDK errors (`shieldlabs.ErrRateLimited`, `ErrServer`, `ErrConnection`,
`ErrTimeout`, `ErrAuthentication`). On a request path, fall back to step-up or review on error.
