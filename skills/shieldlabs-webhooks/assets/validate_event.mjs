// Copy this file and webhook-event.schema.json into the application.
// Install and pin @cfworker/json-schema in that application's package manager.
import { Validator } from '@cfworker/json-schema';
import schema from './webhook-event.schema.json' with { type: 'json' };

const validator = new Validator(schema, '2020-12');

/** Validate only after SDK signature verification. Do not log payloads or schema errors. */
export function validateKnownEvent(envelope) {
  if (!envelope || typeof envelope !== 'object') return false;
  const kind = envelope.event_type;
  if (kind !== 'identification.scored' && kind !== 'hre.multi_account.changed') return true;
  if (typeof envelope.event_id !== 'string' || envelope.event_id.length === 0) return false;
  if (kind === 'hre.multi_account.changed' && envelope.schema_version !== '2026-10-07') return false;
  return validator.validate(envelope).valid;
}
