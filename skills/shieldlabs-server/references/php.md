# PHP with `shieldlabs/shieldlabs-php`

PHP 8.1 or later. Namespace `ShieldLabs\`. It uses any PSR-18 client your project has (Guzzle 7,
Symfony HttpClient) and falls back to a built-in cURL client.

## Install and create the client

```bash
composer require shieldlabs/shieldlabs-php
```

```php
use ShieldLabs\ShieldLabs;

$shieldlabs = new ShieldLabs(); // reads SHIELDLABS_API_KEY (and SHIELDLABS_API_BASE_URL when set)
```

Options (array): `api_key`, `base_url` (default `https://account.shieldlabs.ai`), `timeout`
(seconds per attempt, default `10`), `max_retries` (default `2`), `http_client` (any PSR-18 client,
used as is, so give it a timeout), `request_factory`. A client keeps no mutable state after
construction: share one instance (a container singleton), also in long-running workers.

## Plain PHP

```php
<?php

require __DIR__ . '/vendor/autoload.php';

use ShieldLabs\Exception\ShieldLabsException;
use ShieldLabs\Risk;
use ShieldLabs\ShieldLabs;

$pdo = new PDO(getenv('DATABASE_DSN') ?: 'sqlite:' . __DIR__ . '/app.db');
$shieldlabs = new ShieldLabs();

// CREATE TABLE used_request_ids (request_id CHAR(36) PRIMARY KEY, used_at TIMESTAMP NOT NULL)
function claimRequestId(PDO $pdo, string $requestId): bool
{
    try {
        $pdo->prepare('INSERT INTO used_request_ids (request_id, used_at) VALUES (?, CURRENT_TIMESTAMP)')
            ->execute([$requestId]);
        return true;
    } catch (PDOException $exception) {
        if (str_starts_with((string) $exception->getCode(), '23')) {
            return false; // integrity constraint violation: used before
        }
        throw $exception;
    }
}

$requestId = $_POST['requestId'] ?? '';
$identification = null;
if (is_string($requestId) && $requestId !== '') {
    try {
        // Polls until the identification is scored, for up to 10 seconds by default.
        $identification = $shieldlabs->identifications->get($requestId);
    } catch (ShieldLabsException $exception) {
        error_log('ShieldLabs lookup failed: ' . $exception::class); // unverified, never clean
    }
}

$evaluation = Risk::evaluate($identification, [
    'is_replay' => fn (string $id): bool => !claimRequestId($pdo, $id),
]);

if (!$evaluation->ok) {
    error_log('signup refused: ' . $evaluation->reason?->value);
    http_response_code(403);
    exit;
}
// Create the account here.
http_response_code(201);
```

PDO throws exceptions by default since PHP 8.0. With Redis,
`SET shieldlabs:used:<request ID> 1 NX EX 86400` does the same in one command.

## Laravel

```php
// config/services.php: add the shieldlabs entry next to the services the file already has
return [
    'shieldlabs' => [
        'api_key' => env('SHIELDLABS_API_KEY'),
        'webhook_secret' => env('SHIELDLABS_WEBHOOK_SECRET'),
        'user_hid_secret' => env('USER_HID_SECRET'),
    ],
];
```

```php
// app/Providers/AppServiceProvider.php
namespace App\Providers;

use Illuminate\Support\ServiceProvider;
use ShieldLabs\ShieldLabs;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        // One client for the whole process, shared by every request.
        $this->app->singleton(ShieldLabs::class, fn () => new ShieldLabs([
            'api_key' => config('services.shieldlabs.api_key'),
        ]));
    }
}
```

