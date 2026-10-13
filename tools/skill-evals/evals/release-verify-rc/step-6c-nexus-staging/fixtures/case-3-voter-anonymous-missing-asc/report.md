<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

release-build.md § JVM artefact checks: `nexus_staging_repo:
orgapachefoo-1024`, `jvm_companion_location: nexus-staging`. The RC is
1.0.0-rc1. The runner is a **voter with no Nexus credentials** — no
`~/.config/apache-magpie/asf-nexus/netrc` file exists.

Existence check (anonymous):

```text
curl -fsS -o /dev/null -w '%{http_code}\n' "https://repository.apache.org/content/repositories/orgapachefoo-1024/"
→ HTTP 200 OK
```

Staging repository details (authenticated path):

```text
curl .../service/local/staging/repository/orgapachefoo-1024
→ HTTP 401 Unauthorized
```

Artefact inventory (anonymous web-tree crawl over
`https://repository.apache.org/content/repositories/orgapachefoo-1024/`,
trimmed to one module):

```text
/org/apache/foo/foo-core/1.0.0/
  foo-core-1.0.0.jar            foo-core-1.0.0.jar.asc            foo-core-1.0.0.jar.sha1
  foo-core-1.0.0.pom            foo-core-1.0.0.pom.asc            foo-core-1.0.0.pom.sha1
  foo-core-1.0.0-sources.jar                                      foo-core-1.0.0-sources.jar.sha1
  foo-core-1.0.0-javadoc.jar    foo-core-1.0.0-javadoc.jar.asc    foo-core-1.0.0-javadoc.jar.sha1
```

`release-management verify-rc nexus --inventory <inventory.json> --existence-code 200 --crawl <crawl.txt>`
(no `--rm-credentials`: the runner has none) printed:

```json
{
  "step": "nexus-staging",
  "status": "FAIL",
  "staging_repos": [
    {
      "id": "orgapachefoo-1024",
      "state": "unverified",
      "matches_rc": true
    }
  ],
  "nexus_findings": [
    "foo-core-1.0.0-sources.jar has no sibling .asc in the staging repository — signature coverage must match the main artefacts",
    "STATE-UNVERIFIED: no Nexus credentials, so the authoritative closed state could not be read — verify by hand in the Nexus UI (stagingRepositories)"
  ],
  "paste_recipe": "# 1. Existence (anonymous, every run)\ncurl -fsS -o /dev/null -w '%{http_code}\\n' \\\n  \"https://repository.apache.org/content/repositories/orgapachefoo-1024/\"\n\n# 4. Artefact inventory (anonymous web-tree crawl, every run)\nbase=\"https://repository.apache.org/content/repositories/orgapachefoo-1024\"\ncrawl() {\n  visited=\"\"\n  frontier=\"$base\"\n  while [ -n \"$frontier\" ]; do\n    next=\"\"\n    for dir in $frontier; do\n      case \",$visited,\" in *\",$dir,\"*) continue ;; esac\n      visited=\"$visited,$dir\"\n      for href in $(curl -fsS \"${dir%/}/\" | grep -oE 'href=\"[^\"]+\"' | sed 's/^href=\"//;s/\"$//'); do\n        case \"$href\" in\n          \"../\") continue ;;\n          \"https://\"*|\"http://\"*) path=\"$href\" ;;\n          /*) path=\"https://repository.apache.org$href\" ;;\n          *) path=\"${dir%/}/${href#/}\" ;;\n        esac\n        case \"$path\" in\n          \"$base\"/*) path=\"${path%/}\" ;;\n          *) continue ;;\n        esac\n        case \",$visited,\" in *\",$path,\"*) continue ;; esac\n        case \"$href\" in\n          */) next=\"$next $path\" ;;\n          *) echo \"${path#\"$base/\"}\" ;;\n        esac\n      done\n    done\n    frontier=\"$next\"\n  done\n}\ncrawl"
}
```

Things to classify here:

- The `401` is the expected anonymous shape for `/service/local/...`
  — it says nothing about whether the repository exists. The
  authoritative `state` cannot be read, which is `STATE-UNVERIFIED`
  (a warning naming what to verify by hand in the Nexus UI), never a
  failure: a voter with no Nexus account is the expected runner of
  the anonymous path.
- The inventory is otherwise complete and matching — except
  `foo-core-1.0.0-sources.jar` has no sibling `.asc`, while the main
  jar, the POM and the javadoc companion do. A hard finding: the
  signature coverage is the same rule Step 2 applies to the main
  artefacts.
