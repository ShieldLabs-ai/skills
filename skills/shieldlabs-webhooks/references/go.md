# Webhooks in Go

Use the verified raw envelope for current deliveries. Its `event_id` is the delivery key;
`data.identification_id` correlates the visit. Use the verified envelope for these identifiers.
The application-provided enqueue-once service must reject an empty key and atomically persist
its dedup record and job (transaction/outbox). Roll back on failure and commit before 2xx.
This queue API is application code, not a ShieldLabs SDK method.
Do not enqueue only the old normalized data model.
Route by the verified raw `event_type`, including `hre.multi_account.changed` even when the SDK
represents it as an unknown event. Validate known current shapes against the bundled
[wire schema](../assets/webhook-event.schema.json) before enqueueing; reject an invalid known
payload with 400. Require a nonempty signed `event_id`. Use the
[High-Risk Event consumer](high-risk-events.md) for the queued group transition.
Queue failures must return a retryable non-2xx; never acknowledge a lost job.



Package `github.com/ShieldLabs-ai/shieldlabs-go/webhook`. `webhook.ConstructEvent(payload, header,
secrets...)` verifies the signature and returns a typed `webhook.Event`:
`*webhook.IdentificationScoredEvent` (with `Data`, a `*shieldlabs.Identification`),
`*webhook.PingEvent` or `*webhook.UnknownEvent`. Errors match `webhook.ErrSignature` (answer 401)
or `webhook.ErrParse` (answer 400). `webhook.VerifySignature(payload, header, secrets...)` returns
a `bool`; `webhook.SignatureHeader` is `"X-Shield-Signature"`.

## `net/http`

```go
import (
	"bytes"
	"encoding/json"
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

	if event.Type() == "identification.scored" || event.Type() == "hre.multi_account.changed" {
		// Decode the same already-verified bytes; keep all fields and numeric precision.
		var envelope map[string]any
		decoder := json.NewDecoder(bytes.NewReader(body))
		decoder.UseNumber()
		if err := decoder.Decode(&envelope); err != nil {
			http.Error(w, "invalid payload", http.StatusBadRequest)
			return
		}
		eventID, ok := envelope["event_id"].(string)
		if !ok || eventID == "" {
			http.Error(w, "missing event_id", http.StatusBadRequest)
			return
		}
		if err := a.jobs.EnqueueOnce(r.Context(), eventID, envelope); err != nil {
			http.Error(w, "queue unavailable", http.StatusServiceUnavailable)
			return
		}
	}
	w.WriteHeader(http.StatusOK)
}
```

Use a durable queue/outbox and acknowledge promptly after it commits. To
rotate a secret, pass both: `webhook.ConstructEvent(body, header, newSecret, oldSecret)`.

## Event data

`e.Data` is the same `shieldlabs.Identification` the History API returns: `RequestID`,
`DeviceID`, `UserHID` (`*string`), `PublicIP.Country`, `RiskScore`, `Signals`, `DetectionFlags`,
`ObservedAt`, `Source` and `Raw`. `e.Data.Band()` gives the risk band. The envelope fields are
`e.EventType`, `e.SchemaVersion` and `e.CreatedAt`.
