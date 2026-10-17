# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Step 6c: gates, the read-only probe recipe, and the classification of its saved output.

The staging repository id is spliced into `curl` URLs the agent runs itself,
and it can come from the planning issue body, so it is validated against the
Nexus shape before any recipe is rendered: anything but
`orgapache<project>-NNNN` (or the literal `snapshots`, which the rules then
flag) is a `SKIP` naming the bad value. Every recipe is a `GET`; nothing
here closes, drops or promotes a repository, and nothing here runs one.
"""

from __future__ import annotations

import json
import re
from typing import Any

from release_management.verify_rc.common import VerifyRc
from release_management.verify_rc.jvm import NAMES_PENDING, is_jvm

NEXUS = "https://repository.apache.org"
NETRC = "~/.config/apache-magpie/asf-nexus/netrc"
ID_SHAPE = re.compile(r"^orgapache[a-z0-9]+-[0-9]+$")
SNAPSHOTS = "snapshots"
CHECKSUMS = (".sha1", ".md5", ".sha256", ".sha512")
_URL_ID = re.compile(
    r"repository\.apache\.org/(?:content/repositories|service/local/staging/repository)/([^/\s`\"'<>)]+)"
)
_ISSUE_LINE = re.compile(r"nexus-staging-repo:\s*`?([^\s`]+)`?", re.IGNORECASE)

CRAWL = """\
base="{base}"
crawl() {{
  visited=""
  frontier="$base"
  while [ -n "$frontier" ]; do
    next=""
    for dir in $frontier; do
      case ",$visited," in *",$dir,"*) continue ;; esac
      visited="$visited,$dir"
      for href in $(curl -fsS "${{dir%/}}/" | grep -oE 'href="[^"]+"' | sed 's/^href="//;s/"$//'); do
        case "$href" in
          "../") continue ;;
          "https://"*|"http://"*) path="$href" ;;
          /*) path="https://repository.apache.org$href" ;;
          *) path="${{dir%/}}/${{href#/}}" ;;
        esac
        case "$path" in
          "$base"/*) path="${{path%/}}" ;;
          *) continue ;;
        esac
        case ",$visited," in *",$path,"*) continue ;; esac
        case "$href" in
          */) next="$next $path" ;;
          *) echo "${{path#"$base/"}}" ;;
        esac
      done
    done
    frontier="$next"
  done
}}
crawl"""


def _id_of(value: str) -> str:
    match = _URL_ID.search(value)
    return match.group(1) if match else value.strip().strip("`").rstrip("/")


def resolve_id(v: VerifyRc, issue_body: str | None) -> tuple[str | None, str | None]:
    """The staging repository id and where it came from: the config key, then the planning issue."""
    configured = v.meta.get("nexus_staging_repo")
    if configured:
        return _id_of(str(configured)), "release-build.md § JVM artefact checks nexus_staging_repo"
    if issue_body:
        line = _ISSUE_LINE.search(issue_body)
        if line:
            return _id_of(line.group(1)), "the planning issue's nexus-staging-repo: line"
        url = _URL_ID.search(issue_body)
        if url:
            return url.group(1), "the staging-repository URL on the planning issue"
    return None, None


def valid_id(repo: str) -> bool:
    return repo == SNAPSHOTS or bool(ID_SHAPE.fullmatch(repo))


def recipe(repo: str, *, rm_credentials: bool) -> str:
    """Recipes 1 and 4 for every runner; 2 and 3 only for an RM pasting into their own terminal."""
    lines = [
        "# 1. Existence (anonymous, every run)",
        "curl -fsS -o /dev/null -w '%{http_code}\\n' \\",
        f'  "{NEXUS}/content/repositories/{repo}/"',
        "",
        "# 4. Artefact inventory (anonymous web-tree crawl, every run)",
        CRAWL.format(base=f"{NEXUS}/content/repositories/{repo}"),
    ]
    if rm_credentials and repo != SNAPSHOTS:
        prefix = repo.rsplit("-", 1)[0]
        lines += [
            "",
            "# 2. Authoritative state (authenticated; paste into your own terminal)",
            f"curl -fsS --netrc-file {NETRC} \\",
            f'  "{NEXUS}/service/local/staging/repository/{repo}" | jq .data',
            "",
            "# 3. Every staging repository for the project (authenticated; your own terminal)",
            f"curl -fsS --netrc-file {NETRC} \\",
            f'  "{NEXUS}/service/local/staging/profile_repositories" \\',
            "| jq -r '.data[] | [.repositoryId, .state, .profileName] | @tsv' \\",
            f'| grep -i "{prefix}"',
        ]
    return "\n".join(lines)


def _skip(reason: str, findings: list[str] | None = None) -> dict[str, Any]:
    return {
        "step": "nexus-staging",
        "status": "SKIP",
        "staging_repos": [],
        "nexus_findings": findings or [],
        "paste_recipe": f"# Step 6c skipped: {reason}",
        "skip_reason": reason,
    }


def gate(
    v: VerifyRc, names: list[str] | None, issue_body: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    """A `SKIP` result when a gate fails (a pending one when `names` is unknown), else `(None, id)`."""
    if str(v.meta.get("jvm_artefact_checks") or "on") == "off":
        return _skip("release-build.md § JVM artefact checks declares jvm_artefact_checks: off"), None
    if not v.is_asf:
        return _skip(
            f"organization is {v.organization}, not ASF: repository.apache.org is ASF infrastructure"
        ), None
    if names is None:
        pending = {
            "step": "nexus-staging",
            "status": None,
            "staging_repos": [],
            "nexus_findings": [],
            "paste_recipe": "# Step 6c pending: no Step 1 listing supplied",
            "pending": [NAMES_PENDING],
        }
        return pending, None
    if not is_jvm(names):
        return _skip("no .jar or .pom in the Step 1 listing (no JVM artefacts)"), None
    repo, _ = resolve_id(v, issue_body)
    if repo is None:
        return (
            _skip(
                "no staging repository id: set nexus_staging_repo in release-build.md § JVM artefact checks, "
                "or put a nexus-staging-repo: line on the planning issue and pass --post-to"
            ),
            None,
        )
    if not valid_id(repo):
        finding = (
            f"nexus_staging_repo value {repo!r} does not match the Nexus id shape (orgapache<project>-NNNN) — "
            "no probe run; supply a valid staging repository id"
        )
        return _skip(f"malformed staging repository id {repo!r}", [finding]), None
    return None, repo


def inventory_paths(text: str, repo: str) -> list[str]:
    """Repository-relative file paths from the crawl output (or a pasted tree listing)."""
    base = f"{NEXUS}/content/repositories/{repo}/"
    files: list[str] = []
    current = ""
    for raw in text.splitlines():
        for token in raw.split():
            token = token.replace(base, "")
            if token.endswith("/"):
                current = token.strip("/")
                continue
            if "/" in token:
                files.append(token.strip("/"))
            elif "." in token and current:
                files.append(f"{current}/{token}")
    return list(dict.fromkeys(files))


def _state(text: str) -> tuple[str, str | None]:
    """(closed | open | unverified, why unverified) from what recipe 2 printed."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        code = re.search(r"\b(401|403|404|5\d\d)\b", text)
        return "unverified", f"the staging API answered {code.group(1) if code else 'without a state'}"
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict) or "state" not in data:
        return "unverified", "the staging API printed no state"
    if data.get("transitioning"):
        return "unverified", f"Nexus is still transitioning the repository (state {data.get('state')!r})"
    state = str(data.get("state"))
    if state in ("closed", "open"):
        return state, None
    return "unverified", f"the staging API reported state {state!r}"


