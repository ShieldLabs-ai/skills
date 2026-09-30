# Risk decisions in Go

The `decide()` function of the skill on `shieldlabs.EvaluateIdentification`.

```go
package risk

import (
	"time"

	shieldlabs "github.com/ShieldLabs-ai/shieldlabs-go"
)

type Sensitivity string
type Decision string

const (
	Low    Sensitivity = "low"
	Medium Sensitivity = "medium"
	High   Sensitivity = "high"

	Allow  Decision = "allow"
	StepUp Decision = "step_up"
	Review Decision = "review"
	Block  Decision = "block"
)

var byBand = map[shieldlabs.Band]map[Sensitivity]Decision{
	shieldlabs.BandTrusted:    {Low: Allow, Medium: Allow, High: Allow},
	shieldlabs.BandSuspicious: {Low: Allow, Medium: StepUp, High: Review},
	shieldlabs.BandDangerous:  {Low: StepUp, Medium: Block, High: Block},
}

var unverified = map[Sensitivity]Decision{Low: Allow, Medium: StepUp, High: Review}

var userMismatch = map[Sensitivity]Decision{Low: StepUp, Medium: StepUp, High: Block}

var strictness = map[Decision]int{Allow: 0, StepUp: 1, Review: 2, Block: 3}

// Context carries what the policy needs besides the identification.
type Context struct {
	FirstUse        bool      // from your atomic claim of the request ID
	ExpectedUserHID string    // the session user's User HID; "" for anonymous actions
	Now             time.Time // zero value: time.Now()
}

func Decide(ident *shieldlabs.Identification, s Sensitivity, c Context) (Decision, string) {
	verdict := shieldlabs.EvaluateIdentification(ident, shieldlabs.EvaluateOptions{
		IsReplay:   func(string) bool { return !c.FirstUse },
		BlockBands: []shieldlabs.Band{}, // empty, non-nil: bands are mapped per sensitivity below
		Now:        c.Now,
	})
	switch verdict.Reason {
	case shieldlabs.ReasonReplayed, shieldlabs.ReasonStale, shieldlabs.ReasonBlockedFlag:
		return Block, string(verdict.Reason)
	case shieldlabs.ReasonMissing, shieldlabs.ReasonNoDeviceSignals:
		return unverified[s], string(verdict.Reason)
	case shieldlabs.ReasonRateLimited:
		if s == High {
			return Review, string(verdict.Reason)
		}
		return StepUp, string(verdict.Reason)
	}
	// Map the band first: a User HID mismatch can only make the decision stricter, never softer.
	decision := byBand[verdict.Band][s]
	if c.ExpectedUserHID != "" && (ident.UserHID == nil || *ident.UserHID != c.ExpectedUserHID) {
		if mismatch := userMismatch[s]; strictness[mismatch] > strictness[decision] {
			return mismatch, "user_mismatch"
		}
	}
	return decision, "band_" + string(verdict.Band)
}
```

## In a handler

```go
ident := a.readIdentification(r) // nil on any failure (shieldlabs-server skill)
firstUse := ident != nil && a.claimRequestID(r.Context(), ident.RequestID)
hid, _ := shieldlabs.UserHID(strconv.FormatInt(user.ID, 10), a.userHIDSecret)
decision, reason := risk.Decide(ident, risk.High, risk.Context{FirstUse: firstUse, ExpectedUserHID: hid})
log.Printf("payout decision=%s reason=%s", decision, reason)
switch decision {
case risk.Allow:
	a.createPayout(w, r)
case risk.StepUp:
	writeJSON(w, http.StatusAccepted, map[string]string{"next": "verify_second_factor"})
case risk.Review:
	a.holdPayoutForReview(w, r, reason)
default:
	http.Error(w, "request refused", http.StatusForbidden)
}
```

## Extra flag rules

```go
func stricterForHighValue(ident *shieldlabs.Identification, s Sensitivity) (Decision, bool) {
	f := ident.DetectionFlags
	if f.AntiDetectBrowser || f.Tor {
		switch s {
		case High:
			return Block, true
		case Medium:
			return StepUp, true
		}
	}
	return "", false
}
```

Helpers: `shieldlabs.RiskBand(score)`, `shieldlabs.IsRateLimited(score)`, `ident.Band()`,
`ident.DetectionFlags.Get(name)`, `shieldlabs.NilUUID`, and the flag name constants such as
`shieldlabs.FlagBrowserAutomation`.
