# Security Policy

This repo ships no executable code. It ships something arguably more sensitive: the manifest that
decides **which repositories `/plugin install` fetches onto a user's machine**. A wrong or
malicious entry in `marketplace.json` installs someone else's code under Trackmind's name. Treat
every change to that file as a supply-chain change.

## Reporting

**Don't open a public issue for a security problem.**

- **Catalog integrity** — an entry pointing at a repository Trackmind doesn't control, a source
  URL that doesn't match the plugin it claims to be, or anything that would cause a user to
  install unexpected code: report it here, privately, at
  `https://github.com/trackmind-ai/marketplace/security/advisories/new`, or email
  `oss@trackmind.com`.
- **A vulnerability inside a plugin** — report it to that plugin's own repository, which has its
  own security policy and its own maintainers. For example, `mcp-rubriq` issues go to
  [trackmind-ai/mcp-rubriq](https://github.com/trackmind-ai/mcp-rubriq/security/advisories/new).

Expect acknowledgment within 5 business days and an initial assessment within 10.

## What we check before merging a catalog change

Any pull request touching `.claude-plugin/marketplace.json` is reviewed against these, in
addition to normal review:

1. **Ownership.** Every `source` points at a repository under `trackmind-ai`. A source pointing
   anywhere else is rejected by default — listing a third-party plugin is a deliberate decision,
   not a routine merge.
2. **The URL matches the plugin.** The `repo`/`url` genuinely hosts the plugin the entry
   describes. A plausible-looking name is not evidence.
3. **Pins are intentional.** An unpinned git source means users track a moving branch and receive
   whatever lands on it. That's acceptable for a pre-1.0 plugin and stated as such; for a released
   one, `ref` should name a tag.
4. **Renames go through `renames`.** Silently changing a plugin's `name` breaks every existing
   install and is treated as a defect, not a cosmetic edit.

CI enforces the mechanical half of this — reserved marketplace names, source-field shape,
dangling `renames` targets, and that every listed repository and pinned ref actually resolves. The
judgment half (points 1 and 2) is human review; CI cannot tell an intended repository from a
convincing lookalike.

## Scheduled re-validation

CI re-runs the source checks weekly, not just on push. A catalog can break with no commit at all —
a listed repo turns private, a pinned tag gets deleted — and the failure would otherwise surface
first as a broken install for a user.