def _profile(text: str) -> list[dict[str, str]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        rows = []
        for line in text.splitlines():
            cells = line.split("\t") if "\t" in line else line.split()
            if len(cells) >= 2 and cells[0].startswith("orgapache"):
                rows.append({"id": cells[0], "state": cells[1], "description": ""})
        return rows
    items = data.get("data", []) if isinstance(data, dict) else data
    return [
        {
            "id": str(i.get("repositoryId")),
            "state": str(i.get("state")),
            "description": str(i.get("description") or ""),
        }
        for i in items
        if isinstance(i, dict) and i.get("repositoryId")
    ]


def _versions(dirs: dict[str, list[str]]) -> set[str]:
    """Versions from `<artifactId>/<version>/` folders that hold `<artifactId>-<version>*.jar|.pom`.

    The artifactId level also holds `maven-metadata.xml` (and its checksums):
    such a folder is not a version folder, so its name is never read as one.
    """
    out: set[str] = set()
    for folder, names in dirs.items():
        parts = folder.split("/")
        if len(parts) < 2:
            continue
        artifact, ver = parts[-2], parts[-1]
        stem = f"{artifact}-{ver}"
        if any(n.startswith(stem) and n.endswith((".jar", ".pom")) for n in names):
            out.add(ver)
    return out


def _inventory_findings(files: list[str], version: str) -> tuple[list[str], bool, list[str]]:
    """Hard findings over the crawl, whether its coordinates match the RC's version, and the other versions."""
    findings: list[str] = []
    present = set(files)
    dirs: dict[str, list[str]] = {}
    for path in files:
        folder, _, name = path.rpartition("/")
        dirs.setdefault(folder, []).append(name)
    versions = sorted(_versions(dirs))
    other = [ver for ver in versions if ver != version]
    # Match only on positive evidence: at least one jar/pom version folder for
    # the RC's own version. A crawl of nothing but maven-metadata.xml (and its
    # checksums) carries no coordinates at all, so it never matches.
    matches = version in versions and not other
    if not files:
        findings.append(f"the staging repository holds no artefacts — nothing for release version {version}")
    elif not versions:
        findings.append(
            "the staging repository holds no .jar or .pom under an <artifactId>/<version>/ folder "
            f"(maven-metadata.xml alone names no coordinates) — nothing for release version {version}"
        )
    for path in files:
        if path.endswith((".jar", ".pom")) and f"{path}.asc" not in present:
            name = path.rsplit("/", 1)[-1]
            findings.append(
                f"{name} has no sibling .asc in the staging repository — signature coverage must match the main artefacts"
            )
    for folder, names in sorted(dirs.items()):
        parts = folder.split("/")
        if len(parts) < 2:
            continue
        artifact, ver = parts[-2], parts[-1]
        main = f"{artifact}-{ver}.jar"
        if main not in names:
            continue  # packaging=pom: no jar, no companions
        for classifier in ("sources", "javadoc"):
            companion = f"{artifact}-{ver}-{classifier}.jar"
            if companion not in names:
                findings.append(f"{main}: companion {companion} is absent from the staging repository")
            elif not any(f"{companion}{suffix}" in names for suffix in CHECKSUMS):
                findings.append(f"{companion} has no checksum sibling in the staging repository")
    return findings, matches, other


def classify(
    v: VerifyRc,
    repo: str,
    *,
    rm_credentials: bool,
    not_probed: bool,
    existence_code: int | None,
    state_text: str | None,
    profile_text: str | None,
    crawl_text: str | None,
) -> dict[str, Any]:
    """Step 6c's JSON contract from the probe output the agent (or the RM) saved."""
    hard: list[str] = []
    warn: list[str] = []
    pending: list[str] = []
    own: dict[str, Any] = {"id": repo, "state": "unverified", "matches_rc": None}
    siblings: list[dict[str, Any]] = []

    def result() -> dict[str, Any]:
        repos = sorted([own, *siblings], key=lambda r: str(r["id"]))
        status = "FAIL" if hard else None if pending else "WARN" if warn else "PASS"
        out: dict[str, Any] = {
            "step": "nexus-staging",
            "status": status,
            "staging_repos": repos,
            "nexus_findings": hard + warn,
            "paste_recipe": recipe(repo, rm_credentials=rm_credentials),
        }
        if pending and not hard:
            out["pending"] = pending
        return out

    if not_probed:
        warn.append(
            f"STATE-UNVERIFIED (not probed): the sandbox refused the probe before it left the machine, so {repo} "
            "was not checked — this is not 'repository not reachable'; run the paste_recipe from your own terminal"
        )
        return result()
    if existence_code is None:
        pending.append("--existence-code: what recipe 1 printed")
    elif existence_code == 404:
        own["matches_rc"] = False
        hard.append(
            f"{repo} is not reachable at the id given for this RC (404 on the content tree) — "
            "the RC's jar surface does not exist there"
        )
        return result()
    elif existence_code != 200:
        warn.append(
            f"STATE-UNVERIFIED: recipe 1 answered HTTP {existence_code} for {repo} (not a 404 and not a FAIL) — "
            "verify the repository by hand in the Nexus UI"
        )
        return result()

    files = inventory_paths(crawl_text, repo) if crawl_text is not None else None
    if repo == SNAPSHOTS:
        own["matches_rc"] = False
        snapshot_versions = sorted({p.rsplit("/", 2)[-2] for p in files or [] if p.count("/") >= 1})
        tail = (
            f"; the RC's jars appear to be {', '.join(snapshot_versions)} artefacts"
            if snapshot_versions
            else ""
        )
        hard.append(
            "the id resolves to the snapshots repository (content/repositories/snapshots/) — never a valid vote target"
            + tail
        )
        return result()

    if rm_credentials:
        if state_text is None:
            pending.append("--state: what recipe 2 printed")
        else:
            state, why = _state(state_text)
            own["state"] = state
            if state == "open":
                hard.append(
                    f"{repo} is open — still mutable, not a valid vote target; the RM must close it before the [VOTE] opens"
                )
            elif state == "unverified":
                warn.append(
                    f"STATE-UNVERIFIED: {why}, so the authoritative closed state of {repo} could not be read — verify by hand in the Nexus UI (stagingRepositories)"
                )
        if profile_text is None:
            pending.append("--profile: what recipe 3 printed")
        else:
            prefix = repo.rsplit("-", 1)[0]
            for row in _profile(profile_text):
                if row["id"] == repo:
                    if state_text is None and row["state"] in ("closed", "open"):
                        own["state"] = row["state"]
                    continue
                if not row["id"].startswith(prefix + "-"):
                    continue
                state = row["state"] if row["state"] in ("closed", "open") else "unverified"
                siblings.append({"id": row["id"], "state": state, "matches_rc": False})
                described = f", {row['description']}" if row["description"] else ""
                warn.append(
                    f"{row['id']} is a stale sibling staging repository ({row['state']}{described}) — "
                    f"drop it after confirming this RC is {repo}"
                )
    else:
        warn.append(
            "STATE-UNVERIFIED: no Nexus credentials, so the authoritative closed state could not be read — "
            "verify by hand in the Nexus UI (stagingRepositories)"
        )

    if files is None:
        pending.append("--crawl: what recipe 4 printed")
    else:
        findings, matches, other = _inventory_findings(files, v.version)
        own["matches_rc"] = matches
        if other:
            hard.append(
                f"{repo} holds artefacts for {', '.join(other)} but the RC declares release version {v.version} — "
                "the vote would cover jars for some other version"
            )
        hard += findings
    return result()
