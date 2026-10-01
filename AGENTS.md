# ShieldLabs skills for coding agents

This repository holds Agent Skills that integrate ShieldLabs (device intelligence and fraud
detection) into web applications. Each skill is a folder under `skills/` with a `SKILL.md` (the
workflow and rules) and `references/` (details per framework or language). Read the `SKILL.md`
first, then only the reference files for the stack at hand.

## Which skill to use

| Task | Skill |
|---|---|
| Add ShieldLabs to a project, plan the integration, or audit an existing one | [skills/shieldlabs-setup](skills/shieldlabs-setup/SKILL.md) |
| Install and use the browser SDK (plain JavaScript, React, Next.js, Vue and Nuxt, Angular, Svelte and SvelteKit) | [skills/shieldlabs-browser](skills/shieldlabs-browser/SKILL.md) |
| Read verdicts on the server (Node.js, Python, Go, PHP, Java, .NET) | [skills/shieldlabs-server](skills/shieldlabs-server/SKILL.md) |
| Receive and verify webhooks | [skills/shieldlabs-webhooks](skills/shieldlabs-webhooks/SKILL.md) |
| Map Risk Scores, bands and flags to allow, step-up, review or block | [skills/shieldlabs-risk-decisions](skills/shieldlabs-risk-decisions/SKILL.md) |
| Multi-accounting, account sharing, impossible travel, account takeover, ban evasion, promo abuse | [skills/shieldlabs-account-abuse](skills/shieldlabs-account-abuse/SKILL.md) |
| Link identifications to user accounts with a User HID | [skills/shieldlabs-user-linking](skills/shieldlabs-user-linking/SKILL.md) |
| Investigate requests, users, devices and webhook signatures with the ShieldLabs MCP server | [skills/shieldlabs-investigate](skills/shieldlabs-investigate/SKILL.md) |

## Core rules

- The agent loads only from `https://cdn.shieldlabs.ai` through a ShieldLabs browser package. Never
  self-host, proxy or bundle it.
- One identification per protected action: call `identify()` in the action's handler and send the
  `requestId` in the same request. Never identify on render or on route changes.
- Only the Public Key reaches the browser. `SHIELDLABS_API_KEY`, `SHIELDLABS_SECRET_KEY`,
  `SHIELDLABS_WEBHOOK_SECRET` and `USER_HID_SECRET` stay on the server, in environment variables.
- The backend reads the verdict with `identifications.get`, claims each request ID once, refuses
  identifications older than 5 minutes and runs the SDK policy helper.
- No identification means unverified, never clean. `999` is a rate-limit marker, not a score. The
  all-zero device ID means no usable device signals.
- Bands: trusted 0-29, suspicious 30-59, dangerous 60-100. Branch on bands and detection flags;
  never add up signal weights.
- Webhooks: verify `X-Shield-Signature` over the raw body before parsing, deduplicate on
  `data.request_id`, answer within one second.
- User HIDs come from the SDK `userHid` helpers on the server, never raw emails or IDs.
- Use only the public SDK APIs, and confirm package versions on the registry and at
  https://docs.shieldlabs.ai.

## MCP server

In Claude Code, `.mcp.json` starts the read-only ShieldLabs MCP server (`npx -y @shieldlabs-ai/mcp`)
with `SHIELDLABS_API_KEY` and the optional Management API and webhook variables from the
environment. Codex and other clients add the server to their own configuration
([clients.md](skills/shieldlabs-investigate/references/clients.md)). Its tools are listed in
[skills/shieldlabs-investigate](skills/shieldlabs-investigate/SKILL.md).

## Working on this repository

- Run `python3 scripts/validate_skills.py` and `python3 -m unittest discover -s tests` before
  committing.
- Keep each `SKILL.md` short (under 500 lines) and put per-stack detail in `references/`.
- See [CONTRIBUTING.md](CONTRIBUTING.md) for the writing conventions.
