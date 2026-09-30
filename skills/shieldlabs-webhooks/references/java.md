# Webhooks in Java

`ai.shieldlabs.Webhooks.constructEvent(payload, signatureHeader, secrets...)` takes the raw body as
`byte[]` (or `String`) and one or more secrets (varargs or a `Collection<String>`). It returns an
`IdentificationScoredEvent` (`getIdentification()`), a `WebhookPingEvent` or an
`UnknownWebhookEvent`, and throws `SignatureVerificationException` (answer 401) or
`WebhookParseException` (answer 400). `Webhooks.verifySignature(...)` returns a `boolean`;
`Webhooks.SIGNATURE_HEADER` is `"X-Shield-Signature"`.

`claimDelivery(requestId)` below stands for your atomic "first time" check (an insert on a unique
key), separate from the store of request IDs that authorized actions.

```java
List<String> secrets = Arrays.stream(System.getenv().getOrDefault("SHIELDLABS_WEBHOOK_SECRET", "").split(","))
        .map(String::trim)
        .filter(s -> !s.isEmpty())
        .collect(Collectors.toList());
if (secrets.isEmpty()) {
    System.getLogger("shieldlabs").log(System.Logger.Level.ERROR, "SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500");
}
```

Both receivers answer 500 while the list is empty: a missing secret is a configuration error, and a
401 would look like a wrong secret.

## Spring

`@RequestBody byte[]` gives the raw bytes; never bind the webhook to a DTO before verifying.

```java
@RestController
class ShieldLabsWebhookController {
    private final List<String> secrets;
    private final DeliveryStore deliveries;
    private final ExecutorService workers;

    ShieldLabsWebhookController(List<String> secrets, DeliveryStore deliveries, ExecutorService workers) {
        this.secrets = secrets;
        this.deliveries = deliveries;
        this.workers = workers;
    }

    @PostMapping("/webhooks/shieldlabs")
    ResponseEntity<Void> receive(@RequestBody byte[] body,
                                 @RequestHeader(name = Webhooks.SIGNATURE_HEADER, required = false) String signature) {
        if (secrets.isEmpty()) return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).build();
        WebhookEvent event;
        try {
            event = Webhooks.constructEvent(body, signature, secrets);
        } catch (SignatureVerificationException e) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build();
        } catch (WebhookParseException e) {
            return ResponseEntity.badRequest().build();
        }
        if (event instanceof IdentificationScoredEvent) {
            Identification identification = ((IdentificationScoredEvent) event).getIdentification();
            if (deliveries.claim(identification.getRequestId())) {
                workers.submit(() -> process(identification)); // answer within 1 second
            }
        }
        return ResponseEntity.ok().build(); // WebhookPingEvent and UnknownWebhookEvent: acknowledge
    }
}
```

If Spring Security's CSRF protection is on, exempt the webhook path (the signature authenticates
the request).

## `com.sun.net.httpserver`

```java
server.createContext("/webhooks/shieldlabs", exchange -> {
    byte[] body = exchange.getRequestBody().readAllBytes();
    String signature = exchange.getRequestHeaders().getFirst(Webhooks.SIGNATURE_HEADER);
    int status = 200;
    if (secrets.isEmpty()) {
        status = 500; // a configuration error, not a bad signature
    } else {
        try {
            WebhookEvent event = Webhooks.constructEvent(body, signature, secrets);
            if (event instanceof IdentificationScoredEvent) {
                Identification identification = ((IdentificationScoredEvent) event).getIdentification();
                if (claimDelivery(identification.getRequestId())) workers.submit(() -> process(identification));
            }
        } catch (SignatureVerificationException e) {
            status = 401;
        } catch (WebhookParseException e) {
            status = 400;
        }
    }
    exchange.sendResponseHeaders(status, -1);
    exchange.close();
});
```

## Event data

`getIdentification()` returns the same `Identification` the History API returns: `getRequestId()`,
`getDeviceId()`, `getUserHid()`, `getPublicIp().getCountry()`, `getRiskScore()`, `getSignals()`,
`getDetectionFlags()`, `getObservedAt()` and `raw()`. `Risk.band(identification.getRiskScore())`
gives the band. The envelope has `getType()`, `getSchemaVersion()` and `getCreatedAt()` (an `Instant`).
