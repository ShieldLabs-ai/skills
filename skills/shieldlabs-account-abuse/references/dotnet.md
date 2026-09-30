# Account-abuse helpers in .NET

Built on `client.History.IterateAsync(LookupType, value, HistoryIterateOptions?, CancellationToken)`,
an `IAsyncEnumerable<Identification>` newest first that skips rows repeated between pages.

```csharp
using ShieldLabs;

public sealed class AccountAbuse(ShieldLabsClient client)
{
    private const string NilUuid = "00000000-0000-0000-0000-000000000000";
    private static readonly HashSet<string> NotAnAccount = new() { "anonymous", "fail", "-1", "unknown" };

    private static bool IsAccount(string? userHid) => !string.IsNullOrEmpty(userHid) && !NotAnAccount.Contains(userHid);

    private static HistoryIterateOptions UpTo(int maxItems) => new() { MaxItems = maxItems };

    /// <summary>A VPN, proxy, Tor or relay hides the real country.</summary>
    private static bool Masked(Identification i) =>
        i.DetectionFlags.Vpn || i.DetectionFlags.Proxy || i.DetectionFlags.Tor ||
        i.DetectionFlags.PrivacyRelay || i.DetectionFlags.BrowserVpnProxy;

    /// <summary>Multi-accounting: the distinct accounts (User HIDs) on one device or visitor (DeviceId or VisitorId).</summary>
    public async Task<HashSet<string>> AccountsOnAsync(LookupType lookup, string id, int maxItems = 500, CancellationToken ct = default)
    {
        var accounts = new HashSet<string>();
        if (id == NilUuid) return accounts;
        await foreach (var row in client.History.IterateAsync(lookup, id, UpTo(maxItems), ct))
        {
            if (IsAccount(row.UserHid)) accounts.Add(row.UserHid!);
        }
        return accounts;
    }

    /// <summary>Account sharing: the distinct devices of one account since a point in time.</summary>
    public async Task<HashSet<string>> DevicesOfAccountAsync(string userHid, DateTimeOffset since, int maxItems = 500, CancellationToken ct = default)
    {
        var devices = new HashSet<string>();
        await foreach (var row in client.History.IterateAsync(LookupType.UserHid, userHid, UpTo(maxItems), ct))
        {
            if (row.ObservedAt != DateTimeOffset.MinValue && row.ObservedAt < since) break; // newest first: the rest is older
            if (row.DeviceId != NilUuid) devices.Add(row.DeviceId);
        }
        return devices;
    }

    /// <summary>A change of country: From is the earlier identification, To the current one.</summary>
    public sealed record TravelJump(string From, string To, int Minutes, string EarlierRequestId);

    /// <summary>
    /// Impossible travel at an action: the current identification comes from another country than an
    /// identification of the same account less than <paramref name="within"/> before it. Identifications
    /// without a country, through a VPN, proxy, Tor or relay, or with the rate-limit marker are skipped.
    /// </summary>
    public async Task<TravelJump?> ImpossibleTravelAsync(string userHid, Identification current, TimeSpan within, int maxItems = 100, CancellationToken ct = default)
    {
        var at = current.ObservedAt;
        var country = current.PublicIp.Country;
        if (country.Length == 0 || at == DateTimeOffset.MinValue || Masked(current) || Risk.IsRateLimited(current.RiskScore)) return null;
        await foreach (var row in client.History.IterateAsync(LookupType.UserHid, userHid, UpTo(maxItems), ct))
        {
            if (row.RequestId == current.RequestId || row.ObservedAt == DateTimeOffset.MinValue || row.ObservedAt > at) continue; // only earlier ones
            var gap = at - row.ObservedAt;
            if (gap > within) break; // newest first: the rest is older
            if (row.PublicIp.Country.Length == 0 || Masked(row) || Risk.IsRateLimited(row.RiskScore)) continue;
            if (row.PublicIp.Country != country)
            {
                return new TravelJump(row.PublicIp.Country, country, (int)Math.Round(gap.TotalMinutes), row.RequestId);
            }
        }
        return null;
    }

    /// <summary>Account takeover at login: true for a known account on a new device and from a new country.</summary>
    public async Task<bool> LooksLikeTakeoverAsync(string userHid, Identification current, int maxItems = 200, CancellationToken ct = default)
    {
        var devices = new HashSet<string>();
        var countries = new HashSet<string>();
        var known = false;
        await foreach (var row in client.History.IterateAsync(LookupType.UserHid, userHid, UpTo(maxItems), ct))
        {
            if (row.RequestId == current.RequestId || Risk.IsRateLimited(row.RiskScore)) continue;
            known = true;
            if (row.DeviceId != NilUuid) devices.Add(row.DeviceId);
            if (row.PublicIp.Country.Length > 0) countries.Add(row.PublicIp.Country);
        }
        var newDevice = current.DeviceId != NilUuid && !devices.Contains(current.DeviceId);
        var newCountry = current.PublicIp.Country.Length > 0 && !countries.Contains(current.PublicIp.Country);
        return known && newDevice && newCountry;
    }

    /// <summary>Ban evasion: a banned device, or a banned account on the same device.</summary>
    public async Task<bool> LinkedToBannedAccountAsync(Identification identification, Func<string, Task<bool>> isBannedDevice,
        Func<string, Task<bool>> isBannedAccount, CancellationToken ct = default)
    {
        if (identification.DeviceId == NilUuid) return false;
        if (await isBannedDevice(identification.DeviceId)) return true;
        foreach (var hid in await AccountsOnAsync(LookupType.DeviceId, identification.DeviceId, 500, ct))
        {
            if (await isBannedAccount(hid)) return true;
        }
        return false;
    }

    /// <summary>
    /// Promo, bonus and free-trial abuse: null when the redemption may go ahead, else a reason.
    /// <paramref name="accountHid"/> is the User HID of the redeeming account.
    /// </summary>
    public async Task<string?> RefuseRedemptionAsync(Identification identification, string accountHid,
        Func<string, Task<bool>> redeemedOnDevice, CancellationToken ct = default)
    {
        if (identification.DeviceId == NilUuid) return "no_device_signals";
        if (await redeemedOnDevice(identification.DeviceId)) return "already_redeemed_on_device"; // your redemptions table
        // Accounts ShieldLabs saw on this device (only those whose signed-in pages passed a User HID),
        // plus the redeeming account, which may not be among them yet.
        var accounts = await AccountsOnAsync(LookupType.DeviceId, identification.DeviceId, 200, ct);
        accounts.Add(accountHid);
        if (accounts.Count >= 3) return "many_accounts_on_device";
        return null;
    }
}
```

