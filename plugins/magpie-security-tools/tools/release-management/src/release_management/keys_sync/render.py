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
"""release-keys-sync's Step 0 KEYS lookup and Step 2 KEYS block and command sequence.

The functions are pure. They read what `release-config preflight` / `load
--skill keys-sync` printed, what `release-verify list-keys` printed for the
KEYS file and for the key fetched from the keyserver (release-verify reads
both in a throwaway GNUPGHOME; nothing here runs gpg), the Step 1 JSON, and
the fetched key's text. Nothing here commits, uploads or touches the network
(Golden rule 2). Every UID, fingerprint and URL spliced into a command is
quoted: the UID comes from the keyserver, which is external content.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from release_management.keys_sync.check import InputError, find_key, keys_dir, listed_keys, normalise_fpr
from release_management.shell import dq, w

PUBLIC_BLOCK = re.compile(
    r"-----BEGIN PGP PUBLIC KEY BLOCK-----\r?\n.*?\r?\n-----END PGP PUBLIC KEY BLOCK-----", re.DOTALL
)
PRIVATE_MARKER = "PRIVATE KEY BLOCK"
BACKENDS = ("svnpubsub", "atr", "git", "generic")
READ = {
    "svnpubsub": ["backends/svnpubsub.md"],
    "atr": ["backends/atr.md", "backends/svnpubsub.md"],
    "git": ["backends/git.md"],
    "generic": ["backends/git.md"],
}


class RenderError(ValueError):
    """The skill must refuse to emit this; it surfaces the reason and stops."""


def _one_line(value: object) -> str:
    """External text as one printable line: it cannot add a line to KEYS or to a command."""
    return " ".join("".join(c if c.isprintable() else " " for c in str(value)).split())


# --------------------------------------------------------------------------- Step 0


def verdict(
    preflight: dict[str, Any],
    keys_listing: dict[str, Any] | None,
    key_listing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Step 0: the preflight blockers, then whether the fingerprint is in KEYS and under which UID.

    Not in KEYS → `proceed`. In KEYS and any UID the keyserver reports is one
    of that key's UIDs in KEYS → `noop` (Golden rule 3: the fingerprint is
    there for a UID the keyserver still reports). UIDs are compared as sets,
    never by position: keyservers strip unverified UIDs and order the rest
    as they like. In KEYS under none of the keyserver's UIDs → `blocked`, the
    Golden rule 4 hand-off. In KEYS but the keyserver has no key or no UID for
    it → `blocked`: the UIDs cannot be compared. Until an input it needs is
    given, `verdict` is null and `pending` names it.
    """
    values = preflight.get("values") or {}
    fingerprint: str | None = None
    fingerprint_error: str | None = None
    if values.get("fingerprint"):
        try:
            fingerprint = normalise_fpr(str(values["fingerprint"]))
        except InputError as exc:
            fingerprint_error = str(exc)
    out: dict[str, Any] = {
        "verdict": None,
        "blockers": [str(b) for b in preflight.get("blockers") or []],
        "noop_reason": None,
        "fingerprint": fingerprint,
        "keys_file_url": values.get("keys_file_url"),
        "keyserver": values.get("keyserver"),
        "pending": [],
        "read": [],
    }
    if fingerprint_error:
        out["blockers"].append(fingerprint_error)
    if out["blockers"]:
        out["verdict"] = "blocked"
        return out
    if keys_listing is None:
        out["pending"].append("--keys-listing: `release-verify list-keys --file <KEYS>` output")
        return out
    keys = listed_keys(keys_listing, "--keys-listing")
    if not keys:
        out["blockers"].append(
            f"the KEYS file fetched from {out['keys_file_url']} lists no public key: "
            "check keys_file_url and that the saved file is the KEYS file, not an error page"
        )
        out["verdict"] = "blocked"
        return out
    assert fingerprint is not None  # the preflight blocks without one
    in_keys = find_key(keys, fingerprint, subkeys=True)
    if in_keys is None:
        out["verdict"] = "proceed"
        return out
    if key_listing is None:
        out["pending"].append(
            "--key-listing: the fingerprint is in KEYS; `release-verify list-keys --file <fetched.asc>` output "
            "for the key fetched from the keyserver"
        )
        return out
    keys_uids = [_one_line(u) for u in in_keys.get("uids") or []]
    keys_uid = keys_uids[0] if keys_uids else "<no user ID>"
    served = find_key(listed_keys(key_listing, "--key-listing"), fingerprint, subkeys=True)
    served_uids = [_one_line(u) for u in (served or {}).get("uids") or []]
    out["read"] = ["outcomes/key-rolled.md"]
    out["verdict"] = "blocked"
    if not served_uids:
        what = "no key" if served is None else "no user ID"
        out["blockers"].append(
            f"fingerprint {fingerprint} is already in KEYS for uid {keys_uid!r} but the keyserver "
            f"{out['keyserver']} returned {what} for it, so the UIDs cannot be compared; "
            "the RM uploads the public key (and verifies its email address there), then re-runs"
        )
        return out
    shared = [u for u in served_uids if u in keys_uids]
    if shared:
        out["verdict"] = "noop"
        out["noop_reason"] = f"fingerprint {fingerprint} already present in KEYS for uid: {shared[0]}"
        out["read"] = ["outcomes/noop.md"]
        return out
    reported = "uid " + repr(served_uids[0]) if len(served_uids) == 1 else f"uids {served_uids!r}"
    out["blockers"].append(
        f"fingerprint {fingerprint} is already in KEYS for uid {keys_uid!r} but the keyserver reports "
        f"{reported}; the RM must decide whether to append the updated key block or replace the "
        "existing one, then update rm_key_fingerprint if the key itself changed"
    )
    return out


