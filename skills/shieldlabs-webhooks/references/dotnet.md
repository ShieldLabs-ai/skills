# Webhooks in .NET

Use the verified raw envelope for current deliveries. Its `event_id` is the delivery key;
`data.identification_id` correlates the visit. The older typed SDK model can omit these fields.
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



`WebhookEvents.ConstructEvent(payload, signatureHeader, params secrets)` takes the raw body as
`byte[]` (or `string`) and one or more secrets. It returns an `IdentificationScoredEvent` (`Data` is
an `Identification`), a `WebhookPingEvent` or an `UnknownWebhookEvent`, and throws
`SignatureVerificationException` (answer 401) or `WebhookParseException` (answer 400).
`WebhookSignature.Verify(...)` returns a `bool` and never throws; `WebhookSignature.HeaderName` is
`"X-Shield-Signature"`.


## ASP.NET Core minimal API

```csharp
var webhookSecrets = (builder.Configuration["SHIELDLABS_WEBHOOK_SECRET"] ?? string.Empty)
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
if (webhookSecrets.Length == 0) app.Logger.LogError("SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500");

app.MapPost("/webhooks/shieldlabs", async (HttpRequest request, IBackgroundQueue queue) =>
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

    if (evt.EventType is "identification.scored" or "hre.multi_account.changed")
    {
        await queue.EnqueueOnceAsync(evt.Raw.GetProperty("event_id").GetString()!, evt.Raw); // acknowledge promptly after durable acceptance, work in the background
    }
    return Results.Ok(); // WebhookPingEvent and UnknownWebhookEvent: acknowledge
});
```

`IBackgroundQueue` is your own durable enqueue-once service, for example a table with a
unique key on the event ID and a durable outbox of verified JSON envelopes read by a hosted service.

## MVC controller

```csharp
[ApiController]
[Route("webhooks/shieldlabs")]
public sealed class ShieldLabsWebhookController(IBackgroundQueue queue, IConfiguration config) : ControllerBase
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
            if (evt.EventType is "identification.scored" or "hre.multi_account.changed")
            {
                await queue.EnqueueOnceAsync(evt.Raw.GetProperty("event_id").GetString()!, evt.Raw);
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
