# Java server integration

Use the existing Java backend and its HTTP client for the current public domain-scoped History
API. Install the official ShieldLabs SDK for its User HID, signature and webhook helpers:
`Maven ai.shieldlabs:shieldlabs-java`. Keep the Private API Key and `SHIELDLABS_DOMAIN_ID` in the server environment.
Resolve that public domain UUID through MCP list_domains or `GET /api/v1/domains`.

## Read a current card

```java
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

final class ShieldHistory {
    private final HttpClient http = HttpClient.newHttpClient();
    private final ObjectMapper json = new ObjectMapper();

    // Validate domain UUID, resource and ID before calling; do not follow cross-origin redirects.
    JsonNode readCard(String resource, String id) throws Exception {
        String domain = System.getenv("SHIELDLABS_DOMAIN_ID");
        String encoded = URLEncoder.encode(id, StandardCharsets.UTF_8).replace("+", "%20");
        var request = HttpRequest.newBuilder(URI.create("https://account.shieldlabs.ai/api/v1/domains/"
                + domain + "/history/" + resource + "/" + encoded))
                .timeout(Duration.ofSeconds(5))
                .header("Authorization", "Bearer " + System.getenv("SHIELDLABS_API_KEY"))
                .header("Accept", "application/json").GET().build();
        var response = http.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() != 200) throw new IllegalStateException("History status " + response.statusCode());
        var card = json.readTree(response.body()).path("data");
        String expectedType = resource.equals("identifications") ? "identification" : resource;
        if (!domain.equals(card.path("domain_id").asText()) || !id.equals(card.path("id").asText())
                || !expectedType.equals(card.path("type").asText()))
            throw new IllegalStateException("History identity mismatch");
        return card;
    }
}
```

The sample performs one HTTP read. For a new identification, wrap reads in the bounded wait below.
Use `identifications` for the browser UUID; `user` for the exact server-generated HID; `visitor`,
`device` or `ip` for other cards. Check resource type, ID and domain before trusting a result.
See [current History](current-history.md) for the wire schema, filters and relations.

## Wait and handle errors

Use one total ten-second budget and one HTTP attempt per poll. Start immediately, then wait
250 ms, 500 ms, 1 s, 1.5 s and every 2 s, cutting the final wait to the remaining budget.
A missing/not-yet-available card can be read again for that same UUID. Preserve persistent errors.
After HTTP 429 wait the longest of the scheduled wait, 1 s and Retry-After capped at 10 s;
when that capped delay exceeds the time left, stop with the error. Connection errors, timeouts
and 5xx may retry within this budget. Stop on 400, 401, 402 or 403. A structured missing card is
unverified; a wrong route or malformed response is a configuration error.

Outside the wait, follow Retry-After as sent, capped at 10 s (0 retries at once); a 429 without
it waits at least 1 s. Keep retries bounded. HTTP 429 `rate_limited` is separate from the public
Banned IP `banned_ip` signal. Do not infer a billing cause from a missing result or status alone.

## Apply action policy

Treat a missing card, unavailable risk or unavailable signals as unverified. On an identification,
require numeric risk.score in 0–100 and an available band; read signal codes from signals.items.
Do not turn missing data into 0, an empty known flag set or a verified human.

Before performing the action: enforce a five-minute freshness limit using created_at, atomically
claim the identification UUID once, compare user_hid to the authenticated account's server HID
when signed in, then apply the application's policy for bands and signal codes. Refuse/review/
step-up on failures. Use a unique database key or Redis SET NX for replay protection; an unavailable
store cannot authorize the action. Do not pass this entity card directly to an SDK policy helper
that expects a normalized webhook Identification model.

History reads do not consume browser identifications. For signed webhooks, use the
[Java receiver](../../shieldlabs-webhooks/references/java.md); for account hashing, use
[User HID in Java](../../shieldlabs-user-linking/references/java.md).
