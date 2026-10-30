# User HID in PHP

`ShieldLabs\UserHid::fromUserId(string $userId, string $secret): string` returns HMAC-SHA256 as
64 lowercase hex characters and throws `ValidationException` on empty input.

```php
use ShieldLabs\UserHid;

$userHid = UserHid::fromUserId((string) $user->id, (string) getenv('USER_HID_SECRET'));
```

## Laravel

Keep the secret in `config/services.php` (`'shieldlabs' => ['user_hid_secret' => env('USER_HID_SECRET')]`)
and share the User HID with every view of a signed-in user:

```php
// app/Providers/AppServiceProvider.php, in boot()
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\View;
use ShieldLabs\UserHid;

View::composer('*', function ($view) {
    $user = Auth::user();
    $view->with('shieldlabsUserHid', $user
        ? UserHid::fromUserId((string) $user->getAuthIdentifier(), config('services.shieldlabs.user_hid_secret'))
        : null);
});
```

```blade
<form id="checkout" data-user-hid="{{ $shieldlabsUserHid }}">...</form>
```

Blade escapes the value and renders `null` as an empty attribute. The page script passes `form.dataset.userHid || undefined` to `identify({ userId })`: for a visitor who is not signed in the attribute is empty, and an empty `userId` is rejected with `invalid_options`, while `undefined` runs an anonymous identification.

## Plain PHP and Symfony

Compute the value in the controller and render it the same way (`htmlspecialchars()` in plain PHP,
`{{ shieldlabs_user_hid }}` in Twig).

## Check it on the server

```php
$expected = UserHid::fromUserId((string) $user->id, $secret);
if ($identification !== null && $identification->user_hid !== $expected) {
    // treat as unverified: another account's identification, or an anonymous one
}
```

## Read the account's History card

Read the `user` card with the exact generated HID, in the selected public domain UUID.
Preserve risk, signals, High-Risk Events and nullable related counts. Fetch additional cards
only when their IDs are known. Use the application database for its account/device associations.
See [current History](../../shieldlabs-server/references/current-history.md) and the
[account-abuse workflow](../../shieldlabs-account-abuse/references/high-risk-events.md).