# --------------------------------------------------------------------------- Step 2


def detect_backend(keys_url: str, dist_backend: str | None) -> str:
    """`dist.apache.org` → svnpubsub (atr when the dist backend is atr), `github.com` → git, else generic."""
    host = (urlparse(keys_url).hostname or "").lower()
    if host == "dist.apache.org":
        return "atr" if dist_backend == "atr" else "svnpubsub"
    if host in ("github.com", "www.github.com", "raw.githubusercontent.com"):
        return "git"
    return "generic"


def public_block(text: str) -> str:
    """The one armoured public key block in the fetched file; private-key material is refused."""
    if PRIVATE_MARKER in text:
        raise RenderError("the fetched key file contains private-key material; refusing (Golden rule 1)")
    blocks = PUBLIC_BLOCK.findall(text)
    if len(blocks) != 1:
        raise RenderError(
            f"the fetched key file holds {len(blocks)} armoured public key blocks; expected exactly one "
            "(fetch the key armoured, e.g. https://<keyserver>/vks/v1/by-fingerprint/<fingerprint>)"
        )
    return str(blocks[0]).replace("\r\n", "\n")


def _github(keys_url: str, keys_branch: str | None = None) -> tuple[str, str, str, str, str | None]:
    """`https://github.com/<owner>/<repo>/blob/<branch>/<path>/KEYS` → (owner, repo, branch, path, warning).

    `blob/`, `raw/` and `raw.githubusercontent.com/<owner>/<repo>/[refs/heads/]…`
    are read alike. The branch is the first segment after them and the path the
    rest, so KEYS may sit in a sub-directory (`dist/KEYS`). A branch holding `/`
    (`release/1.x`) cannot be told from the URL: `keys_file_branch` names it, and
    the URL must then start with it. Without `keys_file_branch` and with a path in
    a sub-directory, the reading is stated as a warning. The file must be named
    `KEYS`; anything else is refused.
    """
    parsed = urlparse(keys_url)
    parts = [p for p in parsed.path.split("/") if p]
    host = (parsed.hostname or "").lower()
    shape = "https://github.com/<owner>/<repo>/blob/<branch>/[<dir>/]KEYS"
    if host in ("github.com", "www.github.com") and len(parts) == 2 and not keys_branch:
        return parts[0], parts[1].removesuffix(".git"), "main", "KEYS", None
    rest: list[str] | None = None
    if host == "raw.githubusercontent.com" and len(parts) >= 3:
        rest = parts[2:]
        if rest[:2] == ["refs", "heads"]:
            rest = rest[2:]
    elif len(parts) >= 4 and parts[2] in ("blob", "raw"):
        rest = parts[3:]
    if rest is None:
        raise RenderError(
            f"cannot read the repository, branch and KEYS path from keys_file_url {keys_url!r}: expected {shape}"
        )
    if not rest or rest[-1] != "KEYS":
        raise RenderError(
            f"keys_file_url {keys_url!r} does not name a file called KEYS (last segment "
            f"{(rest or [''])[-1]!r}): expected {shape}"
        )
    owner, repo = parts[0], parts[1].removesuffix(".git")
    warning = None
    if keys_branch:
        want = [b for b in keys_branch.strip().split("/") if b]
        if rest[: len(want)] != want or len(rest) == len(want):
            raise RenderError(
                f"keys_file_branch {keys_branch!r} does not match keys_file_url {keys_url!r}: the URL's segments "
                f"after blob/ ({'/'.join(rest[:-1]) or '<none>'} before KEYS) must start with the branch; "
                "fix one of them"
            )
        branch, path = "/".join(want), "/".join(rest[len(want) :])
    else:
        if len(rest) < 2:
            raise RenderError(f"keys_file_url {keys_url!r} names no branch before KEYS: expected {shape}")
        branch, path = rest[0], "/".join(rest[1:])
        if len(rest) > 2:
            warning = (
                f"keys_file_url is read as branch {branch!r} and file {path!r}; if the branch itself contains "
                "'/' (e.g. release/1.x), set keys_file_branch in release-management-config.md"
            )
    return owner, repo, branch, path, warning


