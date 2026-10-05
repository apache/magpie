<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Operations: ASF Nexus staging repository](#operations-asf-nexus-staging-repository)
  - [Verified access model (October 2026)](#verified-access-model-october-2026)
  - [Endpoints](#endpoints)
  - [Recipes](#recipes)
    - [1. Existence (anonymous, every run)](#1-existence-anonymous-every-run)
    - [2. Authoritative state (authenticated, RM path)](#2-authoritative-state-authenticated-rm-path)
    - [3. Every staging repository for the project (authenticated, RM path)](#3-every-staging-repository-for-the-project-authenticated-rm-path)
    - [4. Artefact inventory (anonymous, every run)](#4-artefact-inventory-anonymous-every-run)
  - [Egress summary](#egress-summary)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Operations: ASF Nexus staging repository

Every recipe here is a read-only `GET` against
`repository.apache.org`. Nothing in this file writes, transitions, or
deletes anything.

## Verified access model (October 2026)

Probed against the live service with anonymous `curl`:

| Probe | Anonymous result | Consequence |
|---|---|---|
| `GET /service/local/staging/repository/<id>` | `401` | The staging REST API needs credentials — for real and for non-existent ids alike, so a `401` says nothing about whether the id exists |
| `GET /service/local/staging/profile_repositories` | `401` | Enumerating a profile's staging repositories needs credentials too |
| `GET /service/local/repositories/<id>/content?path=/` | `401` | The JSON content API is behind the same realm, even for the public `releases` repository |
| `GET /content/repositories/<id>/` | `404` for a non-existent id, `200` for real ones | The web content tree is anonymous-readable: a `404` here is a genuine *repository does not exist*, a `200` a genuine *it does* |

Two read paths follow, and the calling skill treats them as one
verification with two confidence levels:

- **Anonymous (voter) path** — `https://repository.apache.org/content/repositories/<staging-repo>/`
  serves the artefact tree to anyone. It answers existence, the
  artefact inventory, and `.asc` / checksum coverage. It does **not**
  expose the `state` field, so the closed-not-open rule is verified
  under the `STATE-UNVERIFIED` label on this path.
- **Authenticated (RM) path** — `/service/local/staging/...` with ASF
  Nexus credentials answers the `state` question authoritatively and
  lists every staging repository in the profile, which is how stale
  repositories from an earlier RC are surfaced.

Credentials live under
`~/.config/apache-magpie/asf-nexus/netrc` in netrc format —
`machine repository.apache.org login <user> password <pass>`, `chmod
600` — per the framework's home-directory rule. Recipes read them
with `curl --netrc-file`, so the secret never appears in argv (a
`-u user:pass` expands into `curl`'s command line, visible in `ps`
and in any transcript that records the expanded command).

Note two scope facts the recipes rely on. `~/.config/` is denied to
the sandboxed agent by design, so recipes 2 and 3 (the authenticated
staging API) are for the RM to paste into their **own** terminal; the
agent's own run takes the anonymous path and reports
`STATE-UNVERIFIED` for the state question. And a sandbox network
refusal — the probe blocked before it left the machine — is reported
as `STATE-UNVERIFIED` / not-probed, never as "repository not
reachable": one says the runner could not see, the other says nothing
is there.

## Endpoints

Base: `https://repository.apache.org` (Nexus Repository Manager 2).

| What | Method + path | Auth | Notes |
|---|---|---|---|
| Staging repository details (authoritative `state`) | `GET /service/local/staging/repository/<id>` | required | `state` is `open` or `closed`; `transitioning` is `true` while Nexus works on it — treat as not-yet-closed |
| Profile-wide staging repository list | `GET /service/local/staging/profile_repositories` | required | Returns every staging repository for every profile the account can see — filter to the RC's project and version |
| Repository content (JSON inventory) | `GET /service/local/repositories/<id>/content?path=/` | required | One call per directory; `leaf: true` entries are files |
| Repository content (anonymous web tree) | `GET /content/repositories/<id>/` | anonymous | HTML directory listing; follow links with the crawl recipe below |
| Snapshots repository | `GET /content/repositories/snapshots/` | anonymous | Exists, anonymous, and **never a valid vote target** |

## Recipes

In all recipes: `<repo>` is the staging repository id
(`orgapache<project>-NNNN`, read from the planning issue or
`release-build.md § JVM artefact checks` → `nexus_staging_repo` —
Nexus assigns the number at deploy time, it cannot be predicted).

### 1. Existence (anonymous, every run)

Before the id reaches a URL, validate it: the resolved value must
match the Nexus shape `^orgapache[a-z0-9]+-[0-9]+$` (or be the
literal `snapshots`, which the classification rules then flag as a
finding). The id can come from the planning issue body — content the
step reads — and it is spliced into `curl` URLs the agent runs
itself, so anything else is a `SKIP` that names the bad value, never
a probe.

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' \
  "https://repository.apache.org/content/repositories/<repo>/"
```

`200` — the repository exists and its tree is readable. `404` — the
repository does not exist (or was already promoted/dropped): a hard
`FAIL` worded factually as "repository not reachable at the id given
for this RC" — the same rule `staging-verification.md`, the Step 6c
body and the troubleshooting table state; the RC under vote has no
reachable jar surface. Any other code — report the code verbatim and
stop this recipe; a refusal (sandbox network deny, `403` from a
proxy) is `STATE-UNVERIFIED`, not a `404` and not a `FAIL`.

### 2. Authoritative state (authenticated, RM path)

```bash
curl -fsS --netrc-file ~/.config/apache-magpie/asf-nexus/netrc \
  "https://repository.apache.org/service/local/staging/repository/<repo>" | jq .data
```

Paste this one into the RM's own terminal (`~/.config/` is denied to
the sandboxed agent by design).

Judge `data.state`: `closed` — the only state a `[VOTE]` may be
opened against; `open` — mutable, **not** a valid vote target (a hard
finding, distinct from a missing repository); anything else, or
`data.transitioning: true` — report verbatim as `STATE-UNVERIFIED`
and name what to verify by hand. A `401` on this recipe means the
credentials are missing or stale: fall back to the anonymous path and
report `STATE-UNVERIFIED` — a voter with no Nexus account must not be
told the verification failed. A sandbox network refusal is the same
`STATE-UNVERIFIED`, never a `FAIL`.

### 3. Every staging repository for the project (authenticated, RM path)

```bash
curl -fsS --netrc-file ~/.config/apache-magpie/asf-nexus/netrc \
  "https://repository.apache.org/service/local/staging/profile_repositories" \
| jq -r '.data[] | [.repositoryId, .state, .profileName] | @tsv' \
| grep -i "orgapache<project>"
```

A retried deploy or a reactor deployed in more than one pass leaves
several staging repositories for one version. Surface **all** of them
with their states — stale repositories from an earlier RC are a
common real-world footgun — and never silently pick one. When exactly
one matches the RC's version, proceed with it and note the others as
stale.

### 4. Artefact inventory (anonymous, every run)

The web tree is a plain HTML directory listing, and the listing's
entry hrefs are **absolute** URLs (verified against the live service
in October 2026 — a real line from a `content/repositories/`
directory):

```html
<td><a href="https://repository.apache.org/content/repositories/snapshots/org/apache/maven/plugins/maven-assembly-plugin/3.1.2-SNAPSHOT/">3.1.2-SNAPSHOT/</a></td>
```

Every href is **normalised first**: a relative href is prefixed with the directory being read, and a root-relative one (`/favicon.ico`) is resolved against the host.
Then the `"$base"/*` guard applies to files and directories alike before anything is echoed or enqueued.
So relative directory links are crawled, relative file links come out clean, and page-head `favicon` / stylesheet links never reach the inventory:

```bash
base="https://repository.apache.org/content/repositories/<repo>"
crawl() {
  visited=""
  frontier="$base"
  while [ -n "$frontier" ]; do
    next=""
    for dir in $frontier; do
      case ",$visited," in *",$dir,"*) continue ;; esac
      visited="$visited,$dir"
      for href in $(curl -fsS "${dir%/}/" | grep -oE 'href="[^"]+"' | sed 's/^href="//;s/"$//'); do
        case "$href" in
          "../") continue ;;
          "https://"*|"http://"*) path="$href" ;;
          /*) path="https://repository.apache.org$href" ;;
          *) path="${dir%/}/${href#/}" ;;
        esac
        case "$path" in
          "$base"/*) path="${path%/}" ;;
          *) continue ;;
        esac
        case ",$visited," in *",$path,"*) continue ;; esac
        case "$href" in
          */) next="$next $path" ;;
          *) echo "${path#"$base/"}" ;;
        esac
      done
    done
    frontier="$next"
  done
}
crawl
```

Verified against a stubbed `curl` serving a mixed listing (absolute, relative and root-relative links, the `../` parent link, and page-head `favicon` / stylesheet links): the inventory is exactly the repository's files, nothing else.
The normalisation covers every href form — the absolute URLs the live service emits, and the relative or root-relative forms a proxy or a future Nexus version might emit.
The guard keeps the crawl inside the repository tree, and `visited` makes the recursion terminate.

Collect every path; the classification rules need, per declared
artefact: the main `<artifactId>-<version>.jar`, its `.pom`, both
companions (`-sources.jar`, `-javadoc.jar`), and the `.asc` +
checksum companions of each. Consumers that prefer JSON over the HTML
crawl can use the authenticated content API
(`GET /service/local/repositories/<repo>/content?path=/...`,
`leaf: true` entries are files, each file entry carries
`checksums: {"sha1": ..., "md5": ...}` computed by Nexus at deploy
time).

Two hard exclusions, both `FAIL`-grade when violated:

- **Snapshots.** The snapshots repository
  (`content/repositories/snapshots/`) is never a valid vote target.
  An id of `snapshots`, or any inventory path under
  `.../repositories/snapshots/`, is a finding naming the snapshots
  repository — an RC staged there is an unmarked snapshot, however
  the version string reads.
- **Promoted-away ids.** A `404` on the repository id after a
  successful promotion is *expected* — the id stops serving when its
  content is released. That is why the recipes run against the id
  recorded for **this** RC, and why a `404` is reported as a `FAIL`
  worded "repository not reachable at the id given for this RC" —
  the same rule recipe 1, `staging-verification.md` and
  `jvm-artefacts.md` state.

## Egress summary

One host (`repository.apache.org` — an exact-host entry in the
sandbox's `allowedDomains` allowlists: `.claude/settings.json`,
`tools/sandbox-lint/expected.json`, and the block in
`docs/setup/secure-agent-setup.md`; the sandbox list is exact hosts
only, so a suffix claim would have been false), one method (`GET`),
zero write-verbs. That is the entire egress surface of this adapter — see
`tools/egress-gateway/tool.md`, *Declared egress surfaces*.
