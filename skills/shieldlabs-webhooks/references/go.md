# Webhooks in Go

Package `github.com/ShieldLabs-ai/shieldlabs-go/webhook`. `webhook.ConstructEvent(payload, header,
secrets...)` verifies the signature and returns a typed `webhook.Event`:
`*webhook.IdentificationScoredEvent` (with `Data`, a `*shieldlabs.Identification`),
`*webhook.PingEvent` or `*webhook.UnknownEvent`. Errors match `webhook.ErrSignature` (answer 401)
or `webhook.ErrParse` (answer 400). `webhook.VerifySignature(payload, header, secrets...)` returns
a `bool`; `webhook.SignatureHeader` is `"X-Shield-Signature"`.

## `net/http`

```go
import (
	"errors"
	"io"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/ShieldLabs-ai/shieldlabs-go/webhook"
)

// webhookSecrets reads SHIELDLABS_WEBHOOK_SECRET once at startup (several secrets, comma-separated,
// while you rotate one) into app.webhookSecrets.
func webhookSecrets() []string {
	var secrets []string
	for _, s := range strings.Split(os.Getenv("SHIELDLABS_WEBHOOK_SECRET"), ",") {
		if s = strings.TrimSpace(s); s != "" {
			secrets = append(secrets, s)
		}
	}
	if len(secrets) == 0 {
		log.Print("SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500")
	}
	return secrets
}

func (a *app) shieldlabsWebhook(w http.ResponseWriter, r *http.Request) {
	if len(a.webhookSecrets) == 0 { // a configuration error, not a bad signature
		http.Error(w, "webhook secret not configured", http.StatusInternalServerError)
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, 1<<20)) // the raw bytes
	if err != nil {
		http.Error(w, "cannot read the body", http.StatusBadRequest)
		return
	}
	event, err := webhook.ConstructEvent(body, r.Header.Get(webhook.SignatureHeader), a.webhookSecrets...)
	switch {
	case errors.Is(err, webhook.ErrSignature):
		http.Error(w, "invalid signature", http.StatusUnauthorized)
		return
	case err != nil:
		http.Error(w, "invalid payload", http.StatusBadRequest)
		return
	}

	switch e := event.(type) {
	case *webhook.IdentificationScoredEvent:
		// claimDelivery: atomic "first time" check, separate from the action replay store.
		if a.claimDelivery(r.Context(), e.Data.RequestID) {
			a.jobs <- e.Data // hand off; the worker does the slow part
		}
	case *webhook.PingEvent:
		log.Print("webhook.ping received")
	default:
		log.Printf("ignoring event type %s", event.Type())
	}
	w.WriteHeader(http.StatusOK)
}
```

Keep the channel buffered (or use a real queue) so the handler never blocks past one second. To
rotate a secret, pass both: `webhook.ConstructEvent(body, header, newSecret, oldSecret)`.

## Event data

`e.Data` is the same `shieldlabs.Identification` the History API returns: `RequestID`,
`DeviceID`, `UserHID` (`*string`), `PublicIP.Country`, `RiskScore`, `Signals`, `DetectionFlags`,
`ObservedAt`, `Source` and `Raw`. `e.Data.Band()` gives the risk band. The envelope fields are
`e.EventType`, `e.SchemaVersion` and `e.CreatedAt`.
