---
description: Add ShieldLabs identification, risk signals and Risk Score to a website or application using OAuth MCP and matching SDKs
argument-hint: "[protected actions or notes, for example: signup and checkout]"
---

Use the [shieldlabs-setup skill](../skills/shieldlabs-setup/SKILL.md).

User notes: $ARGUMENTS

Inspect the existing website or application and preserve its stack. Configure through OAuth MCP
by default. Use the dashboard when the user chooses it or their client does not support OAuth.
Follow one path. Open the OAuth flow in the user's normal browser: login or signup, then consent;
already signed-in users proceed to consent. Keep one pending flow and wait for its completion.
If tools are missing after login, save a setup checkpoint, ask the user to restart the detected
client by name, return to this same chat and continue. Pause integration changes until tools are
callable; do not switch setup paths while OAuth or discovery is pending.

Install only the matching SDKs and code for the requested scope. Reuse keys and resources;
never rotate credentials automatically. Use `check()` for background identification and `identify()`
for an existing protected action. For an application with accounts, compute User HIDs on the server
and pass them for signed-in checks. Add a backend only when requested.

Verify the same browser UUID and Risk Score through the chosen path, matching the backend result
when present. Use the public domain UUID for History. Read the same identification quietly for a
total of 10–15 seconds, preserving risk/signal availability. Do not create another identification
to poll or infer quota from a missing result. Report persistent failure with its actual evidence.

Use major-stage checkpoints. After the first verified result offer only applicable unfinished
stages: server verification, signed webhooks, user linking/account checks, or finish. Reuse stages
and approvals already selected; do not ask before each file edit or package install.
