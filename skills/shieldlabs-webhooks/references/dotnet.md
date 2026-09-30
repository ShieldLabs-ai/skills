# Webhooks in .NET

`WebhookEvents.ConstructEvent(payload, signatureHeader, params secrets)` takes the raw body as
`byte[]` (or `string`) and one or more secrets. It returns an `IdentificationScoredEvent` (`Data` is
an `Identification`), a `WebhookPingEvent` or an `UnknownWebhookEvent`, and throws
`SignatureVerificationException` (answer 401) or `WebhookParseException` (answer 400).
`WebhookSignature.Verify(...)` returns a `bool` and never throws; `WebhookSignature.HeaderName` is
`"X-Shield-Signature"`.

`processed.TryMark(requestId)` below stands for your atomic "first time" check, separate from the
store of request IDs that authorized actions.

## ASP.NET Core minimal API

```csharp
var webhookSecrets = (builder.Configuration["SHIELDLABS_WEBHOOK_SECRET"] ?? string.Empty)
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
if (webhookSecrets.Length == 0) app.Logger.LogError("SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500");

app.MapPost("/webhooks/shieldlabs", async (HttpRequest request, ProcessedDeliveries processed, IBackgroundQueue queue) =>
{
    if (webhookSecrets.Length == 0) return Results.StatusCode(500); // a configuration error, not a bad signature

    // Read the raw bytes; never bind the webhook to a model with [FromBody] before verifying.
    byte[] payload;
    using (var buffer = new MemoryStream())
    {
        await request.Body.CopyToAsync(buffer);
        payload = buffer.ToArray();
    }

    WebhookEvent evt;
    try
    {
        evt = WebhookEvents.ConstructEvent(payload, request.Headers[WebhookSignature.HeaderName], webhookSecrets);
    }
    catch (SignatureVerificationException)
    {
        return Results.Unauthorized();
    }
    catch (WebhookParseException)
    {
        return Results.BadRequest();
    }

    if (evt is IdentificationScoredEvent scored && processed.TryMark(scored.Data.RequestId))
    {
        queue.Enqueue(scored.Data); // answer within 1 second, work in the background
    }
    return Results.Ok(); // WebhookPingEvent and UnknownWebhookEvent: acknowledge
});
```

`ProcessedDeliveries` and `IBackgroundQueue` are your own services, for example a table with a
unique key on the request ID and a `Channel<Identification>` read by a hosted service.

## MVC controller

```csharp
[ApiController]
[Route("webhooks/shieldlabs")]
public sealed class ShieldLabsWebhookController(ProcessedDeliveries processed, IBackgroundQueue queue, IConfiguration config) : ControllerBase
{
    [HttpPost]
    public async Task<IActionResult> Receive()
    {
        using var buffer = new MemoryStream();
        await Request.Body.CopyToAsync(buffer);
        var secrets = (config["SHIELDLABS_WEBHOOK_SECRET"] ?? string.Empty)
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (secrets.Length == 0) return StatusCode(500); // a configuration error, not a bad signature
        try
        {
            var evt = WebhookEvents.ConstructEvent(buffer.ToArray(), Request.Headers[WebhookSignature.HeaderName], secrets);
            if (evt is IdentificationScoredEvent scored && processed.TryMark(scored.Data.RequestId))
            {
                queue.Enqueue(scored.Data);
            }
            return Ok();
        }
        catch (SignatureVerificationException)
        {
            return Unauthorized();
        }
        catch (WebhookParseException)
        {
            return BadRequest();
        }
    }
}
```

When antiforgery validation is enabled for the app, exclude this endpoint: the signature
authenticates the request.

## Event data

`scored.Data` is the same `Identification` the History API returns: `RequestId`, `DeviceId`,
`UserHid` (`string?`), `PublicIp.Country`, `RiskScore`, `Signals`, `DetectionFlags`, `ObservedAt`,
`Source` and `Raw`. `Risk.Band(scored.Data.RiskScore)` gives the band. The envelope has
`EventType`, `SchemaVersion`, `CreatedAt` and `Raw`.
