# ShieldLabs skills

Agent Skills, slash commands and a hosted OAuth MCP connection that let AI coding agents integrate ShieldLabs
device intelligence and fraud detection into your app.

[![CI](https://github.com/ShieldLabs-ai/skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ShieldLabs-ai/skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/tag/ShieldLabs-ai/skills?label=version&sort=semver)](https://github.com/ShieldLabs-ai/skills/tags)

This repository is a plugin marketplace named `shieldlabs` with one plugin, `shieldlabs`, for
Claude Code, Cursor and Codex, with Grok metadata retained. The skills also work in OpenCode and any other client
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
/plugin marketplace add ShieldLabs-ai/skills
/plugin install shieldlabs@shieldlabs
```

From a shell: `claude plugin marketplace add ShieldLabs-ai/skills`, then
`claude plugin install shieldlabs@shieldlabs`. Restart Claude Code to load the plugin.

### Grok and Claude desktop

The Grok plugin metadata is included. Verify remote HTTP/OAuth support in your Grok version
before enabling MCP. Claude desktop can connect
through a custom connector where available. See [client setup](skills/shieldlabs-investigate/references/clients.md).

### Cursor

Import this repository using From GitHub Repository (`ShieldLabs-ai/skills`) and install the
`shieldlabs` plugin with a project or user scope. Cursor reads `.cursor-plugin/`, the skills and
`rules/shieldlabs.mdc`. To connect the MCP server, see
[MCP setup for Cursor](skills/shieldlabs-investigate/references/clients.md#cursor).

### Codex

```sh
codex plugin marketplace add ShieldLabs-ai/skills
codex plugin add shieldlabs@shieldlabs
```

Start a new Codex session after installing. Codex reads `.codex-plugin/`, the skills and
[AGENTS.md](AGENTS.md). The plugin includes the hosted MCP configuration. Sign in when prompted, or connect it explicitly
with `codex mcp add` and `codex mcp login` ([MCP setup for Codex](skills/shieldlabs-investigate/references/clients.md#codex)).

### `npx skills`

```sh
npx skills add https://github.com/ShieldLabs-ai/skills
```

`npx skills` installs the eight skills; it does not install the plugin's MCP connection.
Follow [MCP client setup](skills/shieldlabs-investigate/references/clients.md) and sign in separately.

### Manual copy

Download the repository and copy the skill folders into your agent's skills directory:

```sh
curl -L https://github.com/ShieldLabs-ai/skills/archive/refs/heads/main.tar.gz | tar -xz
cp -R skills-main/skills/* ~/.claude/skills/
```

| Agent | Skills directory |
|---|---|
| Claude Code | `~/.claude/skills/`, or `.claude/skills/` in a project |
| Grok | `~/.grok/skills/`, or `.grok/skills/` in a project |
| Cursor | `~/.cursor/skills/` |
| Codex | `~/.codex/skills/` |
| OpenCode | `~/.config/opencode/skills/` |
| Other Agent Skills clients | the client's skills directory |

## One-link setup

Give your coding agent: **Read https://shieldlabs.ai/get-started.md and follow its instructions to install ShieldLabs in this project.**

The guide and the setup skill use the same workflow: inspect the project, reuse existing integration,
configure through OAuth MCP by default or the dashboard when chosen, install the matching SDKs and
verify the first identification and Risk Score. A guided menu then offers unfinished server,
webhook and user-linking stages, or finish. Already selected stages continue without repeated
approval, and routine file/package changes do not each need a question. Choose one setup path; do not run both. No separate
ShieldLabs CLI is required. Skills installation and MCP connection are separate operations.

## Quick start

After installing, open your project and ask the agent:

- "Add ShieldLabs to this app and protect signup and checkout", or run
  `/shieldlabs:get-started signup and checkout` (or `/shieldlabs:setup`). The agent detects the stack, states a plan, and uses the scope you authorized to add the browser identification, the server-side check, environment variables
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
| [shieldlabs-investigate](skills/shieldlabs-investigate/SKILL.md) | OAuth connection, all 21 MCP tools, domain and webhook management, investigations and real-visit verification |

Also in the plugin:

- **Slash commands**: [`/shieldlabs:get-started`](commands/get-started.md), [`/shieldlabs:setup`](commands/setup.md) and [`/shieldlabs:audit`](commands/audit.md).
- **Cursor rule**: [`rules/shieldlabs.mdc`](rules/shieldlabs.mdc), attached when a task needs it.
- **Agent guide**: [`AGENTS.md`](AGENTS.md) for Codex and other agents that read it.
- **Helper scripts** in shieldlabs-setup: stack detection and a read-only audit scan (Python 3,
  standard library).

## Connect MCP with OAuth

The plugin includes this remote entry in [`.mcp.json`](.mcp.json):

```json
{
  "mcpServers": {
    "shieldlabs": { "type": "http", "url": "https://mcp.shieldlabs.ai/mcp" }
  }
}
```

Enable the connection in your client. Sign in or create a ShieldLabs account in the fresh
authorization flow, then approve access. You do not need
Node.js, a domain API key or a pasted bearer token for this connection. For skills-only installs:

```sh
# Codex
codex mcp add shieldlabs --url https://mcp.shieldlabs.ai/mcp
codex mcp login shieldlabs --no-browser

# Claude Code: then authenticate through /mcp
claude mcp add --transport http shieldlabs https://mcp.shieldlabs.ai/mcp
```

Choose one setup path to avoid duplicate server entries. Other clients:
[clients.md](skills/shieldlabs-investigate/references/clients.md).

After signing in, ask: "Check the ShieldLabs connection and list my domains."
The agent calls `shieldlabs_check_connection`, then `shieldlabs_list_domains`. Resolve the hostname
to its returned public UUID before History or management calls.

### 21 tools

| Area | Tools (prefix `shieldlabs_`) |
|---|---|
| Connection (1) | `check_connection` |
| Domains (6) | `list_domains`, `get_domain`, `add_domain`, `patch_domain`, `delete_domain`, `rotate_server_key` |
| Webhooks (10) | `list_webhooks`, `get_webhook`, `create_webhook`, `patch_webhook`, `delete_webhook`, `disable_webhook`, `enable_webhook`, `rotate_webhook_secret`, `verify_webhook`, `test_webhook` |
| Investigation (4) | `get_identification`, `list_history`, `get_history`, `explain_risk_score` |

[All arguments and behavior](skills/shieldlabs-investigate/references/tools.md).
Domain/webhook writes are supported and require the user's intent. Deletes, disable, rotations
and disruptive patches require explicit `confirm: true`. Mutations are not automatically retried.
Credentials stay masked by default; one-time secret retrieval is an installer opt-in.

### Verify a real installation

Ask: "Verify a fresh visit on example.com through identification, Risk Score and MCP."
The agent captures the actual browser identification UUID, reads that same ID on the selected
domain, explains the score and checks its history. Scoring is asynchronous; a missing result is
unverified. Empty detailed weights can be valid and do not mean a zero Risk Score.

For webhooks, verification pings, sample deliveries and real scored events are separate checks.
Use an authorized HTTPS receiver. [Step-by-step playbooks](skills/shieldlabs-investigate/references/playbooks.md).

## Application credentials and identifiers

OAuth authenticates the **MCP connection**. Your application's backend still needs its own SDK
API key and, when receiving webhooks, its signing secret. Keep these in a private server environment;
only the Public Key belongs in frontend code. Never paste private keys into chat or commit them.
See [environment setup](skills/shieldlabs-setup/references/environment.md).

The browser returns `identificationId`; the server SDK uses `identification_id`.
Pass the same UUID as MCP `identification_id`. Use the webhook envelope's `event_id` for delivery
deduplication and `data.identification_id` to correlate the identification.
See [identifiers and payloads](skills/shieldlabs-server/references/sdk-contract.md).

## Compatibility

- ShieldLabs SDKs 1.x: `@shieldlabs-ai/js`, `@shieldlabs-ai/react`, `@shieldlabs-ai/next`,
  `@shieldlabs-ai/vue`, `@shieldlabs-ai/angular`, `@shieldlabs-ai/svelte`, `@shieldlabs-ai/node`, `shieldlabs`
  (Python), `shieldlabs-go`, `shieldlabs/shieldlabs-php`, `ai.shieldlabs:shieldlabs-java`,
  `ShieldLabs` (.NET). The hosted MCP is versioned independently of the npm SDKs. The skills tell the agent to confirm current versions
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
.mcp.json           hosted HTTP MCP connection (OAuth)
AGENTS.md           guide for agents that read AGENTS.md
commands/           slash commands
rules/              Cursor rule
skills/             the skills: SKILL.md, references/, scripts/
scripts/            validator, release packaging and link check
tests/              unit tests
```

For release preparation and anonymous installation checks, see
[PUBLICATION.md](PUBLICATION.md). See [CONTRIBUTING.md](CONTRIBUTING.md). Documentation: https://docs.shieldlabs.ai. Analytics
dashboard: https://app.shieldlabs.ai. Support: contact@shieldlabs.ai.

## License

[MIT](LICENSE). Copyright (c) 2026 ShieldLabs Inc.
