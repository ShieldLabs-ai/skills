# .NET with the `ShieldLabs` package

.NET 8 or later (`net8.0` build) and runtimes that implement .NET Standard 2.0. Namespace
`ShieldLabs`.

## Install and register the client

```sh
dotnet add package ShieldLabs
```

```csharp
using ShieldLabs;

// Program.cs: one client per domain, shared by every request (safe for concurrent use).
builder.Services.AddSingleton(_ => new ShieldLabsClient(new ShieldLabsClientOptions
{
    ApiKey = builder.Configuration["SHIELDLABS_API_KEY"], // Private API Key, sec_...
    BaseUrl = builder.Configuration["SHIELDLABS_API_BASE_URL"], // optional, tests only
}));
```

Options: `ApiKey` (required), `BaseUrl` (default `https://account.shieldlabs.ai`), `Timeout` (per
attempt, default 10 s), `MaxRetries` (default 2). Pass an `HttpClient` as the second constructor
argument to use `IHttpClientFactory`; the SDK never disposes it.

## Minimal API endpoint

```csharp
app.MapPost("/api/signup", async (SignupRequest body, ShieldLabsClient shieldlabs, UsedRequestIds used,
    ILogger<Program> logger, CancellationToken cancellationToken) =>
{
    Identification? identification = null;
    if (!string.IsNullOrWhiteSpace(body.RequestId))
    {
        try
        {
            // Waits at most 10 seconds for the verdict.
            identification = await shieldlabs.Identifications.GetAsync(body.RequestId, cancellationToken: cancellationToken);
        }
        catch (ShieldLabsException error)
        {
            logger.LogWarning(error, "ShieldLabs lookup failed"); // unverified, never clean
        }
    }

    // IsReplay is synchronous: claim first, then pass the result.
    var firstUse = identification is not null && await used.ClaimAsync(identification.RequestId);
    var evaluation = Risk.Evaluate(identification, new EvaluateOptions { IsReplay = _ => !firstUse });
    if (!evaluation.Ok)
    {
        logger.LogInformation("Signup refused: {Reason} (band {Band}, flag {Flag})", evaluation.Reason, evaluation.Band, evaluation.Flag);
        return Results.Json(new { error = "signup_refused" }, statusCode: StatusCodes.Status403Forbidden);
    }
    // Create the account here.
    return Results.Created("/account", new { ok = true });
});

internal sealed record SignupRequest(string? RequestId, string? Email);
```

`UsedRequestIds.ClaimAsync` returns `true` the first time a request ID is claimed. Back it with a
unique key, for example with StackExchange.Redis:

```csharp
internal sealed class UsedRequestIds(IConnectionMultiplexer redis)
{
    public async Task<bool> ClaimAsync(string requestId)
    {
        try
        {
            return await redis.GetDatabase().StringSetAsync(
                "shieldlabs:used:" + requestId, "1", TimeSpan.FromDays(1), When.NotExists);
        }
        catch (RedisException)
        {
            return false; // store unreachable: refuse rather than allow
        }
    }
}
```

With EF Core, insert a row with the request ID as the primary key and treat a
`DbUpdateException` for the duplicate key as "used before".

## Options

```csharp
var identification = await shieldlabs.Identifications.GetAsync(
    requestId,
    new GetIdentificationOptions { Timeout = TimeSpan.FromSeconds(5) }, // total budget; Wait (true), PollInterval (250 ms)
    cancellationToken);
var once = await shieldlabs.Identifications.GetAsync(requestId, new GetIdentificationOptions { Wait = false }); // one lookup, usual retries

var evaluation = Risk.Evaluate(identification, new EvaluateOptions
{
    MaxAge = TimeSpan.FromMinutes(5),
    BlockBands = new[] { RiskBand.Dangerous },
    BlockFlags = new[] { DetectionFlagNames.BrowserAutomation, DetectionFlagNames.JavascriptDisabled },
    IsReplay = _ => !firstUse,
});
// evaluation.Ok, evaluation.Reason (EvaluationReason?), evaluation.Band (RiskBand?), evaluation.Flag (string?)
```

The waits between lookups are 1, 2, 4, 6 and then 8 times `PollInterval`, each at most 2 s or
`PollInterval`, whichever is longer, and the last lookup runs at the deadline. Each lookup is one
HTTP attempt: a 429, a 5xx, a timeout or a connection error keeps it polling, and at the deadline
the exception of a failed last lookup is thrown instead of returning `null`. A 400, 401, 403 or
404 throws at once, and so does a 429 whose `Retry-After` (capped at 10 s) is longer than the time
left; after any other 429 the next lookup waits the longest of the scheduled wait, 1 s and the
capped `Retry-After` (0 when missing), cut short at the deadline.

Helpers: `Risk.Band(score)` (`Trusted`, `Suspicious`, `Dangerous`, `RateLimited`),
`Risk.IsRateLimited(score)`. The all-zero device ID is `"00000000-0000-0000-0000-000000000000"`.

## The `Identification` model

Properties (JSON names follow the webhook contract): `RequestId`, `VisitorId`, `DeviceId`,
`SessionId`, `CookieId`, `UserHid` (`string?`; `"anonymous"` for anonymous checks), `Domain`,
`PublicIp` and `LocalIp` (`Ip`, `Country`), `ConnectionType`, `Os`, `Browser`, `DeviceType`,
`TrafficSource`, `RiskScore`, `Signals`, `DetectionFlags` (19 booleans such as `Vpn`, `Proxy`,
`Tor`, `AntiDetectBrowser`, `BrowserAutomation`), `ObservedAt` (UTC), `Source`, `Raw`.

## Errors

`ShieldLabsException` is the base: `ValidationException` (nothing sent), `ApiException` with
`StatusCode`, `Body`, `Error`, `Headers`, and its subclasses `BadRequestException` (400),
`AuthenticationException` (401, 403), `QuotaExceededException` (402), `NotFoundException` (404),
`RateLimitException` (429, `RetryAfter`), `ServerException` (5xx); plus `ApiConnectionException`
and `ApiTimeoutException`. Cancelling the token throws `OperationCanceledException`.

## Management API

```csharp
var management = new ManagementClient(new ManagementClientOptions
{
    SecretKey = builder.Configuration["SHIELDLABS_SECRET_KEY"],
    Domain = builder.Configuration["SHIELDLABS_DOMAIN"],
});
DomainProfile profile = await management.GetProfileAsync(); // cache it: about 15 calls per minute per IP
// profile.RemainingIdentifications is negative when the account is over its included volume
```
