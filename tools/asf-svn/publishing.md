<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [ASF SVN — website / docs publishing (optional)](#asf-svn--website--docs-publishing-optional)
  - [When this capability applies](#when-this-capability-applies)
  - [How svnpubsub publishing works](#how-svnpubsub-publishing-works)
  - [Publish a site update](#publish-a-site-update)
  - [Staging before production](#staging-before-production)
  - [Write-path confirmation rule](#write-path-confirmation-rule)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ASF SVN — website / docs publishing (optional)

Optional capability for ASF projects that publish their website or
documentation through SVN. Many ASF projects serve their site via
**svnpubsub**: an SVN commit to a designated site path is mirrored to
the live web server within seconds, with no separate deploy step.

This capability is **optional** — a project that publishes its site
some other way (a GitHub Pages build, an asf.yaml-driven publish from a
Git branch, a generated-site commit handled by CI) does not enable it.
Declare it under *Tools enabled → website publishing* only if the
project's site lives in SVN.

`svnpubsub` is one of the release-distribution backends the
`release-rc-cut` and release-announce skills already recognise (the
`release_dist_backend: svnpubsub` value); this document covers the
site/docs side of the same mechanism.

---

## When this capability applies

Use this capability when the project's website source lives under an
SVN path such as:

```text
https://svn.apache.org/repos/asf/<project>/site/             # site source
https://svn.apache.org/repos/infra/websites/production/<project>/   # published tree (svnpubsub-backed)
```

The exact paths are project-specific and are declared in the project
manifest. A project that does not publish via SVN leaves this
capability unconfigured, and the skills skip it.

---

## How svnpubsub publishing works

svnpubsub watches a configured SVN path. When a commit lands there,
the live web server's working copy is updated automatically (a
server-side `svn update` triggered by the commit notification). The
publish action is therefore **just an SVN commit** to the right path —
there is no separate "deploy" command.

This means every recipe below reduces to the `svn` operations already
documented in [`operations.md`](operations.md); the only thing
specific to publishing is *which path* is committed to.

---

## Publish a site update

```bash
# Check out the published site tree (or the site-source path)
svn checkout \
  https://svn.apache.org/repos/asf/<project>/site \
  site-wc

# Edit / regenerate the site content under site-wc/ ...

# Schedule NEW files for addition.
svn add --force site-wc/        # schedules additions only — NOT deletions

# Schedule REMOVED files for deletion. `svn add --force` does not do this,
# so regenerating a site that dropped pages would otherwise leave the
# stale pages versioned and re-commit them — and svnpubsub keeps serving
# them. `svn status` marks missing-but-versioned paths with `!`; feed
# those to `svn rm` so the deletions are part of the commit:
svn status site-wc/ | awk '/^!/{print $2}' | xargs -r svn rm

svn status site-wc/             # review the full add/delete set before commit

# Commit — svnpubsub mirrors this to the live site automatically
svn commit site-wc \
  --username <asf-id> \
  -m "Publish <project> site update: <summary>"
```

For a generated site, regenerate into the working copy first, then run
**both** scheduling steps above (`svn add --force` for new pages and the
`svn status | svn rm` step for removed pages) so deletions propagate —
otherwise stale pages stay live after the commit.

---

## Staging before production

Projects that maintain a staging tree publish to the staging path
first, verify the rendered result, then promote to production with a
server-side copy — the same pattern as a release dev→release
promotion:

```bash
# Promote a verified staging tree to production (server-side, no re-upload)
svn copy \
  https://svn.apache.org/repos/infra/websites/staging/<project> \
  https://svn.apache.org/repos/infra/websites/production/<project> \
  --username <asf-id> \
  -m "Promote <project> site from staging to production"
```

The staging and production paths are project- and infra-specific;
confirm them via `svn list` against the `infra/websites` tree, or from
the project manifest, before committing.

---

## Write-path confirmation rule

Every `svn commit` and `svn copy` in this document is a write-path
operation that publishes to a public website. The calling skill must:

1. Show the exact command(s) and the path being published to.
2. Get explicit user confirmation before executing.
3. Report the SVN revision number on success.

Never publish a site update on autopilot — a bad commit is live
within seconds.
