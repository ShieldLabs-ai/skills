# Account-abuse helpers in Java

Built on `client.history().stream(LookupType, value, HistoryIterateOptions)`, a lazy
`Stream<Identification>` newest first that skips rows repeated between pages (`iterate(...)` gives
the same as an `Iterable`).

```java
import ai.shieldlabs.*;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.function.Predicate;
import java.util.stream.Collectors;

public final class AccountAbuse {
    private static final Set<String> NOT_AN_ACCOUNT = Set.of("anonymous", "fail", "-1", "unknown");
    private final ShieldLabsClient client;

    public AccountAbuse(ShieldLabsClient client) {
        this.client = client;
    }

    static boolean isAccount(String userHid) {
        return userHid != null && !userHid.isEmpty() && !NOT_AN_ACCOUNT.contains(userHid);
    }

    private static HistoryIterateOptions max(int items) {
        return HistoryIterateOptions.builder().maxItems(items).build();
    }

    /** A VPN, proxy, Tor or relay hides the real country. */
    private static boolean masked(Identification i) {
        DetectionFlags f = i.getDetectionFlags();
        return f.isVpn() || f.isProxy() || f.isTor() || f.isPrivacyRelay() || f.isBrowserVpnProxy();
    }

    /** Multi-accounting: the distinct accounts (User HIDs) on one device or visitor (DEVICE_ID or VISITOR_ID). */
    public Set<String> accountsOn(LookupType lookup, String id, int maxItems) {
        if (Risk.NIL_DEVICE_ID.equals(id)) return Set.of();
        return client.history().stream(lookup, id, max(maxItems))
                .map(Identification::getUserHid)
                .filter(AccountAbuse::isAccount)
                .collect(Collectors.toSet());
    }

    /** Account sharing: the distinct devices of one account since a point in time. */
    public Set<String> devicesOfAccount(String userHid, Instant since, int maxItems) {
        return client.history().stream(LookupType.USER_HID, userHid, max(maxItems))
                .takeWhile(i -> i.getObservedAt() == null || !i.getObservedAt().isBefore(since)) // newest first
                .map(Identification::getDeviceId)
                .filter(id -> !Risk.NIL_DEVICE_ID.equals(id))
                .collect(Collectors.toSet());
    }

    public static final class TravelJump {
        public final String from, to, earlierRequestId; // countries of the earlier and the current identification
        public final long minutes;

        TravelJump(String from, String to, long minutes, String earlierRequestId) {
            this.from = from; this.to = to; this.minutes = minutes; this.earlierRequestId = earlierRequestId;
        }
    }

    /**
     * Impossible travel at an action: the current identification comes from another country than an
     * identification of the same account less than {@code within} before it. Identifications without a
     * country, through a VPN, proxy, Tor or relay, or with the rate-limit marker are skipped.
     */
    public Optional<TravelJump> impossibleTravel(String userHid, Identification current, Duration within, int maxItems) {
        Instant at = current.getObservedAt();
        String country = current.getPublicIp().getCountry();
        if (country.isEmpty() || at == null || masked(current) || Risk.isRateLimited(current.getRiskScore())) {
            return Optional.empty();
        }
        for (Identification item : client.history().iterate(LookupType.USER_HID, userHid, max(maxItems))) {
            Instant observed = item.getObservedAt();
            if (item.getRequestId().equals(current.getRequestId()) || observed == null || observed.isAfter(at)) {
                continue; // only identifications before the current one
            }
            Duration gap = Duration.between(observed, at);
            if (gap.compareTo(within) > 0) break; // newest first: the rest is older
            String earlier = item.getPublicIp().getCountry();
            if (earlier.isEmpty() || masked(item) || Risk.isRateLimited(item.getRiskScore())) continue;
            if (!earlier.equals(country)) {
                return Optional.of(new TravelJump(earlier, country, gap.toMinutes(), item.getRequestId()));
            }
        }
        return Optional.empty();
    }

    /** Account takeover at login: true for a known account on a new device and from a new country. */
    public boolean looksLikeTakeover(String userHid, Identification current, int maxItems) {
        Set<String> devices = new HashSet<>();
        Set<String> countries = new HashSet<>();
        boolean known = false;
        for (Identification item : client.history().iterate(LookupType.USER_HID, userHid, max(maxItems))) {
            if (item.getRequestId().equals(current.getRequestId()) || Risk.isRateLimited(item.getRiskScore())) continue;
            known = true;
            if (!Risk.NIL_DEVICE_ID.equals(item.getDeviceId())) devices.add(item.getDeviceId());
            if (!item.getPublicIp().getCountry().isEmpty()) countries.add(item.getPublicIp().getCountry());
        }
        boolean newDevice = !Risk.NIL_DEVICE_ID.equals(current.getDeviceId()) && !devices.contains(current.getDeviceId());
        String country = current.getPublicIp().getCountry();
        boolean newCountry = !country.isEmpty() && !countries.contains(country);
        return known && newDevice && newCountry;
    }

    /** Ban evasion: a banned device, or a banned account on the same device. */
    public boolean linkedToBannedAccount(Identification identification, Predicate<String> isBannedDevice, Predicate<String> isBannedAccount) {
        String deviceId = identification.getDeviceId();
        if (Risk.NIL_DEVICE_ID.equals(deviceId)) return false;
        if (isBannedDevice.test(deviceId)) return true;
        return accountsOn(LookupType.DEVICE_ID, deviceId, 500).stream().anyMatch(isBannedAccount);
    }

    /**
     * Promo, bonus and free-trial abuse: empty when the redemption may go ahead, else a reason.
     * {@code accountHid} is the User HID of the redeeming account.
     */
    public Optional<String> refuseRedemption(Identification identification, String accountHid, Predicate<String> redeemedOnDevice) {
        String deviceId = identification.getDeviceId();
        if (Risk.NIL_DEVICE_ID.equals(deviceId)) return Optional.of("no_device_signals");
        if (redeemedOnDevice.test(deviceId)) return Optional.of("already_redeemed_on_device"); // your redemptions table
        // Accounts ShieldLabs saw on this device (only those whose signed-in pages passed a User HID),
        // plus the redeeming account, which may not be among them yet.
        Set<String> accounts = new HashSet<>(accountsOn(LookupType.DEVICE_ID, deviceId, 200));
        accounts.add(accountHid);
        if (accounts.size() >= 3) return Optional.of("many_accounts_on_device");
        return Optional.empty();
    }
}
```

