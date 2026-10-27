# Contributing

Thanks for helping improve the ShieldLabs skills. Issues and pull requests are welcome; for
security reports, write to contact@shieldlabs.ai.

## How the repository is organized

- `skills/<name>/SKILL.md`: the workflow, decision tables and rules of one task. Agents load it
  when the task matches its `description`.
- `skills/<name>/references/*.md`: details per framework or language, read only when needed.
- `skills/<name>/scripts/`: optional helper scripts (Python 3, standard library only).
- `commands/`, `rules/`, `AGENTS.md`, `.mcp.json` and the manifests wire the skills into Claude
  Code, Grok, Cursor, Codex and other clients.

## Writing a skill or a reference

- Frontmatter: `name` equals the folder name (kebab-case); `description` says in the third person
  what the skill does and when to use it ("Use when ..."), with the phrases users actually type,
  in at most 1024 characters, without angle brackets or `: ` sequences.
- Keep `SKILL.md` under 500 lines: a short numbered workflow, decision tables, minimal code and
  pitfalls. Move per-stack detail to `references/`, and link every reference file from `SKILL.md`.
- Code samples use only the public APIs of the ShieldLabs SDKs, exactly as their READMEs document
  them. Check names, options and return shapes against the SDK before you change a sample.
- Every sample compiles in context: a complete file, or a function body inside a named function.
  `scripts/validate_skills.py` compiles every Python sample; check Go samples with `gofmt` and PHP
  samples with `php -l`.
- Examples use placeholder keys (`sec_your_private_key`, `whsec_your_signing_secret`,
  `0123456789abcdef0123456789abcdef` as a Public Key), documentation IP addresses (`192.0.2.x`,
  `198.51.100.x`, `203.0.113.x`), UUIDv4 request IDs and Risk Scores in multiples of 5.
- Style: plain, technical English with colons, commas or parentheses instead of em dashes. Say
  "risk signals", "analytics dashboard", "Start free", and use the three bands trusted 0-29,
  suspicious 30-59, dangerous 60-100.
- Anything that depends on a version tells the reader to confirm it on the package registry and at
  https://docs.shieldlabs.ai.

## Checks

Run these before opening a pull request; CI runs them too:

```sh
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests
```

`python3 scripts/check_links.py` checks the external links (it needs network access).

## Releases

1. Update the version in `.grok-plugin/plugin.json`, `.grok-plugin/marketplace.json` (both
   places), `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (both places),
   `.cursor-plugin/plugin.json` and `.codex-plugin/plugin.json`, and add a CHANGELOG entry.
2. Merge to `main`, then push a tag `vX.Y.Z`. The release workflow validates the repository and
   attaches an archive of the skills to a GitHub release.

## Hosted MCP contract

Use the live OAuth endpoint and its current tools as the source for MCP instructions. The input
snapshot in shieldlabs-investigate is a dated contract record, not account data. Keep the published
SDK contract distinct from unreleased GitHub main and MCP argument names. See [PUBLICATION.md](PUBLICATION.md)
for release packaging, anonymous install verification and directory-listing boundaries.