def _svn(keys_url: str, workdir: str, message: str) -> tuple[str, str]:
    derived = keys_dir(keys_url)
    if derived["error"]:
        raise RenderError(f"{derived['error']}; fix keys_file_url, no command is emitted against it")
    directory = str(derived["svn_keys_dir_url"])
    keys = f"{workdir}/KEYS"
    lines = [
        "# 1. Check out only the KEYS-file directory (release_dist_backend=svnpubsub)",
        f"svn checkout {w(directory)} {w(workdir)} --depth immediates",
        "",
        f"# 2. Append the key block below to {keys}",
        "",
        "# 3. Commit (release_dist_backend=svnpubsub)",
        f"svn commit {w(keys)} -m {dq(message)}",
    ]
    return "\n".join(lines), directory


def _git(
    keys_url: str,
    workdir: str,
    message: str,
    title: str,
    fingerprint: str,
    warnings: list[str],
    keys_branch: str | None = None,
) -> str:
    owner, repo, branch, path, warning = _github(keys_url, keys_branch)
    if warning:
        warnings.append(warning)
    work_branch = f"keys-sync-{fingerprint[-16:].lower()}"
    lines = [
        "# 1. Clone the repository holding KEYS (push to your fork instead if you lack write access)",
        f"git clone {w(f'https://github.com/{owner}/{repo}.git')} {w(workdir)}",
        f"cd {w(workdir)}",
        f"git checkout -b {w(work_branch)} {w('origin/' + branch)}",
        "",
        f"# 2. Append the key block below to {path}",
        "",
        "# 3. Commit, push and open the PR for review",
        f"git add {w(path)}",
        f"git commit -m {dq(message)}",
        f"git push origin {w(work_branch)}",
        f"gh pr create --web --repo {w(f'{owner}/{repo}')} --base {w(branch)} --title {dq(title)}",
    ]
    return "\n".join(lines)


def _generic(keys_url: str, message: str) -> str:
    return "\n".join(
        [
            f"# keys_file_url {_one_line(keys_url)} is neither a dist.apache.org nor a github.com URL:",
            "# 1. Fetch the KEYS file with the project's own workflow for that location",
            "# 2. Append the key block below to it",
            "# 3. Publish the change under your own credentials, with the message:",
            f"#    {_one_line(message)}",
        ]
    )


