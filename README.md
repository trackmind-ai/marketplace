# Trackmind — Claude Code Plugin Marketplace

[![CI](https://github.com/trackmind-ai/marketplace/actions/workflows/ci.yml/badge.svg)](https://github.com/trackmind-ai/marketplace/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

This repo is a **catalog only**. It holds one manifest —
[`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) — listing every Claude Code
plugin Trackmind publishes. There's no plugin code here; each plugin lives in its own repository
with its own issues, CI, and release history.

## Install

Register the marketplace once per machine:

```
/plugin marketplace add trackmind-ai/marketplace
```

Then install anything in it:

```
/plugin install mcp-rubriq@trackmind
```

That first command is a **one-time step**. Installing more Trackmind plugins later needs only the
second command — you don't re-add the marketplace. Re-running the first command anyway is
harmless; it's idempotent.

> **If `marketplace add` fails with a host-key error:** the `owner/repo` shorthand clones over
> SSH by default, which fails on a machine that has never trusted GitHub's SSH host key. Set
> `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` to clone over HTTPS instead, or pass the full HTTPS URL.

## Plugins

| Plugin | What it does | Repository |
|---|---|---|
| **[mcp-rubriq](https://github.com/trackmind-ai/mcp-rubriq)** | Grades MCP (Model Context Protocol) servers against a published 28-rule quality rubric. | `trackmind-ai/mcp-rubriq` |

## Why one marketplace instead of one per plugin

Claude Code registers **one marketplace per name, per user** — adding a second marketplace under
an existing name silently replaces the first. If every plugin repo shipped its own manifest named
`trackmind`, installing a second Trackmind plugin would knock out the first.

A single catalog also means someone who arrives for one plugin already has the rest available.
Install `mcp-rubriq`, and every other Trackmind plugin is one command away with no second
`marketplace add`.

## Adding a plugin to the catalog

This repo changes only when a plugin ships, or an entry's metadata moves.

1. Add an entry to the `plugins` array in `.claude-plugin/marketplace.json`, pointing at the
   plugin's own repository. Use `git-subdir` when the plugin's `plugin.json` lives in a
   subdirectory — the usual case for a repo that ships one plugin alongside its tests — or
   `github` when the plugin manifest sits at the repo root.
2. Pin `ref` to a release tag once that plugin cuts one. Without a pin, Claude Code resolves the
   branch's current commit, so users get an update on every push to that branch.
3. Run the validator, which is exactly what CI runs:
   ```bash
   python scripts/validate_marketplace.py --check-sources
   ```
4. Update the table above.

**Renaming or removing a plugin?** Don't just edit `name` — that breaks every existing install,
because users reference it in their settings. Add a `renames` entry mapping the old name to the
new one (or to `null` if removed) so existing users migrate automatically instead of hitting
`plugin-not-found`.

## Security

This catalog decides what code `/plugin install` fetches onto a user's machine, which makes any
change to `marketplace.json` a supply-chain change. See [`SECURITY.md`](SECURITY.md) for the
review rules and how to report a problem.

## License

MIT — see [`LICENSE`](LICENSE). This covers the manifest and this repo's own files. Each listed
plugin is licensed separately in its own repository.
