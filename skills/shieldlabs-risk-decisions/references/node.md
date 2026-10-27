# Risk decisions in Node.js

Put `decide()` from the skill ([The policy in code](../SKILL.md#the-policy-in-code)) in
`risk-policy.ts`. It builds on `evaluateIdentification` from `@shieldlabs-ai/node` (also exported by
`@shieldlabs-ai/next/server`); pass `now` in the context only in tests.

## In a handler

```ts
import { userHid } from '@shieldlabs-ai/node';
import { decide } from './risk-policy';

app.post('/api/payout', express.json(), async (req, res) => {
  const identification = await readIdentification(req.body.identificationId); // shieldlabs-server skill; null on any failure
  const firstUse = identification ? await claimRequestId(identification.identification_id) : false;
  const { decision, reason } = decide(identification, 'high', {
    firstUse,
    expectedUserHid: userHid(String(req.user.id), process.env.USER_HID_SECRET!),
  });
  logger.info({ identificationId: identification?.identification_id, decision, reason }, 'payout decision');

  switch (decision) {
    case 'allow':
      return res.json(await createPayout(req.user, req.body));
    case 'step_up':
      return res.status(202).json({ next: 'verify_second_factor' });
    case 'review':
      return res.status(202).json(await holdPayoutForReview(req.user, req.body, reason));
    case 'block':
      return res.status(403).json({ error: 'request_refused' });
  }
});
```

## Extra flag rules

Add rules for specific flags after the replay and freshness checks, for example stricter handling
of anti-detect browsers and Tor on high-value actions:

```ts
function stricterForHighValue(identification: Identification, sensitivity: Sensitivity): Decision | null {
  const flags = identification.detection_flags;
  if (sensitivity === 'high' && (flags.anti_detect_browser || flags.tor)) return 'block';
  if (sensitivity === 'medium' && (flags.anti_detect_browser || flags.tor)) return 'step_up';
  return null; // fall back to the band
}
```

Call it after `decide()` has passed the guards, and keep the stricter of the two decisions.

## Useful helpers

- `riskBand(score)`: `'trusted' | 'suspicious' | 'dangerous' | 'rate_limited'`.
- `isRateLimited(score)`: `true` for the `999` marker.
- `NIL_UUID`: the all-zero device ID.
- `SIGNALS`: known signal slugs, for example `SIGNALS.VPN === 'vpn'`. The set is open, so use it to
  label logs, not to branch.
- `RISK_BANDS`: `{ trusted: { min: 0, max: 29 }, suspicious: { min: 30, max: 59 }, dangerous: { min: 60, max: 100 } }`.
