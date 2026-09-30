# Risk decisions in Java

The `decide()` function of the skill on `ai.shieldlabs.Risk.evaluate()`.

```java
import ai.shieldlabs.*;
import java.util.EnumMap;
import java.util.Map;

public final class RiskPolicy {
    public enum Sensitivity { LOW, MEDIUM, HIGH }
    public enum Decision { ALLOW, STEP_UP, REVIEW, BLOCK } // from the mildest to the strictest

    public static final class Result {
        public final Decision decision;
        public final String reason;
        Result(Decision decision, String reason) { this.decision = decision; this.reason = reason; }
    }

    private static final Map<RiskBand, Map<Sensitivity, Decision>> BY_BAND = new EnumMap<>(RiskBand.class);
    private static final Map<Sensitivity, Decision> UNVERIFIED = new EnumMap<>(Sensitivity.class);
    private static final Map<Sensitivity, Decision> USER_MISMATCH = new EnumMap<>(Sensitivity.class);
    static {
        BY_BAND.put(RiskBand.TRUSTED, row(Decision.ALLOW, Decision.ALLOW, Decision.ALLOW));
        BY_BAND.put(RiskBand.SUSPICIOUS, row(Decision.ALLOW, Decision.STEP_UP, Decision.REVIEW));
        BY_BAND.put(RiskBand.DANGEROUS, row(Decision.STEP_UP, Decision.BLOCK, Decision.BLOCK));
        UNVERIFIED.putAll(row(Decision.ALLOW, Decision.STEP_UP, Decision.REVIEW));
        USER_MISMATCH.putAll(row(Decision.STEP_UP, Decision.STEP_UP, Decision.BLOCK));
    }

    private static Map<Sensitivity, Decision> row(Decision low, Decision medium, Decision high) {
        Map<Sensitivity, Decision> map = new EnumMap<>(Sensitivity.class);
        map.put(Sensitivity.LOW, low);
        map.put(Sensitivity.MEDIUM, medium);
        map.put(Sensitivity.HIGH, high);
        return map;
    }

    public static Result decide(Identification identification, Sensitivity sensitivity, boolean firstUse, String expectedUserHid) {
        Evaluation evaluation = Risk.evaluate(identification, EvaluateOptions.builder()
                .replayCheck(id -> !firstUse)
                .blockBands() // none: bands are mapped per sensitivity below
                .build());
        if (evaluation.getReason().isPresent()) {
            Evaluation.Reason reason = evaluation.getReason().get();
            switch (reason) {
                case REPLAYED:
                case STALE:
                case BLOCKED_FLAG:
                    return new Result(Decision.BLOCK, reason.getValue());
                case MISSING:
                case NO_DEVICE_SIGNALS:
                    return new Result(UNVERIFIED.get(sensitivity), reason.getValue());
                case RATE_LIMITED:
                    return new Result(sensitivity == Sensitivity.HIGH ? Decision.REVIEW : Decision.STEP_UP, reason.getValue());
                default:
                    break;
            }
        }
        RiskBand band = evaluation.getBand().orElse(RiskBand.DANGEROUS);
        // Map the band first: a User HID mismatch can only make the decision stricter, never softer.
        Decision decision = BY_BAND.get(band).get(sensitivity);
        if (expectedUserHid != null && !expectedUserHid.equals(identification.getUserHid())) {
            Decision mismatch = USER_MISMATCH.get(sensitivity);
            if (mismatch.compareTo(decision) > 0) return new Result(mismatch, "user_mismatch");
        }
        return new Result(decision, "band_" + band.getValue());
    }
}
```

## In a controller

```java
Identification identification = readIdentification(body.requestId); // null on any failure
boolean firstUse = identification != null && claimRequestId(identification.getRequestId());
String expectedHid = UserHid.fromUserId(String.valueOf(user.getId()), userHidSecret);
RiskPolicy.Result result = RiskPolicy.decide(identification, RiskPolicy.Sensitivity.HIGH, firstUse, expectedHid);
log.info("payout decision={} reason={}", result.decision, result.reason);
switch (result.decision) {
    case ALLOW: return createPayout(body);
    case STEP_UP: return ResponseEntity.accepted().body(Map.of("next", "verify_second_factor"));
    case REVIEW: return holdPayoutForReview(body, result.reason);
    default: return ResponseEntity.status(HttpStatus.FORBIDDEN).body(Map.of("error", "request_refused"));
}
```

## Extra flag rules

```java
DetectionFlags flags = identification.getDetectionFlags();
if (flags.isAntiDetectBrowser() || flags.isTor()) {
    // block on high-value actions, step-up on medium ones
}
```

Helpers: `Risk.band(score)`, `Risk.isRateLimited(score)`, `Risk.NIL_DEVICE_ID`,
`flags.get(DetectionFlag.TOR)`, `flags.active()`, and the `SignalName` constants (an open set).
Pass `.now(Instant)` to `EvaluateOptions.builder()` in tests.