## At the action

```csharp
var abuse = new AccountAbuse(shieldlabs);

// Signup: the History API plus your own table of devices per account. The account being created is
// in neither yet: count it, so 2 existing accounts + this one = 3.
var seen = (await abuse.AccountsOnAsync(LookupType.DeviceId, identification.DeviceId)).Count;
if (Math.Max(seen, await accountDevices.CountAccountsAsync(identification.DeviceId)) + 1 >= 3)
{
    await HoldRewardsAsync(account, "many_accounts_on_device");
}
// Seat check: the account's devices of the last 30 days, and this one.
var devices = await abuse.DevicesOfAccountAsync(userHid, DateTimeOffset.UtcNow.AddDays(-30));
if (identification.DeviceId != "00000000-0000-0000-0000-000000000000") devices.Add(identification.DeviceId);
if (devices.Count >= 4)
{
    await FlagForReviewAsync(account, "account_sharing");
}
// Login, after the password check: the form identified anonymously.
if (await abuse.LooksLikeTakeoverAsync(userHid, identification)
    || await abuse.ImpossibleTravelAsync(userHid, identification, TimeSpan.FromHours(1)) is not null)
{
    return RequireSecondFactor(account);
}
```

History calls throw the SDK exceptions (`RateLimitException`, `ServerException`,
`ApiConnectionException`, `ApiTimeoutException`, `AuthenticationException`). On a request path,
catch `ShieldLabsException` and fall back to step-up or review.