def step2(
    preflight: dict[str, Any],
    loaded: dict[str, Any],
    step1: dict[str, Any],
    key_text: str,
    key_listing: dict[str, Any] | None,
    *,
    backend: str | None = None,
) -> dict[str, Any]:
    """Step 2: the KEYS block, the backend's command sequence and the keyserver reminder.

    `key_listing` is what `release-verify list-keys --file <fetched.asc>` printed for
    `key_text`, the same listing Step 1 checked: it must hold exactly one primary key,
    the one Step 1 judged, or nothing is emitted.
    """
    if step1.get("verdict") != "proceed":
        raise RenderError(
            "Step 1 did not proceed (key missing, below the strength floor or otherwise blocked): "
            "no KEYS block or command is emitted (Hard rules)"
        )
    values = preflight.get("values") or {}
    config = loaded.get("config") or {}
    keys_url = str(values.get("keys_file_url") or config.get("keys_file_url") or "")
    keyserver = str(values.get("keyserver") or config.get("keyserver") or "keys.openpgp.org")
    raw_fpr = str(step1.get("fingerprint") or values.get("fingerprint") or "")
    if not raw_fpr or not keys_url:
        raise RenderError("the fingerprint or keys_file_url is unresolved: re-run Step 0")
    try:
        fingerprint = normalise_fpr(raw_fpr)
        listed = listed_keys(key_listing, "--key-listing")
        listed_fprs = [normalise_fpr(str(k.get("fingerprint") or "")) for k in listed]
    except InputError as exc:
        raise RenderError(f"{exc}; re-run `release-verify list-keys` on the fetched key file") from exc
    if listed_fprs != [fingerprint]:
        raise RenderError(
            f"the fetched key file lists {len(listed_fprs)} primary key(s) "
            f"({', '.join(listed_fprs) or 'none'}); expected exactly the Step 1 key {fingerprint}: "
            "re-fetch only that key, re-list it and re-run Step 1"
        )
    uid = _one_line(step1.get("uid") or "")
    if not uid:
        raise RenderError(
            "the fetched key carries no user ID, so the KEYS entry cannot name its owner: "
            f"verify the key's email address on {keyserver}, re-fetch it and re-run Step 1"
        )
    chosen = backend or detect_backend(keys_url, config.get("release_dist_backend"))
    if chosen not in BACKENDS:
        raise RenderError(f"unknown KEYS backend {chosen!r}: one of {', '.join(BACKENDS)}")
    warnings: list[str] = []
    name = str(config.get("project_dist_name") or "")
    if not name:
        warnings.append("project_dist_name is unset: the working directory carries <project-dist-name>")
        name = "<project-dist-name>"
    workdir = f"/tmp/{name}-keys"
    message = f"Add {uid} to KEYS (fingerprint: {fingerprint})"
    svn_dir = None
    if chosen in ("svnpubsub", "atr"):
        commands, svn_dir = _svn(keys_url, workdir, message)
    elif chosen == "git":
        keys_branch = values.get("keys_file_branch") or config.get("keys_file_branch")
        commands = _git(
            keys_url,
            workdir,
            message,
            f"Add {uid} to KEYS",
            fingerprint,
            warnings,
            str(keys_branch or "") or None,
        )
    else:
        commands = _generic(keys_url, message)
    block = f"# {uid}\n{public_block(key_text)}"
    reminder = (
        f"Upload the public key to https://{keyserver}/upload (or the keyserver's documented upload endpoint) "
        "before the vote opens, so voters and future verifiers can fetch it."
    )
    note = step1.get("strength_note")
    if note and "expir" in str(note):
        reminder += f" Expiry advisory: {_one_line(note)}."
    return {
        "keys_block_to_append": block,
        "svn_command_sequence": commands,
        "keyserver_upload_reminder": reminder,
        "proposed": True,
        "backend": chosen,
        "atr_offer": chosen == "atr",
        "svn_keys_dir_url": svn_dir,
        "read": READ[chosen],
        "warnings": warnings,
    }


__all__ = ["InputError", "RenderError", "detect_backend", "public_block", "step2", "verdict"]