```php
// app/Http/Controllers/SignupController.php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use ShieldLabs\Exception\ShieldLabsException;
use ShieldLabs\Risk;
use ShieldLabs\ShieldLabs;

class SignupController extends Controller
{
    public function store(Request $request, ShieldLabs $shieldlabs)
    {
        $requestId = (string) $request->input('requestId', '');
        $identification = null;
        if ($requestId !== '') {
            try {
                $identification = $shieldlabs->identifications->get($requestId);
            } catch (ShieldLabsException $exception) {
                Log::warning('ShieldLabs lookup failed', ['error' => $exception::class]);
            }
        }

        $evaluation = Risk::evaluate($identification, [
            // insertOrIgnore returns 0 when the primary key already exists.
            'is_replay' => fn (string $id): bool => DB::table('used_request_ids')
                ->insertOrIgnore(['request_id' => $id, 'used_at' => now()]) === 0,
        ]);

        if (!$evaluation->ok) {
            Log::info('signup refused', ['reason' => $evaluation->reason?->value, 'band' => $evaluation->band?->value]);
            return response()->json(['error' => 'signup_refused'], 403);
        }
        // Create the account here.
        return response()->json(['ok' => true], 201);
    }
}
```

Symfony works the same way: register `ShieldLabs\ShieldLabs` as a service with the key from
`%env(SHIELDLABS_API_KEY)%` and inject it into the controller.

## `identifications->get()` options

```php
$shieldlabs->identifications->get($requestId);                            // wait up to 10 s in total
$shieldlabs->identifications->get($requestId, ['timeout' => 3]);          // a 3-second budget (seconds)
$shieldlabs->identifications->get($requestId, ['poll_interval' => 0.25]); // waits of p, 2p, 4p, 6p, then 8p, each at most max(2 s, p)
$shieldlabs->identifications->get($requestId, ['wait' => false]);         // one lookup with the usual retries
```

It returns a `ShieldLabs\Model\Identification` or `null`. The last poll runs when the budget ends.
Each poll is one HTTP request without retries; a 429, a 5xx, a connection error or a timeout keeps
it polling, and at the deadline the exception of a failed last poll is thrown. A 400, 401, 403 or
404 throws at once, and so does a 429 whose `Retry-After` (capped at 10 seconds) is longer than the
time left; after any other 429 the next poll waits the longest of the scheduled wait, 1 second and
the capped `Retry-After` (0 when missing), cut short at the deadline. A poll gets the time left in
the budget (at least 1 second, never more than the client `timeout`) with the built-in
`CurlClient` and the Guzzle or Symfony client the SDK creates; a PSR-18 client you pass as
`http_client` keeps its own timeout, so the call can end up to one request timeout after the budget.

## `Risk::evaluate()` options

```php
use ShieldLabs\RiskBand;

$evaluation = Risk::evaluate($identification, [
    'max_age' => 300,                                      // seconds, by observed_at
    'block_bands' => [RiskBand::Dangerous],
    'block_flags' => ['browser_automation', 'javascript_disabled'],
    'is_replay' => $isReplay,
]);
// $evaluation->ok, $evaluation->reason (EvaluationReason enum or null), $evaluation->band (RiskBand), $evaluation->flag
```

Helpers: `Risk::band($score)`, `Risk::isRateLimited($score)`, `$identification->riskBand()`,
`$identification->isRateLimited()`, `$identification->hasDeviceSignals()`,
`$identification->detection_flags->active()`.

## Errors

Every exception extends `ShieldLabs\Exception\ShieldLabsException`: `ValidationException`
(nothing sent), `BadRequestException` (400), `AuthenticationException` (401, 403),
`QuotaExceededException` (402), `NotFoundException` (404), `RateLimitException` (429,
`getRetryAfter()`), `ServerException` (5xx), `ApiException` (their parent, with
`getStatusCode()`, `getBody()`, `getErrorMessage()`), `ApiConnectionException`,
`ApiTimeoutException`. Warnings (for example a key in an unexpected format) go to `error_log()`.

## Management API

```php
use ShieldLabs\ShieldLabsManagement;

$management = new ShieldLabsManagement(); // reads SHIELDLABS_SECRET_KEY and SHIELDLABS_DOMAIN
$profile = $management->getProfile();     // cache it: about 15 calls per minute per IP
echo $profile->remaining_identifications; // negative when the account is over its included volume
```
