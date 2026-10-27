---
description: Install ShieldLabs using OAuth MCP or the dashboard, integrate the matching SDKs and verify the first result
argument-hint: "[protected actions or notes, for example: signup and checkout]"
---

Use the [shieldlabs-setup skill](../skills/shieldlabs-setup/SKILL.md).

User notes: $ARGUMENTS

Inspect the project and existing integration. Configure through OAuth MCP by default, or the
ShieldLabs dashboard if the user chooses it or MCP is unavailable. Follow one path; wait for
pending OAuth approval. Install only the SDKs and code needed for the requested scope. Reuse keys
and resources; do not rotate credentials automatically. For a frontend-only app, do not add a
backend unless requested. Verify the same browser identification and Risk Score through the
chosen path, matching the backend result when present. Report what passed and any blocker.

Use the setup skill's guided checkpoints. A general install starts with browser identification
and a verified first result, then offers applicable unfinished stages: server verification,
signed webhooks, user linking/account checks, or finish. Ask for account status only if unknown
and no authenticated connection exists. Reuse stages and approvals already selected; do not
ask before each file edit or package install.
