# Webhooks in PHP

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



`ShieldLabs\Webhook::constructEvent(string $payload, ?string $header, string|array $secret)`
returns `Event\IdentificationScoredEvent` (`$event->data` is a `Model\Identification`),
`Event\WebhookPingEvent` or `Event\UnknownWebhookEvent`. It throws
`Exception\SignatureVerificationException` (answer 401) or `Exception\WebhookParseException`
(answer 400). `Webhook::verifySignature(...)` returns a `bool`.


## Plain PHP

```php
<?php

require __DIR__ . '/vendor/autoload.php';

use ShieldLabs\Event\IdentificationScoredEvent;
use ShieldLabs\Exception\SignatureVerificationException;
use ShieldLabs\Exception\WebhookParseException;
use ShieldLabs\Webhook;

$payload = (string) file_get_contents('php://input'); // the raw body, byte for byte
$signature = $_SERVER['HTTP_X_SHIELD_SIGNATURE'] ?? null;
$secrets = array_values(array_filter(array_map('trim', explode(',', (string) getenv('SHIELDLABS_WEBHOOK_SECRET')))));
if ($secrets === []) { // a configuration error, not a bad signature
    error_log('SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500');
    http_response_code(500);
    exit;
}

try {
    $event = Webhook::constructEvent($payload, $signature, $secrets);
} catch (SignatureVerificationException) {
    http_response_code(401);
    exit;
} catch (WebhookParseException) {
    http_response_code(400);
    exit;
}

if (in_array($event->raw['event_type'] ?? '', ['identification.scored', 'hre.multi_account.changed'], true)) {
    enqueueOnce($event->raw['event_id'], $event->raw); // atomic durable acceptance
}
http_response_code(200);
```

## Laravel

```php
// routes/web.php (or routes/api.php, which has no CSRF middleware)
use App\Http\Controllers\ShieldLabsWebhookController;
use Illuminate\Support\Facades\Route;

Route::post('/webhooks/shieldlabs', ShieldLabsWebhookController::class);
```

In Laravel 11 and later, exempt the route from CSRF checks in `bootstrap/app.php`: add the
`withMiddleware()` call and keep the other calls the file already makes.

```php
// bootstrap/app.php
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Middleware;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(web: __DIR__ . '/../routes/web.php')
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->validateCsrfTokens(except: ['webhooks/shieldlabs']);
    })
    ->create();
```

```php
// app/Http/Controllers/ShieldLabsWebhookController.php
namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use ShieldLabs\Event\IdentificationScoredEvent;
use ShieldLabs\Exception\SignatureVerificationException;
use ShieldLabs\Exception\WebhookParseException;
use ShieldLabs\Webhook;

class ShieldLabsWebhookController extends Controller
{
    public function __invoke(Request $request)
    {
        $secrets = array_values(array_filter(array_map('trim', explode(',', (string) config('services.shieldlabs.webhook_secret')))));
        if ($secrets === []) {
            Log::error('SHIELDLABS_WEBHOOK_SECRET is not set: webhook deliveries get 500');
            return response()->noContent(500);
        }
        try {
            // getContent() is the raw body; never verify $request->all() or re-encoded JSON.
            $event = Webhook::constructEvent($request->getContent(), $request->header('X-Shield-Signature'), $secrets);
        } catch (SignatureVerificationException) {
            return response()->noContent(401);
        } catch (WebhookParseException) {
            return response()->noContent(400);
        }

        if (in_array($event->raw['event_type'] ?? '', ['identification.scored', 'hre.multi_account.changed'], true)) {
            app(DurableWebhookQueue::class)->enqueueOnce($event->raw['event_id'], $event->raw);
        }
        return response()->noContent(200);
    }
}
```

In Laravel 10 and earlier, add the path to `$except` in `app/Http/Middleware/VerifyCsrfToken.php`.

## Symfony

```php
// src/Controller/ShieldLabsWebhookController.php
namespace App\Controller;

use ShieldLabs\Event\IdentificationScoredEvent;
use ShieldLabs\Exception\SignatureVerificationException;
use ShieldLabs\Exception\WebhookParseException;
use ShieldLabs\Webhook;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Attribute\Route;

final class ShieldLabsWebhookController
{
    /** @var list<string> */
    private readonly array $webhookSecrets;

    public function __construct(
        string $webhookSecret, // several secrets, comma-separated, while you rotate one
        private readonly DurableWebhookQueue $queue,
    ) {
        $this->webhookSecrets = array_values(array_filter(array_map('trim', explode(',', $webhookSecret))));
    }

    #[Route('/webhooks/shieldlabs', methods: ['POST'])]
    public function receive(Request $request): Response
    {
        if ($this->webhookSecrets === []) { // a configuration error, not a bad signature
            return new Response(status: 500);
        }
        try {
            $event = Webhook::constructEvent($request->getContent(), $request->headers->get('X-Shield-Signature'), $this->webhookSecrets);
        } catch (SignatureVerificationException) {
            return new Response(status: 401);
        } catch (WebhookParseException) {
            return new Response(status: 400);
        }
        if (in_array($event->raw['event_type'] ?? '', ['identification.scored', 'hre.multi_account.changed'], true)) {
            $this->queue->enqueueOnce($event->raw['event_id'], $event->raw);
        }
        return new Response(status: 200);
    }
}
```

`DurableWebhookQueue` and the plain-PHP `enqueueOnce` function are application-provided,
using a transaction/outbox; they are not Laravel/Symfony/ShieldLabs built-ins. Bind `$webhookSecret` to
`'%env(SHIELDLABS_WEBHOOK_SECRET)%'` in `config/services.yaml`.

## Event data

`$event->data` has `request_id`, `device_id`, `user_hid` (`?string`), `public_ip->country`,
`risk_score`, `signals`, `detection_flags` (`get()`, `active()`), `observed_at`
(`?DateTimeImmutable`), `source` (`"webhook"`) and `raw`; `riskBand()`, `isRateLimited()`,
`hasDeviceSignals()` and `toArray()` are methods.