## At the action

```java
AccountAbuse abuse = new AccountAbuse(client);

// Signup: the History API plus your own table of devices per account. The account being created is
// in neither yet: count it, so 2 existing accounts + this one = 3.
int seen = abuse.accountsOn(LookupType.DEVICE_ID, identification.getDeviceId(), 500).size();
if (Math.max(seen, accountDevices.countAccounts(identification.getDeviceId())) + 1 >= 3) {
    holdRewards(account, "many_accounts_on_device");
}
// Seat check: the account's devices of the last 30 days, and this one.
Set<String> devices = new HashSet<>(abuse.devicesOfAccount(userHid, Instant.now().minus(Duration.ofDays(30)), 500));
if (!Risk.NIL_DEVICE_ID.equals(identification.getDeviceId())) devices.add(identification.getDeviceId());
if (devices.size() >= 4) {
    flagForReview(account, "account_sharing");
}
// Login, after the password check: the form identified anonymously.
if (abuse.looksLikeTakeover(userHid, identification, 200)
        || abuse.impossibleTravel(userHid, identification, Duration.ofHours(1), 100).isPresent()) {
    return requireSecondFactor(account);
}
```

History calls throw the SDK exceptions (`RateLimitException`, `ServerException`,
`ApiConnectionException`, `ApiTimeoutException`, `AuthenticationException`). On a request path,
catch `ShieldLabsException` and fall back to step-up or review.
