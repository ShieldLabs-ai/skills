# Verify the integration

Run these checks after the setup, and after any change to the integration. Report which ones
passed and which could not be run (for example because no registered domain is available yet).

## 1. Build and keys

- [ ] The app builds, and its type checks and tests pass.
- [ ] No server credential in the frontend build output:

  ```bash
  grep -rEl "sec_[a-z0-9]{8}-[a-z0-9]{8}-[a-z0-9]{8}|whsec_[0-9a-f]{32}" dist build .next/static .output/public public static 2>/dev/null
  ```

  Without a build step, search the folder the server serves to browsers.

- [ ] `.env` files with real keys are ignored by git (`git check-ignore .env`), and `.env.example`
  lists every variable with a placeholder.

## 2. Run it on a registered domain

- [ ] The app runs on a domain registered in the analytics dashboard (Integration > Domains), over
  HTTPS, with that domain's keys. Identifications from `localhost` are not recorded, although the
  page receives a request ID.

## 3. Trigger the protected action in a browser

- [ ] The network panel shows `snippet.js` from `https://cdn.shieldlabs.ai` and successful posts to
  `https://rest.shieldlabs.ai`; the console shows no Content Security Policy errors.
- [ ] The request of the protected action (for example `POST /api/signup`) carries a `requestId`.
- [ ] Nothing identifies on page load or on route changes, unless you chose `checkOnLoad` or
  `runOnMount` for a specific page. The History API can still show one more identification for the
  same device and session, observed just before the action, with a request ID the page never
  received: the agent's own check on the first click or key press of a visit.

## 4. See the server read the verdict

- [ ] The server log shows the identification that was read and the decision, for example
  `signup decision=allow reason=band_trusted risk_score=15 request_id=<id>`. Log the Risk Score
  too: the History row can be refined for up to about 10 seconds, so a later read may differ from
  what the decision saw.

## 5. Check the History API by request ID

Any of these, with the request ID from the log:

- The MCP tool `shieldlabs_get_identification` with `{"request_id": "<id>"}` (shieldlabs-investigate
  skill).
- Node.js:

  ```bash
  node --input-type=module -e "import { ShieldLabs } from '@shieldlabs-ai/node'; const s = new ShieldLabs({ apiKey: process.env.SHIELDLABS_API_KEY }); console.log(await s.identifications.get(process.argv[1]))" "$REQUEST_ID"
  ```

- Python:

  ```bash
  python3 -c "import sys; from shieldlabs import ShieldLabs; print(ShieldLabs().identifications.get(sys.argv[1]))" "$REQUEST_ID"
  ```

- HTTP:

  ```bash
  curl -s "https://account.shieldlabs.ai/api/v1/history/request_id/$REQUEST_ID?limit=1" \
    -H "Authorization: Bearer $SHIELDLABS_API_KEY"
  ```

  A row in `data` means the identification was recorded. History rows use their own field names:
  `score` is the Risk Score and `created_at` the time (the shieldlabs-server skill,
  `references/testing.md`, maps every field).

## 6. Negative paths

- [ ] Sending the same `requestId` again is refused (`replayed`).
- [ ] Sending the action without a `requestId` follows the unverified path (step-up, review or a
  refusal, as the policy says), never "allow as clean".
- [ ] A unit test with the policy helper's `now` option set 10 minutes after `observed_at` gives
  `stale`.
- [ ] For signed-in actions, an identification with another User HID is not trusted.

## 7. Webhooks (when used)

- [ ] **Verify** on the endpoint (analytics dashboard, Integration > Webhooks) gets a 2xx and the
  endpoint shows as delivering.
- [ ] **Test** gets a 2xx within one second; pressing it twice processes the sample once (it
  always has the same `request_id`).
- [ ] A request with a wrong `X-Shield-Signature` gets 401.

## 8. The analytics dashboard

- [ ] The identification appears in the analytics dashboard (https://app.shieldlabs.ai) with its
  Risk Score, risk signals and, for signed-in users, the User HID.
