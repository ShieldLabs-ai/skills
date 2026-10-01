# Set up the ShieldLabs MCP server

The server is the npm package `@shieldlabs-ai/mcp` (Node.js 20 or later), started with
`npx -y @shieldlabs-ai/mcp`. It reads its configuration from environment variables:

| Variable | Needed for |
|---|---|
| `SHIELDLABS_API_KEY` | The History API tools. The Private API Key (`sec_...`) of one domain, from the analytics dashboard (Integration > API keys) |
| `SHIELDLABS_SECRET_KEY` and `SHIELDLABS_DOMAIN` | `shieldlabs_get_domain_profile` (optional) |
| `SHIELDLABS_WEBHOOK_SECRET` | The default secret of `shieldlabs_verify_webhook_signature` (optional) |
| `SHIELDLABS_MCP_TOKEN` | The HTTP transport's bearer token |

Without `SHIELDLABS_API_KEY` the server starts with the offline tools only.

## Claude Code with this plugin

The plugin's `.mcp.json` starts the server and passes the four variables above from the
environment of Claude Code. Export them in the shell (or shell profile) that starts Claude Code,
then restart it:

```bash
export SHIELDLABS_API_KEY=sec_your_private_key
```

Check the connection with `/mcp`.

## Claude Code without the plugin

```bash
claude mcp add --transport stdio shieldlabs --env SHIELDLABS_API_KEY=sec_your_private_key -- npx -y @shieldlabs-ai/mcp
```

Add `--scope user` to make it available in every project. To share it with a project without
committing the key, put this in the project's `.mcp.json`; each developer exports the variable:

```json
{
  "mcpServers": {
    "shieldlabs": {
      "command": "npx",
      "args": ["-y", "@shieldlabs-ai/mcp"],
      "env": { "SHIELDLABS_API_KEY": "${SHIELDLABS_API_KEY}" }
    }
  }
}
```

## Claude Desktop

`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "shieldlabs": {
      "command": "npx",
      "args": ["-y", "@shieldlabs-ai/mcp"],
      "env": { "SHIELDLABS_API_KEY": "sec_your_private_key" }
    }
  }
}
```

## Cursor

`.cursor/mcp.json` in the project, or `~/.cursor/mcp.json` for every project:

```json
{
  "mcpServers": {
    "shieldlabs": {
      "command": "npx",
      "args": ["-y", "@shieldlabs-ai/mcp"],
      "env": { "SHIELDLABS_API_KEY": "${env:SHIELDLABS_API_KEY}" }
    }
  }
}
```

Cursor resolves `${env:SHIELDLABS_API_KEY}` from the environment it was started in. Enable or
disable the server from Customize in the sidebar. When you write the key itself into the file,
keep that file out of version control.

## VS Code

`.vscode/mcp.json`, with the key asked for at start-up:

```json
{
  "inputs": [
    { "type": "promptString", "id": "shieldlabs-api-key", "description": "ShieldLabs Private API Key", "password": true }
  ],
  "servers": {
    "shieldlabs": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@shieldlabs-ai/mcp"],
      "env": { "SHIELDLABS_API_KEY": "${input:shieldlabs-api-key}" }
    }
  }
}
```

## Codex

The Codex plugin installs the skills without starting the server. Add it to `~/.codex/config.toml`,
which stays in your home folder, outside any repository:

```toml
[mcp_servers.shieldlabs]
command = "npx"
args = ["-y", "@shieldlabs-ai/mcp"]

[mcp_servers.shieldlabs.env]
SHIELDLABS_API_KEY = "sec_your_private_key"
```

## Other clients, HTTP and Docker

- Any client that starts stdio servers: command `npx`, arguments `-y @shieldlabs-ai/mcp`, and
  `SHIELDLABS_API_KEY` in the server's environment.
- Streamable HTTP: `SHIELDLABS_MCP_TOKEN=<long random token> npx -y @shieldlabs-ai/mcp --transport http --port 8787`,
  endpoint `http://127.0.0.1:8787/mcp`, header `Authorization: Bearer <token>`. Without the
  variable, the server generates a token and prints it once to stderr.
- Docker: `docker run --rm -i -e SHIELDLABS_API_KEY ghcr.io/shieldlabs-ai/shieldlabs-mcp:1.0.0`.
- `--tools get_identification,explain_risk_score` exposes only the listed tools; `--offline` never
  fetches remote content.

Confirm the current package version on npm and at https://docs.shieldlabs.ai. Client
configuration formats change between client versions: check the client's own documentation when
a snippet does not load.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Only the offline tools are listed | `SHIELDLABS_API_KEY` is not in the server's environment: set it and restart the client |
| "rejected the key (HTTP 401)" | Use the Private API Key (`sec_...`) of the domain, not its Public Key or Secret Key |
| "No identification ... is available yet" | The identification is new (retry in a few seconds) or from another domain |
| "rate limit was reached (HTTP 429)" | The History API allows about 15 requests per second per domain, shared with the backend: wait, and lower `max_items` |
| Domain profile answers 429 | The Management API blocked the IP for 10 minutes after about 15 calls in a minute |
| Domain profile answers 401 | `SHIELDLABS_DOMAIN` must equal the registered domain, for example `example.com` |
