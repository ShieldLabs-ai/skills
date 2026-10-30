# Publish and verify

Maintainer procedure for packaging, publishing and verifying an installation.

## Before publication

- Merge the reviewed release PR after CI passes. Check all plugin/marketplace versions and the
  changelog agree. Use the version declared in the plugin manifests.
- Confirm that the repository and its history can be public, including tags and non-default
  branches; remove private operational data and rotate any credentials if found.
- Make the repository public through the organization's normal release process. A private repo
  can be installed by authorized members, but anonymous users cannot install it from GitHub.
- Run the checks below on the exact release commit and only then create its release tag.

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
npx skills add https://github.com/ShieldLabs-ai/skills --agent codex --yes --copy
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

## One-link onboarding release

Publish the canonical `/get-started.md` entry point on the production landing with the published SDKs.
Check that it returns HTTP 200 and raw Markdown; the landing Prompt and editor links must use
that same guide. The guide and setup skill choose OAuth MCP by default or the ShieldLabs dashboard
fallback, execute one path and verify the same browser identification. Browser-only projects do
not need an invented backend; report server enforcement as not configured.

The landing can offer Prompt, Skills and MCP in one control. `npx skills add` installs instructions,
not SDKs or an OAuth grant. Verify that command anonymously after opening the repository; do not
advertise a private repository as publicly installable. Do not add a ShieldLabs CLI requirement.
