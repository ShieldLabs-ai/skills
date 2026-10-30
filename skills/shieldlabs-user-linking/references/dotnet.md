# User HID in .NET

`ShieldLabs.UserHid.FromUserId(string userId, string secret)` returns HMAC-SHA256 as 64 lowercase
hex characters and throws `ValidationException` on empty input.

```csharp
string userHidSecret = builder.Configuration["USER_HID_SECRET"]
    ?? throw new InvalidOperationException("USER_HID_SECRET is not set");
string userHid = UserHid.FromUserId(user.Id.ToString(), userHidSecret);
```

## Razor Pages and MVC views

Register a small service and inject it into the view:

```csharp
public sealed class UserHidService(IConfiguration config)
{
    private readonly string _secret = config["USER_HID_SECRET"]
        ?? throw new InvalidOperationException("USER_HID_SECRET is not set");

    public string? For(ClaimsPrincipal user) =>
        user.FindFirstValue(ClaimTypes.NameIdentifier) is { Length: > 0 } id ? UserHid.FromUserId(id, _secret) : null;
}

// Program.cs
builder.Services.AddSingleton<UserHidService>();
```

```cshtml
@inject UserHidService UserHids
<form id="checkout" data-user-hid="@UserHids.For(User)">...</form>
```

Razor encodes the value and leaves the attribute out when it is `null`. The page script passes `form.dataset.userHid || undefined` to `identify({ userId })`: for a visitor who is not signed in the attribute is empty, and an empty `userId` is rejected with `invalid_options`, while `undefined` runs an anonymous identification.

## Minimal API session endpoint for single-page apps

```csharp
app.MapGet("/api/session", (ClaimsPrincipal user, UserHidService userHids) =>
    user.Identity?.IsAuthenticated == true
        ? Results.Ok(new { user = new { name = user.Identity.Name, userHid = userHids.For(user) } })
        : Results.Ok(new { user = (object?)null }));
```

## Check it on the server

```csharp
var expected = userHids.For(httpContext.User);
if (identification is not null && identification.UserHid != expected)
{
    // treat as unverified: another account's identification, or an anonymous one
}
```

## Read the account's History card

Read the `user` card with the exact generated HID, in the selected public domain UUID.
Preserve risk, signals, High-Risk Events and nullable related counts. Fetch additional cards
only when their IDs are known. Use the application database for its account/device associations.
See [current History](../../shieldlabs-server/references/current-history.md) and the
[account-abuse workflow](../../shieldlabs-account-abuse/references/high-risk-events.md).
