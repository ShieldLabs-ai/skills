# Client identity, crawlers and AI traffic

Use optional `client_identity` and owner attribution alongside the current flags `search_bot`,
`ai_bot`, `ai_browser` and `browser_automation`. Keep them separate from Risk Score and HRE.
Read the verified raw public result when the installed SDK does not expose these fields.
MCP may return a bounded projection; warnings/truncation mean it is unsuitable as complete
authorization proof. Never treat a missing flag or missing identity as a verified human.

- `claims` contains unverified reported names, kind and purpose. A claimed provider or agent
  can be spoofed. Do not grant access from the User-Agent or a claim alone.
- `verified` proves only its `subject` and `value_id`; `evidence_ids` reference the evidence
  used. Provider proof does not prove a service, agent, browser mode or a human operator.
- `assessments` and `evidence` explain candidate checks. Preserve their status/reason, checked
  times, covered attributes/components and binding/replay limits. Failed or incomplete proof
  does not become a positive verification.
- `search_bot_owner`, `ai_bot_owner`, `ai_browser_owner` are optional reported labels; they
  are not independent authorization proof.
- The object, every nested field and even array entries can be null/omitted. Accept unknown
  fields and string values. `input_unavailable`, null and absent remain unknown, not human.

Choose route policy using the application's requirements. A public documentation route may
permit an independently verified search crawler for indexing. An authenticated export, checkout,
signup or reward route still requires its own access controls and server verification. Provider
network attribution does not authorize those actions. AI traffic handling should use proof of
the relevant service/infrastructure and the applicable flags, not a generic provider claim.

Test a claimed-only crawler, provider-only proof, fully scoped service proof, missing identity,
nullable entries and an unknown future status. Check that the application does not promote
provider-only proof to agent identity or grant protected access when metadata is absent.
