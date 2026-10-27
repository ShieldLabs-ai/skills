# ShieldLabs skills for coding agents

This repository holds Agent Skills that integrate ShieldLabs (device intelligence and fraud
detection) into web applications. Each skill is a folder under `skills/` with a `SKILL.md` (the
workflow and rules) and `references/` (details per framework or language). Read the `SKILL.md`
first, then only the reference files for the stack at hand.

## Which skill to use

| Task | Skill |
|---|---|
| Add ShieldLabs to a project with OAuth MCP by default or dashboard fallback, plan the integration, or audit an existing one | [skills/shieldlabs-setup](skills/shieldlabs-setup/SKILL.md) |
| Install and use the browser SDK (plain JavaScript, React, Next.js, Vue and Nuxt, Angular, Svelte and SvelteKit) | [skills/shieldlabs-browser](skills/shieldlabs-browser/SKILL.md) |
| Read verdicts on the server (Node.js, Python, Go, PHP, Java, .NET) | [skills/shieldlabs-server](skills/shieldlabs-server/SKILL.md) |
| Receive and verify webhooks | [skills/shieldlabs-webhooks](skills/shieldlabs-webhooks/SKILL.md) |
| Map Risk Scores, bands and flags to allow, step-up, review or block | [skills/shieldlabs-risk-decisions](skills/shieldlabs-risk-decisions/SKILL.md) |
| Multi-accounting, account sharing, impossible travel, account takeover, ban evasion, promo abuse | [skills/shieldlabs-account-abuse](skills/shieldlabs-account-abuse/SKILL.md) |
| Link identifications to user accounts with a User HID | [skills/shieldlabs-user-linking](skills/shieldlabs-user-linking/SKILL.md) |
| Connect OAuth MCP, manage domains/webhooks and investigate requests, users and devices with the ShieldLabs MCP server | [skills/shieldlabs-investigate](skills/shieldlabs-investigate/SKILL.md) |

## Guided installation

Follow the setup skill's major-stage checkpoints. Ask about an account only when unknown and no
connection exists. A general install starts with browser identification and a verified result,
then offers only unfinished server verification, webhook or user-linking stages, or finish.
Already requested stages need no repeated question; do not ask before every file or package.
A failed verification is resolved before advancing. Report unconfigured stages at the end.

## Core rules

- The agent loads only from `https://cdn.shieldlabs.ai` through a ShieldLabs browser package. Never
  self-host, proxy or bundle it.
- One identification per protected action: call `identify()` in the action's handler and send the
  `identificationId` in the same request. Never identify on render or on route changes.
- Only the Public Key reaches the browser. `SHIELDLABS_API_KEY`, `SHIELDLABS_SECRET_KEY`,
  `SHIELDLABS_WEBHOOK_SECRET` and `USER_HID_SECRET` stay on the server, in environment variables.
- The backend reads the verdict with `identifications.get`, claims each request ID once, refuses
  identifications older than 5 minutes and runs the SDK policy helper.
- No identification means unverified, never clean. `999` is a rate-limit marker, not a score. The
  all-zero device ID means no usable device signals.
- Bands: trusted 0-29, suspicious 30-59, dangerous 60-100. Branch on bands and detection flags;
  never add up signal weights.
- Webhooks: verify `X-Shield-Signature` over the raw body before parsing, deduplicate on
  verified envelope `event_id`, durably enqueue before answering promptly.
- User HIDs come from the SDK `userHid` helpers on the server, never raw emails or IDs.
- Use only the public SDK APIs, and confirm package versions on the registry and at
  https://docs.shieldlabs.ai.

## MCP server

The plugin connects to `https://mcp.shieldlabs.ai/mcp` over HTTP with OAuth. No API key or local
npm process is required for MCP. See [client setup](skills/shieldlabs-investigate/references/clients.md).
The current server exposes 21 tools; use the [investigate skill](skills/shieldlabs-investigate/SKILL.md)
for their workflows and [catalog](skills/shieldlabs-investigate/references/tools.md) for inputs.

Start with `shieldlabs_check_connection` and `shieldlabs_list_domains`. History takes a hostname;
management takes public UUIDs. Pass the selected hostname explicitly when multiple domains are enabled.
An investigation stays read-only. Mutations need user intent, are never automatically retried, and
require `confirm: true` for destructive operations. Keep secrets masked unless an authorized installer
needs a one-time credential. Never repeat secrets in chat or use private dashboard APIs as a fallback.

Published JS/Node 1.0.1 SDKs use `requestId` / `request_id`; the compatible 1.1.0 candidates use
`identificationId` / `identification_id`. These examples target the candidates; check the installed package types. MCP currently uses
`request_id`. History can omit detailed weights (`signals: []`) even with a nonzero Risk Score.

## Working on this repository

- Run `python3 scripts/validate_skills.py` and `python3 -m unittest discover -s tests` before
  committing.
- Keep each `SKILL.md` short (under 500 lines) and put per-stack detail in `references/`.
- See [CONTRIBUTING.md](CONTRIBUTING.md) for the writing conventions.
