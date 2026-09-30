# Java with `ai.shieldlabs:shieldlabs-java`

Java 11 or later. Package `ai.shieldlabs`. The only runtime dependency is Jackson Databind. All
exceptions are unchecked.

## Install

Maven:

```xml
<dependency>
  <groupId>ai.shieldlabs</groupId>
  <artifactId>shieldlabs-java</artifactId>
  <version>1.0.0</version>
</dependency>
```

Gradle: `implementation("ai.shieldlabs:shieldlabs-java:1.0.0")`.

## Create the client

```java
ShieldLabsClient shieldlabs = ShieldLabsClient.fromEnvironment(); // SHIELDLABS_API_KEY, SHIELDLABS_API_BASE_URL

// or explicitly
ShieldLabsClient shieldlabs = ShieldLabsClient.builder()
        .apiKey(System.getenv("SHIELDLABS_API_KEY"))
        .timeout(Duration.ofSeconds(10)) // per HTTP attempt
        .maxRetries(2)
        .build();
```

Clients are immutable and safe for concurrent use: create one per domain and share it (a Spring
`@Bean`, a singleton).

## Spring Boot controller

```java
import ai.shieldlabs.*;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@Configuration
class ShieldLabsConfig {
    @Bean
    ShieldLabsClient shieldLabsClient() {
        return ShieldLabsClient.fromEnvironment();
    }
}

@RestController
class SignupController {
    private static final Logger log = LoggerFactory.getLogger(SignupController.class);
    private final ShieldLabsClient shieldlabs;
    private final JdbcTemplate jdbc;

    SignupController(ShieldLabsClient shieldlabs, JdbcTemplate jdbc) {
        this.shieldlabs = shieldlabs;
        this.jdbc = jdbc;
    }

    public static class SignupRequest {
        public String email;
        public String requestId;
    }

    @PostMapping("/api/signup")
    ResponseEntity<Map<String, Object>> signup(@RequestBody SignupRequest body) {
        Identification identification = null;
        if (body.requestId != null && !body.requestId.isBlank()) {
            try {
                // Waits up to 10 seconds for the verdict.
                identification = shieldlabs.identifications().get(body.requestId).orElse(null);
            } catch (ShieldLabsException e) {
                log.warn("ShieldLabs lookup failed: {}", e.getClass().getSimpleName()); // unverified
            }
        }

        Evaluation evaluation = Risk.evaluate(identification, EvaluateOptions.builder()
                .replayCheck(id -> !claimRequestId(id))
                .build());
        if (!evaluation.isOk()) {
            log.info("signup refused: {}", evaluation.getReason().map(Evaluation.Reason::getValue).orElse(""));
            return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "signup_refused"));
        }
        // Create the account here.
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("ok", true));
    }

    // CREATE TABLE used_request_ids (request_id CHAR(36) PRIMARY KEY, used_at TIMESTAMP NOT NULL)
    private boolean claimRequestId(String requestId) {
        try {
            jdbc.update("INSERT INTO used_request_ids (request_id, used_at) VALUES (?, CURRENT_TIMESTAMP)", requestId);
            return true;
        } catch (DuplicateKeyException e) {
            return false; // used before
        } catch (DataAccessException e) {
            return false; // store unreachable: refuse rather than allow
        }
    }
}
```

`identifications().get()` blocks the request thread while it polls. In reactive or high-traffic
code use `getAsync(requestId)`, which returns a `CompletableFuture<Optional<Identification>>` and
waits with scheduled delays instead of a blocked thread. A plain `com.sun.net.httpserver` server
works the same way: read `requestId` from the body, then the same `get` and `Risk.evaluate`.

## Options

```java
GetIdentificationOptions options = GetIdentificationOptions.builder()
        .waitFor(Duration.ofSeconds(5))       // total budget; default 10 s
        .pollInterval(Duration.ofMillis(250)) // first wait; then x2, x4, x6, x8, each at most max(2 s, interval)
        .build();
Optional<Identification> found = shieldlabs.identifications().get(requestId, options);
shieldlabs.identifications().get(requestId, GetIdentificationOptions.builder().noWait().build()); // one lookup, usual retries

EvaluateOptions policy = EvaluateOptions.builder()
        .maxAge(Duration.ofMinutes(5))
        .blockBands(RiskBand.DANGEROUS)
        .blockFlags(DetectionFlag.BROWSER_AUTOMATION, DetectionFlag.JAVASCRIPT_DISABLED)
        .replayCheck(id -> !claimRequestId(id))
        .build();
Evaluation evaluation = Risk.evaluate(found.orElse(null), policy);
// isOk(), getReason() -> Optional<Evaluation.Reason>, getBand() -> Optional<RiskBand>, getFlag() -> Optional<DetectionFlag>
```

The options are named `waitFor(Duration)` and `noWait()`: they do what `timeout` and `wait` do in the
other SDKs, so `waitFor(Duration.ZERO)` makes one poll without waiting, as `timeout: 0` does there,
and `noWait()` makes one lookup with the usual retries. The last poll runs at the deadline, and
each poll is one HTTP attempt: a 429, a 5xx, a connection error or a timeout keeps it polling, and
at the deadline the exception of a failed last poll is thrown instead of returning
`Optional.empty()`. A 400, 401, 403 or 404 throws at once, and so does a 429 whose `Retry-After`
(capped at 10 s) is longer than the time left; after any other 429 the next poll waits the longest
of the scheduled wait, 1 s and the capped `Retry-After` (0 when missing), cut short at the
deadline.

Helpers: `Risk.band(score)` (`TRUSTED`, `SUSPICIOUS`, `DANGEROUS`, `RATE_LIMITED`),
`Risk.isRateLimited(score)`, `Risk.NIL_DEVICE_ID`.

## The `Identification` model

Getters follow the webhook field names: `getRequestId()`, `getVisitorId()`, `getDeviceId()`,
`getSessionId()`, `getCookieId()`, `getUserHid()` (null when empty, `"anonymous"` for anonymous
checks), `getDomain()`, `getPublicIp()` and `getLocalIp()` (`getIp()`, `getCountry()`),
`getConnectionType()`, `getOs()`, `getBrowser()`, `getDeviceType()`, `getTrafficSource()`,
`getRiskScore()`, `getSignals()`, `getDetectionFlags()` (`isVpn()`, `isTor()`,
`isBrowserAutomation()`, `get(DetectionFlag)`, `active()`), `getObservedAt()` (`Instant`, null
when unknown), `getSource()`, `raw()`.

## Errors

`ShieldLabsException` is the base: `ValidationException` (nothing sent), `ApiException` with
`getStatusCode()`, `getBody()`, `getErrorMessage()`, `getHeaders()`, and its subclasses
`BadRequestException` (400), `AuthenticationException` (401, 403), `QuotaExceededException`
(402), `NotFoundException` (404), `RateLimitException` (429, `getRetryAfter()`),
`ServerException` (5xx); plus `ApiConnectionException` and `ApiTimeoutException`.

## Management API

```java
ManagementClient management = ManagementClient.fromEnvironment(); // SHIELDLABS_SECRET_KEY, SHIELDLABS_DOMAIN
DomainProfile profile = management.getProfile(); // cache it: about 15 calls per minute per IP
System.out.println(profile.getRemainingIdentifications()); // negative when the account is over its included volume
```
