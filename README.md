# ShieldLabs skills

Agent Skills, slash commands and an MCP server that let AI coding agents integrate ShieldLabs
device intelligence and fraud detection into your app.

[![CI](https://github.com/ShieldLabs-ai/shieldlabs-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ShieldLabs-ai/shieldlabs-skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/tag/ShieldLabs-ai/shieldlabs-skills?label=version&sort=semver)](https://github.com/ShieldLabs-ai/shieldlabs-skills/tags)

This repository is a plugin marketplace named `shieldlabs` with one plugin, `shieldlabs`, for
Claude Code and for Grok. The same skills work in Cursor, Codex, OpenCode and any other client
that reads Agent Skills. New to ShieldLabs? [Start free](https://app.shieldlabs.ai).

## How it fits

A ShieldLabs integration always has three steps, and the skills teach an agent each of them:

1. **Browser.** The ShieldLabs agent, loaded from `https://cdn.shieldlabs.ai` by a browser SDK,
   runs an identification when a user performs a protected action (signup, login, checkout) and
   hands the page a request ID.
2. **Your backend.** It receives the request ID with the action and reads the verdict from the
   History API with a server SDK, or receives it in a signed `identification.scored` webhook.
3. **Decision.** Your backend acts on the Risk Score (trusted 0-29, suspicious 30-59, dangerous
   60-100), the detection flags and the identifiers, for example how many accounts one device has.

## Install

### Claude Code

```text
/plugin marketplace add ShieldLabs-ai/shieldlabs-skills
/plugin install shieldlabs@shieldlabs
```

From a shell: `claude plugin marketplace add ShieldLabs-ai/shieldlabs-skills`, then
`claude plugin install shieldlabs@shieldlabs`. Restart Claude Code to load the plugin.

### Grok

The same marketplace and the same plugin. Grok reads `.grok-plugin/`, the skills, the slash
commands and [`.mcp.json`](.mcp.json).

```sh
grok plugin marketplace add ShieldLabs-ai/shieldlabs-skills
grok plugin install shieldlabs --trust
```

Start a new Grok session after installing. Export `SHIELDLABS_API_KEY` in the shell that starts
Grok, then enable the `shieldlabs` server under `/mcps`. Setup:
[MCP setup for Grok](skills/shieldlabs-investigate/references/clients.md#grok).

### Claude desktop app

Open the plugin manager, add the marketplace `ShieldLabs-ai/shieldlabs-skills` and install the
`shieldlabs` plugin.

### Cursor

Open Customize in the sidebar and install the plugin from the Cursor marketplace, or import this
repository with From GitHub Repository (`ShieldLabs-ai/shieldlabs-skills`) and install the
`shieldlabs` plugin with a project or user scope. Cursor reads `.cursor-plugin/`, the skills and
`rules/shieldlabs.mdc`. To connect the MCP server, see
[MCP setup for Cursor](skills/shieldlabs-investigate/references/clients.md#cursor).

### Codex

```sh
codex plugin marketplace add ShieldLabs-ai/shieldlabs-skills
codex plugin add shieldlabs@shieldlabs
```

Start a new Codex session after installing. Codex reads `.codex-plugin/`, the skills and
[AGENTS.md](AGENTS.md). The Codex plugin carries the skills only: connect the MCP server in
`~/.codex/config.toml` ([MCP setup for Codex](skills/shieldlabs-investigate/references/clients.md#codex)).

### `npx skills`

```sh
npx skills add https://github.com/ShieldLabs-ai/shieldlabs-skills
```

### Manual copy

Download the repository and copy the skill folders into your agent's skills directory:

```sh
curl -L https://github.com/ShieldLabs-ai/shieldlabs-skills/archive/refs/heads/main.tar.gz | tar -xz
cp -R shieldlabs-skills-main/skills/* ~/.claude/skills/
```

| Agent | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills/`, or `.claude/skills/` in a project |
| Grok | `~/.grok/skills/`, or `.grok/skills/` in a project |
| Cursor | `~/.cursor/skills/` |
| Codex | `~/.codex/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| Other Agent Skills clients | the client's skills directory |

## Quick start

After installing, open your project and ask the agent:

- "Add ShieldLabs to this app and protect signup and checkout", or run
  `/shieldlabs:setup signup and checkout`. The agent detects the stack, proposes a plan, and after
  you confirm it adds the browser identification, the server-side check, environment variables
  and a verification checklist.
- "Audit our ShieldLabs integration", or run `/shieldlabs:audit`, for a report of problems by
  severity with fixes.
- "Investigate the ShieldLabs request 6f1c2e8a-3b5d-4c7e-8f9a-0b1c2d3e4f5a" or "Which accounts used
  this device?", answered with the bundled MCP server.

## What is covered

| Skill | Covers |
|---|---|
| [shieldlabs-setup](skills/shieldlabs-setup/SKILL.md) | Entry point: stack detection, the integration plan, keys and environment variables, verification checklist, and audit mode for an existing integration |
| [shieldlabs-browser](skills/shieldlabs-browser/SKILL.md) | The browser SDK for plain JavaScript, React, Next.js, Vue and Nuxt, Angular, Svelte and SvelteKit: identify helpers that resolve `null`, early identification with `getAgent()`, consent with `autoLoad` and `load()`, Content Security Policy, call budget |
| [shieldlabs-server](skills/shieldlabs-server/SKILL.md) | Reading verdicts with the Node.js, Python, Go, PHP, Java and .NET SDKs; waiting for the verdict within a total budget, replay and freshness guards |
| [shieldlabs-webhooks](skills/shieldlabs-webhooks/SKILL.md) | Receiving `identification.scored`, verifying `X-Shield-Signature` over the raw body, deduplication, fast answers |
| [shieldlabs-risk-decisions](skills/shieldlabs-risk-decisions/SKILL.md) | Allow, step-up, review or block per action, from bands, flags, the `999` marker, missing identifications and User HID mismatches |
| [shieldlabs-account-abuse](skills/shieldlabs-account-abuse/SKILL.md) | Multi-accounting, account sharing, impossible travel, account takeover, ban evasion and promo abuse with History API lookups |
| [shieldlabs-user-linking](skills/shieldlabs-user-linking/SKILL.md) | User HIDs computed on the server and passed to the browser SDK |
| [shieldlabs-investigate](skills/shieldlabs-investigate/SKILL.md) | Investigations with the ShieldLabs MCP server |

Also in the plugin:

- **Slash commands**: [`/shieldlabs:setup`](commands/setup.md) and [`/shieldlabs:audit`](commands/audit.md).
- **Cursor rule**: [`rules/shieldlabs.mdc`](rules/shieldlabs.mdc), attached when a task needs it.
- **Agent guide**: [`AGENTS.md`](AGENTS.md) for Codex and other agents that read it.
- **Helper scripts** in shieldlabs-setup: stack detection and a read-only audit scan (Python 3,
  standard library).

## The bundled MCP server

In Claude Code and in Grok, [`.mcp.json`](.mcp.json) starts the ShieldLabs MCP server with
`npx -y @shieldlabs-ai/mcp` (Node.js 20 or later). In Grok the plugin must be trusted before that
server starts. Cursor, Codex and other clients add it to their own MCP configuration. Every tool is read-only: read an identification by request ID, search the History API,
summarize an account, a device or an IP address, explain a Risk Score, verify a webhook signature,
read the domain profile. The server reads its keys from the environment that starts your client:

```bash
export SHIELDLABS_API_KEY=sec_your_private_key   # Private API Key of the domain
```

Without the key it starts with the offline tools only (explain a score, verify a signature, current
time). Setup for other clients: [clients.md](skills/shieldlabs-investigate/references/clients.md).

## Keys

Copy the keys from the analytics dashboard at https://app.shieldlabs.ai: Integration > API keys
for the domain keys, Integration > Webhooks for each endpoint's signing secret.

| Variable | Key | Where it belongs |
|---|---|---|
| `SHIELDLABS_PUBLIC_KEY` (with `VITE_`, `NEXT_PUBLIC_`, `NUXT_PUBLIC_` or `PUBLIC_`) | Public Key | Your frontend build |
| `SHIELDLABS_API_KEY` | Private API Key (`sec_...`) | Your backend, and the MCP server |
| `SHIELDLABS_WEBHOOK_SECRET` | Webhook signing secret (`whsec_...`) | Your backend (optional for the MCP server) |
| `SHIELDLABS_SECRET_KEY`, `SHIELDLABS_DOMAIN` | Secret Key and registered domain | Your backend or the MCP server, for the domain profile (optional) |
| `USER_HID_SECRET` | Your own random secret for User HIDs | Your backend |

The skills keep keys in environment variables, add placeholders to `.env.example` and never put a
server key in browser code. Do not paste keys into a chat with an agent: the MCP server reads them
from its environment.

## Compatibility

- ShieldLabs SDKs 1.x: `@shieldlabs-ai/js`, `@shieldlabs-ai/react`, `@shieldlabs-ai/next`,
  `@shieldlabs-ai/vue`, `@shieldlabs-ai/angular`, `@shieldlabs-ai/svelte`, `@shieldlabs-ai/node`, `shieldlabs`
  (Python), `shieldlabs-go`, `shieldlabs/shieldlabs-php`, `ai.shieldlabs:shieldlabs-java`,
  `ShieldLabs` (.NET) and `@shieldlabs-ai/mcp`. The skills tell the agent to confirm current versions
  on the package registries and at https://docs.shieldlabs.ai.
- Clients: Claude Code, Grok, the Claude desktop app, Cursor, Codex, OpenCode and other clients that read
  Agent Skills (`SKILL.md` with YAML frontmatter).
- The helper scripts need Python 3.9 or later; the skills work without them.

## Development

```sh
python3 scripts/validate_skills.py         # frontmatter, lengths, links, anchors, manifests
python3 -m unittest discover -s tests      # validator, helper script and documented SDK rule tests
python3 scripts/check_links.py             # external links (network)
```

Layout:

```text
.grok-plugin/       Grok plugin and marketplace manifests
.claude-plugin/     Claude Code plugin and marketplace manifests
.cursor-plugin/     Cursor plugin and marketplace manifests
.codex-plugin/      Codex plugin manifest
.agents/plugins/    Codex marketplace manifest
.mcp.json           the bundled MCP server
AGENTS.md           guide for agents that read AGENTS.md
commands/           slash commands
rules/              Cursor rule
skills/             the skills: SKILL.md, references/, scripts/
scripts/            validator and link check
tests/              unit tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Documentation: https://docs.shieldlabs.ai. Analytics
dashboard: https://app.shieldlabs.ai. Support: contact@shieldlabs.ai.

## License

[MIT](LICENSE). Copyright (c) 2026 ShieldLabs Inc.
