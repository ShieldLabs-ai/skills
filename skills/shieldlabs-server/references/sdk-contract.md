# Check the SDK contract before integrating

The published JS/Node packages checked on 2026-10-28 are 1.0.1; framework bindings are 1.0.0.
They are not the same contract as the newer SDK GitHub main branches. The hosted OAuth MCP has
its own adapter and 21-tool contract; its working reads do not prove an application SDK is compatible.

## Required preflight

1. Check the installed package version and types, then use an actual current API row or a current
   public-contract fixture in an offline test. Never use a mock with only the old field names as
   evidence of current compatibility.
2. The identification UUID must survive normalization and equal the browser's UUID. Current
   public History and webhooks use `identification_id`; published Node 1.0.1 reads `request_id`
   and can leave it empty. If the normalized ID is missing or different, treat the result as
   unverified and stop application integration until a compatible SDK or validated adapter exists.
   Do not rotate keys, alter billing or blindly rename properties as a workaround.
3. Test flags and the schema version too. The old normalized model has 19 flags; current SDK main
   has a different 20-flag model. Missing support must not be represented as confirmed false.
4. Verify signatures over original bytes, then preserve the verified raw webhook envelope. Old
   typed models can omit current fields while `raw` retains them. Dedupe current deliveries by
   envelope `event_id`, not by the old normalized `data.request_id`. Use the raw
   `data.identification_id` to correlate the identification; it is a different identifier.
5. Keep deduplication and durable enqueue atomic (transaction/outbox or an enqueue-once service).
   A failed enqueue must remain retryable. Acknowledge only after durable acceptance.

The webhook recipes preserve raw envelopes for this reason. A job that needs a typed current
identification must still validate its processor's schema. The SDK signature helper is useful even
when its typed identification model is older than the payload. Never trust or parse a raw body
before signature verification.

## Test and delivery behavior

Current Portal Verify/Test probes have a five-second budget; the application receiver should
still acknowledge quickly, preferably within one second. Core contains multiple delivery profiles,
including a three-second, three-attempt profile. Do not infer which profile is deployed from source
alone, promise exactly-once delivery, or describe retries as only a future feature.

Each Test click has a fresh `event_id` although its synthetic `data.identification_id` stays fixed.
Two Test clicks are two distinct events; a repeated delivery of the same event must have one
business effect. A test delivery is not a real visitor identification.

Current webhook contracts also contain HRE fields/events. The bounded History recipes in the
account-abuse skill are application heuristics, not substitutes for those backend event verdicts.
Check the installed SDK and current public contract before reading HRE fields.

## Validation scope

A passing Markdown validator, a successful MCP sign-in or a package install does not demonstrate
an app integration. Report separately source review, offline execution, framework compilation and
live end-to-end tests. Do not claim unrun languages/frameworks were executed.
