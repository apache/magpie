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
"""Steps 0 and 2: which PR, and which scope its changed files belong to.

- `parse_ref` resolves the four input forms to a PR number and refuses a PR
  in any repository other than `<upstream>`.
- `detect` strips test files (any path with a `tests/` segment), maps each
  remaining file to the scope label whose `path_prefix` regex matches it
  (`scope_detection.labels` in project.md), and stops on a PR whose
  production files span more than one scope. Several sub-packages of one
  scope are not mixed: they are listed in `sub_packages`, one *Affected
  versions* line each.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

MIXED = "mixed_scope_blocker"
_TEST = re.compile(r"(?:^|/)tests/")
_SUBSTITUTION = re.compile(r"<[^<>]+>")
# A sub-package name substituted into `packageName`: a plain identifier, never a path or a template.
_SUB_PACKAGE = re.compile(r"^[a-z0-9][a-z0-9._-]*$", re.IGNORECASE)
_URL = re.compile(r"^https?://github\.com/([^/\s]+/[^/\s#?]+)/pull/(\d+)(?:[/?#].*)?$", re.IGNORECASE)
_SHORT = re.compile(r"^([A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+)?#(\d+)$")


def parse_ref(ref: str, upstream: str) -> dict[str, Any]:
    """`{ok, number, repo}`, or `{ok: false, refused}` for another repository or an unknown form."""
    text = ref.strip()
    repo: str | None = upstream
    number: str | None = None
    if text.isdigit():
        number = text
    elif match := _URL.match(text):
        repo, number = match.group(1), match.group(2)
    elif match := _SHORT.match(text):
        repo, number = match.group(1) or upstream, match.group(2)
    if number is None or int(number) <= 0:
        return {"ok": False, "refused": f"not a PR reference: {text!r}"}
    if str(repo).lower() != upstream.lower():
        return {
            "ok": False,
            "refused": f"PR is in {repo}, not {upstream}: the team only allocates CVEs for {upstream} PRs",
        }
    return {"ok": True, "number": int(number), "repo": upstream}


def _paths(files: object) -> list[str]:
    if isinstance(files, Mapping):
        files = files.get("files") or []
    if not isinstance(files, Sequence) or isinstance(files, str):
        raise ValueError("--files: expected a list of paths or `gh pr view --json files` output")
    return [str(f["path"] if isinstance(f, Mapping) else f) for f in files]


def _sub_package(match: re.Match[str], path: str, package_name: str) -> str | None:
    if match.groups() and match.group(1):
        return match.group(1)
    if not _SUBSTITUTION.search(package_name):
        return None
    segment = path[match.end() :].lstrip("/").split("/", 1)[0]
    return segment or None


def _substitute(template: str, name: str) -> str:
    """`template` with its first `<…>` replaced by `name`, literally (no backreferences)."""

    def literal(_match: re.Match[str]) -> str:
        return name

    return _SUBSTITUTION.sub(literal, template, count=1)


def detect(files: object, config: Mapping[str, Any]) -> dict[str, Any]:
    """The Step 2 result: `scope`, `stop`, `mixed_scopes`, `sub_packages` / `affected_providers`, the file lists."""
    paths = _paths(files)
    stripped = [p for p in paths if _TEST.search(p)]
    counted = [p for p in paths if not _TEST.search(p)]
    result: dict[str, Any] = {
        "scope": None,
        "stop": False,
        "mixed_scopes": [],
        "sub_packages": [],
        "packages": [],
        "files_counted": counted,
        "test_files_stripped": stripped,
        "unmatched": [],
        "matched": {},
    }
    if config.get("enabled") is False:
        result["scope"] = config.get("default_label")
        result["affected_providers"] = []
        return result
    labels = config.get("labels") or {}
    if not isinstance(labels, Mapping) or not labels:
        raise ValueError("--scope-config: no scope_detection.labels")
    compiled = {str(label): re.compile(str(spec.get("path_prefix") or "")) for label, spec in labels.items()}
    matched: dict[str, list[str]] = {}
    subs: list[str] = []
    for path in counted:
        hit = next(((label, rx.search(path)) for label, rx in compiled.items() if rx.search(path)), None)
        if hit is None:
            result["unmatched"].append(path)
            continue
        label, match = hit
        assert match is not None
        sub = _sub_package(match, path, str(labels[label].get("packageName") or ""))
        if sub is not None and (not _SUB_PACKAGE.match(sub) or ".." in sub):
            result["unmatched"].append(path)
            continue
        matched.setdefault(label, []).append(path)
        if sub and sub not in subs:
            subs.append(sub)
    result["matched"] = matched
    if len(matched) > 1:
        result.update(scope=MIXED, stop=True, mixed_scopes=list(matched))
    elif matched:
        scope = next(iter(matched))
        template = str(labels[scope].get("packageName") or "")
        result["scope"] = scope
        result["sub_packages"] = subs
        result["packages"] = (
            [_substitute(template, s) for s in subs] if subs else [template] if template else []
        )
    result["affected_providers"] = result["sub_packages"]
    return result
