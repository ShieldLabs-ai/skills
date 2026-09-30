# Risk decisions in .NET

The `Decide()` function of the skill on `ShieldLabs.Risk.Evaluate()`.

```csharp
using ShieldLabs;

public enum Sensitivity { Low, Medium, High }
public enum Decision { Allow, StepUp, Review, Block } // from the mildest to the strictest

public static class RiskPolicy
{
    private static readonly Dictionary<RiskBand, Decision[]> ByBand = new()
    {
        // index: Low, Medium, High
        [RiskBand.Trusted] = new[] { Decision.Allow, Decision.Allow, Decision.Allow },
        [RiskBand.Suspicious] = new[] { Decision.Allow, Decision.StepUp, Decision.Review },
        [RiskBand.Dangerous] = new[] { Decision.StepUp, Decision.Block, Decision.Block },
    };
    private static readonly Decision[] Unverified = { Decision.Allow, Decision.StepUp, Decision.Review };
    private static readonly Decision[] UserMismatch = { Decision.StepUp, Decision.StepUp, Decision.Block };

    public static (Decision Decision, string Reason) Decide(
        Identification? identification, Sensitivity sensitivity, bool firstUse, string? expectedUserHid = null)
    {
        var evaluation = Risk.Evaluate(identification, new EvaluateOptions
        {
            IsReplay = _ => !firstUse,
            BlockBands = Array.Empty<RiskBand>(), // bands are mapped per sensitivity below
        });

        switch (evaluation.Reason)
        {
            case EvaluationReason.Replayed or EvaluationReason.Stale or EvaluationReason.BlockedFlag:
                return (Decision.Block, evaluation.Reason.Value.ToString());
            case EvaluationReason.Missing or EvaluationReason.NoDeviceSignals:
                return (Unverified[(int)sensitivity], evaluation.Reason.Value.ToString());
            case EvaluationReason.RateLimited:
                return (sensitivity == Sensitivity.High ? Decision.Review : Decision.StepUp, "RateLimited");
        }

        var band = evaluation.Band ?? RiskBand.Dangerous;
        // Map the band first: a User HID mismatch can only make the decision stricter, never softer.
        var decision = ByBand[band][(int)sensitivity];
        var mismatch = UserMismatch[(int)sensitivity];
        if (expectedUserHid is not null && identification!.UserHid != expectedUserHid && mismatch > decision)
        {
            return (mismatch, "UserMismatch");
        }
        return (decision, "Band" + band);
    }
}
```

## In an endpoint

```csharp
app.MapPost("/api/payout", async (PayoutRequest body, ShieldLabsClient shieldlabs, UsedRequestIds used, ClaimsPrincipal user) =>
{
    Identification? identification = await ReadIdentificationAsync(shieldlabs, body.RequestId); // null on any failure
    var firstUse = identification is not null && await used.ClaimAsync(identification.RequestId);
    var expectedHid = UserHid.FromUserId(user.FindFirstValue(ClaimTypes.NameIdentifier)!, userHidSecret);
    var (decision, reason) = RiskPolicy.Decide(identification, Sensitivity.High, firstUse, expectedHid);

    return decision switch
    {
        Decision.Allow => await CreatePayoutAsync(body),
        Decision.StepUp => Results.Accepted(value: new { next = "verify_second_factor" }),
        Decision.Review => await HoldPayoutForReviewAsync(body, reason),
        _ => Results.Json(new { error = "request_refused" }, statusCode: StatusCodes.Status403Forbidden),
    };
});
```

## Extra flag rules

```csharp
var flags = identification.DetectionFlags;
if (flags.AntiDetectBrowser || flags.Tor)
{
    // block on high-value actions, step-up on medium ones
}
```

Helpers: `Risk.Band(score)`, `Risk.IsRateLimited(score)`, `DetectionFlagNames` (wire names for
`BlockFlags`), `SignalNames` (known signal names, an open set). Set `Now` on `EvaluateOptions` in
tests.
