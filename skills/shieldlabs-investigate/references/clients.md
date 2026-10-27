# Connect the hosted MCP

Endpoint: **`https://mcp.shieldlabs.ai/mcp`**. Transport: HTTP (Streamable HTTP).
Authentication: **OAuth in the client** with the user's ShieldLabs account.
No domain API keys or manually copied access tokens belong in the MCP config.

Installing skills and connecting MCP are separate operations. Plugin-aware clients can load the
repository's `.mcp.json`; copying SKILL.md folders or using `npx skills` installs instructions only.
If a client already has `shieldlabs` configured, update that entry instead of adding a duplicate.

## Claude Code

The plugin includes the remote configuration. Enable it and sign in through `/mcp`.
For a standalone connection without the plugin:

```sh
claude mcp add --transport http shieldlabs https://mcp.shieldlabs.ai/mcp
```

Use `/mcp` to authenticate. See [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp).

## Codex

The plugin's `mcpServers` points to `.mcp.json`. For a standalone connection, or after installing
only the skills:

```sh
codex mcp add shieldlabs --url https://mcp.shieldlabs.ai/mcp
codex mcp login shieldlabs
```

Equivalent user config in `~/.codex/config.toml`:

```toml
[mcp_servers.shieldlabs]
url = "https://mcp.shieldlabs.ai/mcp"
```

Run the login command after saving the config. Do not add a bearer token or API key.
See [Codex MCP documentation](https://developers.openai.com/codex/mcp).

When the user wants to sign in in their own browser, run `codex mcp login shieldlabs --no-browser`
and give them the new authorization URL before opening it anywhere yourself. Complete the entire
flow in that browser. Keep one pending flow: overlapping consent tabs or moving an already-open
consent page to another browser can cause `binding_mismatch` / "Cannot connect this app". Restart
the login with a fresh authorization URL if that occurs. Do not weaken the browser-binding check.
The local native client receives the loopback callback; never ask the user to paste an OAuth code,
callback URL containing a code, access token or refresh token into chat.


## Cursor

Use the plugin's `.mcp.json` when supported, or add this to the client's user/project MCP config:

```json
{
  "mcpServers": {
    "shieldlabs": { "type": "http", "url": "https://mcp.shieldlabs.ai/mcp" }
  }
}
```

Connect and complete OAuth from the MCP settings. See [Cursor MCP documentation](https://cursor.com/docs/mcp).

## VS Code

Use `.vscode/mcp.json` (notice `servers`, not `mcpServers`):

```json
{
  "servers": {
    "shieldlabs": { "type": "http", "url": "https://mcp.shieldlabs.ai/mcp" }
  }
}
```

Start the server entry and follow the sign-in prompt.
See [VS Code MCP documentation](https://code.visualstudio.com/docs/agent-customization/mcp-servers).

## Claude desktop app

Add a custom connector with the endpoint URL in the app's connector settings and complete OAuth.
A local stdio entry in `claude_desktop_config.json` is not the hosted OAuth setup.
Custom connector availability depends on the app/account; consult its current connector UI.

## Grok and other clients

The Grok plugin manifest retains its `.mcp.json` reference and the skills remain portable.
Remote HTTP plus OAuth support must be checked in the installed client version; the local Grok
client was not available for verification of this release. Do not fall back to passing API keys
or bearer tokens through a command line. In any Agent Skills client without HTTP/OAuth support,
use the skills for application code and connect the MCP from a supported client above.

## Verify the connection

1. Sign in, then run `shieldlabs_check_connection` with `{}`.
2. Run `shieldlabs_list_domains` with `{}` and match the intended hostname.
3. Read `shieldlabs_get_domain` using its UUID; keys should be masked.
4. With an identification UUID from a real browser visit, run `shieldlabs_get_identification`
   using the hostname and `wait: true`, then `shieldlabs_explain_risk_score`.

No result is created merely by connecting. The site must have the production snippet, receive a
visit and complete scoring. Domain/webhook changes require an authorized configuration task.

## Migrate from the old local MCP

Remove the old `command: npx`, `args: ["-y", "@shieldlabs-ai/mcp"]` and MCP-only `env` or manually
set authorization headers. Replace that entry with the remote config and sign in. Keep API keys
needed by the application's backend in its private environment; OAuth replaces MCP authentication,
not application SDK credentials. Restart/reload the client if it caches the old tool list.
