# PHP server integration

Use the existing PHP backend and its HTTP client for the current public domain-scoped History
API. Install the official ShieldLabs SDK for its User HID, signature and webhook helpers:
`composer require shieldlabs/shieldlabs-php`. Keep the Private API Key and `SHIELDLABS_DOMAIN_ID` in the server environment.
Resolve that public domain UUID through MCP list_domains or `GET /api/v1/domains`.

## Read a current card

```php
<?php
// Reuse the application's HTTP client in a framework. This standalone example uses cURL.
function readCard(string $resource, string $id): array {
    // Validate domain UUID, resource and ID against current-history.md before calling.
    $domainId = getenv('SHIELDLABS_DOMAIN_ID');
    $url = 'https://account.shieldlabs.ai/api/v1/domains/' . $domainId
        . '/history/' . $resource . '/' . rawurlencode($id);
    $handle = curl_init($url);
    curl_setopt_array($handle, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 5,
        CURLOPT_HTTPHEADER => ['Accept: application/json', 'Authorization: Bearer ' . getenv('SHIELDLABS_API_KEY')],
    ]);
    $body = curl_exec($handle);
    $status = curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
    curl_close($handle);
    if ($body === false || $status !== 200) throw new RuntimeException('History read failed: ' . $status);
    $card = json_decode($body, true, 512, JSON_THROW_ON_ERROR)['data'];
    $expectedType = $resource === 'identifications' ? 'identification' : $resource;
    if ($card['domain_id'] !== $domainId || $card['id'] !== $id || ($card['type'] ?? null) !== $expectedType) throw new RuntimeException('History identity mismatch');
    return $card;
}
```

The sample performs one HTTP read. For a new identification, wrap reads in the bounded wait below.
Use `identifications` for the browser UUID; `user` for the exact server-generated HID; `visitor`,
`device` or `ip` for other cards. Check resource type, ID and domain before trusting a result.
See [current History](current-history.md) for the wire schema, filters and relations.

## Wait and handle errors

Use one total ten-second budget and one HTTP attempt per poll. Start immediately, then wait
250 ms, 500 ms, 1 s, 1.5 s and every 2 s, cutting the final wait to the remaining budget.
A missing/not-yet-available card can be read again for that same UUID. Preserve persistent errors.
After HTTP 429 wait the longest of the scheduled wait, 1 s and Retry-After capped at 10 s;
when that capped delay exceeds the time left, stop with the error. Connection errors, timeouts
and 5xx may retry within this budget. Stop on 400, 401, 402 or 403. A structured missing card is
unverified; a wrong route or malformed response is a configuration error.

Outside the wait, follow Retry-After as sent, capped at 10 s (0 retries at once); a 429 without
it waits at least 1 s. Keep retries bounded. HTTP 429 `rate_limited` is separate from the public
Banned IP `banned_ip` signal. Do not infer a billing cause from a missing result or status alone.

## Apply action policy

Treat a missing card, unavailable risk or unavailable signals as unverified. On an identification,
require numeric risk.score in 0–100 and an available band; read signal codes from signals.items.
Do not turn missing data into 0, an empty known flag set or a verified human.

Before performing the action: enforce a five-minute freshness limit using created_at, atomically
claim the identification UUID once, compare user_hid to the authenticated account's server HID
when signed in, then apply the application's policy for bands and signal codes. Refuse/review/
step-up on failures. Use a unique database key or Redis SET NX for replay protection; an unavailable
store cannot authorize the action. Do not pass this entity card directly to an SDK policy helper
that expects a normalized webhook Identification model.

History reads do not consume browser identifications. For signed webhooks, use the
[PHP receiver](../../shieldlabs-webhooks/references/php.md); for account hashing, use
[User HID in PHP](../../shieldlabs-user-linking/references/php.md).
