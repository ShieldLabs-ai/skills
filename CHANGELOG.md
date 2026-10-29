# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-10-29

- Align all eight skills with hosted OAuth MCP, current domain-scoped History and availability.
- Use Node.js 1.3.0 and browser JS 1.1.0 in verified examples, with stack-specific public HTTP reads for other backends.
- Keep background checks, protected actions, User HID linking and backend High-Risk Events distinct.
- Add clean npm installation, framework type checks and executable Node/JS customer-example tests.

## [1.2.0] - 2026-10-29

- Align all 21 MCP tool inputs with domain UUIDs, entity cards, list cursors and flat filters.
- Update setup verification and investigation playbooks; preserve unavailable risk and signal states.
- Generate the input catalog from registered MCP tools and validate installable archives.

## [1.1.0] - 2026-10-28

- Add evidence-based setup progress/resume, hostname coverage, backend HRE consumption,
  multi-account subscription/consumer and claim-versus-proof identity guidance.
- Route signed group events in all six server language references, ship pinned public wire
  schemas and an executable transactional consumer with ordering, retry and rollback tests.
- Add application-owned order/promo context joins, including webhook-first arrival.
- Update the MCP catalog for multiaccount and 20 current flags; deployed capability
  and published SDK versions still require their separate release checks.

- Add guided checkpoints for account setup and major integration stages, a next-step menu and
  clear completion status, without repeated approval for already selected work.

Public release of the hosted OAuth MCP skills and installation workflows.

- Connect the hosted HTTP MCP with OAuth instead of starting a local API-key server.
- Document all 21 current tools, account/domain selection, webhook lifecycle and real-visit verification.
- Separate application SDK credentials from MCP sign-in and document the identifier field names.
- Add current-tool contract checks and package the complete plugin, including MCP configuration.
- Document public installation and release verification for maintainers.
- Re-audit all eight skills after source refresh; gate old SDK normalization, preserve raw webhook envelopes, dedupe current event IDs and correct Test/retry assumptions.

- Add `/shieldlabs:get-started` as an entry point, with OAuth MCP by default and the dashboard fallback.
- Keep first install scoped to the existing app, with no invented backend or mandatory webhook.
- Document the current 20-flag Node model and current-wire History mock; preserve explicit legacy tests.
- Correct remaining Node reference identifiers, SDK compatibility wording and webhook Test semantics.
- Retain Grok metadata, with remote HTTP/OAuth support explicitly unverified in that client.

## [1.0.0] - 2026-09-30

### Added

- Claude Code plugin marketplace `shieldlabs` with the plugin `shieldlabs`, plus plugin manifests
  for Cursor (`.cursor-plugin/`) and Codex (`.codex-plugin/`, `.agents/plugins/`; a skills-only
  plugin whose marketplace entry asks for no authentication on install).
- Eight skills: `shieldlabs-setup` (entry point and audit mode), `shieldlabs-browser`,
  `shieldlabs-server`, `shieldlabs-webhooks`, `shieldlabs-risk-decisions`,
  `shieldlabs-account-abuse`, `shieldlabs-user-linking` and `shieldlabs-investigate`, with
  references per framework and language for the ShieldLabs SDKs 1.x: identify helpers that resolve
  `null` instead of rejecting, share a running identification with the same User HID and
  effective timeout, and let the `userId` key of a call override the helper's User HID
  (`undefined` and `null` mean anonymous), `autoLoad` with `load()` and `getAgent()` for consent
  and early identification (calls before `load()`, `runOnMount` included, fail fast; after a
  failed or timed-out load `getAgent()` rejects and `runOnMount` does not run again), the total
  wait budget of `identifications.get` in every server SDK (`waitFor` and `noWait()` in Java,
  where `waitFor(Duration.ZERO)` polls once; `NoWait` in Go, where a zero `Timeout` means 10 s)
  with each wait capped at the larger of 2 s and the poll interval and a 429 that ends the wait
  only when its `Retry-After`, capped at 10 s, is longer than the time left, ordinary retries that
  follow `Retry-After` as sent, the User HID lookup rules, a risk policy in which a User HID
  mismatch never softens the band, account-abuse thresholds that count the account or device of
  the action, and the MCP tools with their exact arguments.
- Slash commands `/shieldlabs:setup` and `/shieldlabs:audit`.
- The read-only ShieldLabs MCP server (`npx -y @shieldlabs-ai/mcp`) in `.mcp.json` for Claude Code,
  configured from the environment, with setup snippets for Cursor, Codex, VS Code and other
  clients.
- `rules/shieldlabs.mdc` for Cursor and `AGENTS.md` for other agents.
- Helper scripts in `shieldlabs-setup`: `detect_stack.py` (stack detection) and `audit_scan.py`
  (a read-only scan for common integration problems; test files are skipped for keys and
  hand-written signature checks), and in `shieldlabs-server`:
  `history_mock.py` (a local stand-in of the History API for offline tests).
- `scripts/validate_skills.py` (which also compiles every Python code sample with the Python 3.9
  grammar) and `scripts/check_links.py`, unit tests (including checks that every file stating one
  of the SDK rules above states it in full), and CI and release workflows.

[1.0.0]: https://github.com/ShieldLabs-ai/skills/commit/3b06dc155c7c1a9b349c01424863c0a5213b4296
