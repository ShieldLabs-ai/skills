# Risk decisions in PHP

The `decide()` function of the skill on `ShieldLabs\Risk::evaluate()`.

```php
<?php

use ShieldLabs\EvaluationReason;
use ShieldLabs\Model\Identification;
use ShieldLabs\Risk;

final class RiskPolicy
{
    private const BY_BAND = [
        'trusted' => ['low' => 'allow', 'medium' => 'allow', 'high' => 'allow'],
        'suspicious' => ['low' => 'allow', 'medium' => 'step_up', 'high' => 'review'],
        'dangerous' => ['low' => 'step_up', 'medium' => 'block', 'high' => 'block'],
    ];
    private const UNVERIFIED = ['low' => 'allow', 'medium' => 'step_up', 'high' => 'review'];
    private const USER_MISMATCH = ['low' => 'step_up', 'medium' => 'step_up', 'high' => 'block'];
    private const STRICTNESS = ['allow' => 0, 'step_up' => 1, 'review' => 2, 'block' => 3];

    /**
     * @param 'low'|'medium'|'high' $sensitivity
     * @return array{0: 'allow'|'step_up'|'review'|'block', 1: string}
     */
    public static function decide(?Identification $identification, string $sensitivity, bool $firstUse, ?string $expectedUserHid = null): array
    {
        $evaluation = Risk::evaluate($identification, [
            'is_replay' => fn (string $id): bool => !$firstUse,
            'block_bands' => [], // bands are mapped per sensitivity below
        ]);

        $reason = $evaluation->reason;
        if ($reason !== null) {
            return match ($reason) {
                EvaluationReason::Replayed, EvaluationReason::Stale, EvaluationReason::BlockedFlag,
                EvaluationReason::BlockedBand => ['block', $reason->value],
                EvaluationReason::Missing, EvaluationReason::NoDeviceSignals => [self::UNVERIFIED[$sensitivity], $reason->value],
                EvaluationReason::RateLimited => [$sensitivity === 'high' ? 'review' : 'step_up', $reason->value],
            };
        }

        $band = $evaluation->band?->value;
        if ($band === null || !isset(self::BY_BAND[$band])) {
            return [self::UNVERIFIED[$sensitivity], 'missing']; // not reached after the checks above
        }
        // Map the band first: a User HID mismatch can only make the decision stricter, never softer.
        $decision = self::BY_BAND[$band][$sensitivity];
        if ($expectedUserHid !== null && $identification?->user_hid !== $expectedUserHid) {
            $mismatch = self::USER_MISMATCH[$sensitivity];
            if (self::STRICTNESS[$mismatch] > self::STRICTNESS[$decision]) {
                return [$mismatch, 'user_mismatch'];
            }
        }
        return [$decision, 'band_' . $band];
    }
}
```

## In a controller

```php
use ShieldLabs\UserHid;

$identification = $this->readIdentification($request->input('requestId')); // null on any failure
$firstUse = $identification !== null && $this->claimRequestId($identification->request_id);
[$decision, $reason] = RiskPolicy::decide(
    $identification,
    'high',
    $firstUse,
    UserHid::fromUserId((string) $user->id, config('services.shieldlabs.user_hid_secret')),
);
Log::info('payout decision', ['decision' => $decision, 'reason' => $reason]);

return match ($decision) {
    'allow' => $this->createPayout($request),
    'step_up' => response()->json(['next' => 'verify_second_factor'], 202),
    'review' => $this->holdPayoutForReview($request, $reason),
    default => response()->json(['error' => 'request_refused'], 403),
};
```

## Extra flag rules

```php
$flags = $identification->detection_flags;
if ($flags->anti_detect_browser || $flags->tor) {
    // block on high-value actions, step-up on medium ones
}
```

Helpers: `Risk::band($score)` (`RiskBand::Trusted`, `Suspicious`, `Dangerous`, `RateLimited`),
`Risk::isRateLimited($score)`, `$identification->riskBand()`, `$identification->hasDeviceSignals()`,
`$identification->detection_flags->get('tor')`, `->active()`, and the `SignalName` constants (an
open set).
