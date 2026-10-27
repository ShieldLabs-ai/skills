# Publish and verify

The package is prepared for public installation. These instructions are a release procedure,
not a claim that this repository is already public or listed in an official plugin directory.

## Before publication

The 2026-10-28 audit reproduced a contract mismatch: published Node 1.0.1 preserves the signed
current webhook in `raw`, but its normalized identification ID can be empty. Resolve the
application-SDK compatibility preflight before advertising a complete application integration;
passing MCP checks or Markdown tests does not close it. See
[the SDK contract checklist](skills/shieldlabs-server/references/sdk-contract.md).

- Merge the reviewed release PR after CI passes. Check all plugin/marketplace versions and the
  changelog agree. This release targets 1.1.0.
- Confirm that the repository and its history can be public, including tags and non-default
  branches; remove private operational data and rotate any credentials if found.
- Make the repository public through the organization's normal release process. A private repo
  can be installed by authorized members, but anonymous users cannot install it from GitHub.
- Run the checks below on the exact release commit and only then create tag `v1.1.0`.

```sh
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests
python3 scripts/package_release.py
```

The release workflow validates the tag/version, packages all eight skills **and** hidden plugin
manifests, commands, rules, agent guide and `.mcp.json`, then uploads the ZIP and SHA-256 checksum.
The archive deliberately excludes Git history, local environment files and development caches.

## Public installation smoke test

From a fresh directory without GitHub credentials, verify GitHub's README/archive are accessible,
then install using the documented public path:

```sh
npx skills add https://github.com/ShieldLabs-ai/shieldlabs-skills --agent codex --yes --copy
```

Confirm all eight skill folders are installed and their reference files/scripts are present.
This installs instructions only. Connect MCP separately using the documented client commands.
For plugin installation, use the README's Claude Code or Codex commands and check the remote MCP
entry is loaded once. Complete OAuth with a test account and run `shieldlabs_check_connection`,
`shieldlabs_list_domains` and a domain read. No keys should be requested for MCP sign-in.

With an authorized test website, verify a fresh browser identification, the same UUID in History,
its Risk Score and explanation. Test a webhook only on an authorized receiver. Do not create,
delete or rotate production resources solely for a package-installation smoke test.

## Distribution

A public GitHub repository, a GitHub release and an official client-directory listing are separate
states. Publish only verified install commands. Do not claim an official Cursor/Claude directory
listing until its public listing URL is checked. Client UI and OAuth flows must be tested in that
client; parsing the config alone is not an end-to-end installation test.

## SDK installation verification (2026-10-28)

JS and Node 1.1.0 candidate archives are compatible with the current identification IDs and
20-flag contract. They are not published npm releases. The React 1.0.0 binding compiled with
the browser candidate. A clean React/Vite app and Node/SQLite backend ran on OrbStack, using
a browser-only mapping for an owned EMD QA hostname and real production ShieldLabs services.
Two fresh identification UUIDs matched between browser, Node SDK and OAuth MCP, both scoring
100/Dangerous for automated Chromium. Replay, missing/malformed IDs and restart persistence
passed. Signed current-contract webhook fixtures passed the local endpoint; external webhook
delivery and a new OAuth authorization grant were not completed in this run.

55 Python tests and 41 executed documentation scenarios passed. A first browser UUID remained
unavailable on subsequent History/MCP reads and still needs investigation. Do not describe the
entire production installation as fully verified or publish the skills as generally compatible
with npm 1.0.1. Publish compatible SDKs first, reinstall from the public registry, and repeat
this installation and webhook delivery before public release.
