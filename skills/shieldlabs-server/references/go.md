# Go with `shieldlabs-go`

Go 1.23 or later, standard library only. Module `github.com/ShieldLabs-ai/shieldlabs-go`,
package `shieldlabs`; webhooks live in the `webhook` subpackage.

## Install and create the client

```sh
go get github.com/ShieldLabs-ai/shieldlabs-go
```

```go
import (
	"log"
	"os"

	shieldlabs "github.com/ShieldLabs-ai/shieldlabs-go"
)

// newShieldLabsClient creates the History API client once, at startup.
func newShieldLabsClient() *shieldlabs.Client {
	opts := []shieldlabs.Option{shieldlabs.WithDomainID(os.Getenv("SHIELDLABS_DOMAIN_ID"))}
	if base := os.Getenv("SHIELDLABS_API_BASE_URL"); base != "" {
		opts = append(opts, shieldlabs.WithBaseURL(base)) // tests only; default https://account.shieldlabs.ai
	}
	client, err := shieldlabs.NewClient(os.Getenv("SHIELDLABS_API_KEY"), opts...)
	if err != nil {
		log.Fatal(err)
	}
	return client
}
```

Options: `WithBaseURL`, `WithHTTPClient`, `WithTimeout` (per attempt, default 10 s),
`WithMaxRetries` (default 2), `WithLogger` (configuration warnings only). The SDK reads no
environment variables. A client is safe for concurrent use: create one and share it.

## `net/http` handler

```go
type app struct {
	shieldlabs *shieldlabs.Client
	db         *sql.DB
}

func (a *app) signup(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Email     string `json:"email"`
		RequestID string `json:"requestId"`
	}
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&body); err != nil {
		http.Error(w, "invalid body", http.StatusBadRequest)
		return
	}

	var ident *shieldlabs.Identification
	if body.RequestID != "" {
		found, err := a.shieldlabs.Identifications.Get(r.Context(), body.RequestID, nil) // waits up to 10 s
		if err != nil {
			log.Printf("shieldlabs lookup failed: %v", err) // unverified, never clean
		} else {
			ident = found // nil when no identification appeared in time
		}
	}

	verdict := shieldlabs.EvaluateIdentification(ident, shieldlabs.EvaluateOptions{
		// Claim atomically; a store error counts as a replay so that failures refuse.
		IsReplay: func(requestID string) bool { return !a.claimRequestID(r.Context(), requestID) },
	})
	if !verdict.OK {
		log.Printf("signup refused: reason=%s band=%s flag=%s", verdict.Reason, verdict.Band, verdict.Flag)
		http.Error(w, "signup refused", http.StatusForbidden)
		return
	}
	// Create the account here.
	w.WriteHeader(http.StatusCreated)
}

// claimRequestID reports whether this is the first use of the request ID.
// CREATE TABLE used_request_ids (request_id uuid PRIMARY KEY, used_at timestamptz NOT NULL DEFAULT now());
func (a *app) claimRequestID(ctx context.Context, requestID string) bool {
	res, err := a.db.ExecContext(ctx,
		"INSERT INTO used_request_ids (request_id) VALUES ($1) ON CONFLICT DO NOTHING", requestID)
	if err != nil {
		return false
	}
	n, err := res.RowsAffected()
	return err == nil && n == 1
}
```

## `Identifications.Get` options

```go
ident, err := client.Identifications.Get(ctx, requestID, &shieldlabs.GetIdentificationOptions{
	Timeout: 5 * time.Second, // total budget of the wait, default 10 s
})

latest, err := client.Identifications.Get(ctx, requestID, &shieldlabs.GetIdentificationOptions{NoWait: true}) // one lookup
```

`nil` options and the zero value both wait with the defaults, because a zero field takes its
default: `Timeout: 0` means 10 s (never a zero budget) and `PollInterval: 0` means 250 ms (waits of
p, 2p, 4p, 6p, then 8p, each at most max(2 s, p); a `PollInterval` below 100 ms counts as 100 ms;
the last lookup runs at the deadline).
`(nil, nil)` means no identification was found in time. Each lookup is one HTTP attempt, and a
429, a 5xx, a network failure or an attempt timeout keeps it polling; at the deadline the error of
a failed last lookup is returned. A 400, 401, 403 or 404 ends the wait at once with an error
matching `shieldlabs.ErrBadRequest`, `ErrAuthentication` or `ErrNotFound`, and a 429 whose
`Retry-After` (capped at 10 s) is longer than the time left ends it at once with an error matching
`ErrRateLimited`; after any other 429 the next lookup waits the longest of the scheduled wait, 1 s
and the capped `Retry-After` (0 when missing), cut short at the deadline. `NoWait: true` makes a
single lookup, retried like any History request.

## `EvaluateIdentification`

```go
verdict := shieldlabs.EvaluateIdentification(ident, shieldlabs.EvaluateOptions{
	MaxAge:     5 * time.Minute,                             // zero means the default (5 minutes)
	BlockBands: []shieldlabs.Band{shieldlabs.BandDangerous}, // nil means the default; empty blocks none
	BlockFlags: []string{shieldlabs.FlagBrowserAutomation, shieldlabs.FlagJavaScriptDisabled},
	IsReplay:   isReplay,
})
// verdict.OK, verdict.Reason (shieldlabs.ReasonStale, ...), verdict.Band, verdict.Flag
```

Helpers: `shieldlabs.RiskBand(score)` (returns `BandRateLimited` above 100),
`shieldlabs.IsRateLimited(score)`, `ident.Band()`, `shieldlabs.NilUUID`.

## The `Identification` model

Fields: `RequestID`, `VisitorID`, `DeviceID`, `SessionID`, `CookieID`, `UserHID` (`*string`, nil
when none; `"anonymous"` for anonymous checks), `Domain`, `PublicIP` and `LocalIP` (`IP`,
`Country`), `ConnectionType`, `OS`, `Browser`, `DeviceType`, `TrafficSource`, `RiskScore`,
`Signals`, `DetectionFlags` (19 booleans such as `VPN`, `Proxy`, `Tor`, `AntiDetectBrowser`,
`BrowserAutomation`), `ObservedAt` (UTC `time.Time`), `Source`, `Raw`.

## Errors

Match with `errors.Is`: `ErrValidation` (nothing sent), `ErrBadRequest` (400),
`ErrAuthentication` (401, 403), `ErrQuotaExceeded` (402), `ErrNotFound` (404),
`ErrRateLimited` (429), `ErrServer` (5xx), `ErrConnection`, `ErrTimeout`. Every HTTP error is an
`*shieldlabs.APIError` with `StatusCode`, `Message`, `Body`, `Header` and `RetryAfter`. A
cancelled context stops at once.

## Management API

```go
mgmt, err := shieldlabs.NewManagementClient(os.Getenv("SHIELDLABS_SECRET_KEY"), os.Getenv("SHIELDLABS_DOMAIN"))
if err != nil {
	return err
}
profile, err := mgmt.GetProfile(ctx) // cache it: about 15 calls per minute per IP
if err != nil {
	return err
}
log.Printf("remaining identifications: %d", profile.RemainingIdentifications) // negative when the account is over its included volume
```
