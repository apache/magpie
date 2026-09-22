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

"""Resolve a project's setup state into findings, in two scopes.

The pre-flight has always mixed two questions.  **Project** scope asks
whether this checkout is set up at all — is there a lock, does the
snapshot match, is the machine at the project's floor — and its answer is
identical for every skill invoked in the same tree.  **Skill** scope asks
whether *this* skill's configuration still matches the build now
installed, and differs per skill.  Prose could not keep them apart
usefully, because the agent re-read the whole block on every invocation
either way.  Code can: the project answer is computed once and memoised
against the inputs it depends on, so the second and later skills in a
session pay for their own fingerprint comparison and nothing else.

Every rule here was prose in `tools/dev/preflight-block.md` first, and two
of them are the reason this is code rather than judgement:

* **Unknown is never absent.**  A plugin listing that could not be read is
  `None`, not `[]`.  Inside a sandboxed session the plugin cache is
  read-denied and `claude plugin list --json` prints `[]`, which reads
  exactly like "nothing installed"; acting on it would propose installing
  a project's entire floor on every sandboxed run.  The type system
  carries the distinction so a caller cannot collapse it by accident.
* **A dev build is a version like any other.**  See `version.py`.

Nothing here writes, proposes, or decides what to say.  It reports what is
true; the wording, the proposals and the prohibitions stay in the skill's
`preflight-detail.md`, which the agent reads only when a finding says to.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from .lockfile import Lock, MalformedLock, load
from .version import InvalidVersion, below

LOCAL_DIR = ".apache-magpie-local"
OVERRIDES_DIR = ".apache-magpie-overrides"
LOCK_NAME = ".apache-magpie.lock"
LOCAL_LOCK_NAME = ".apache-magpie.local.lock"
STAMP_NAME = "reconciled.json"
CACHE_NAME = ".preflight-cache.json"

TRUSTED_MARKETPLACE = "apache/magpie"
SNAPSHOT_METHODS = frozenset({"svn-zip", "git-tag", "git-branch"})
DEFAULT_VERIFY_INTERVAL_DAYS = 14
#: How long a memoised project verdict stays usable when the inputs it was
#: computed from have not changed.  Short enough that a plugin installed
#: mid-session is noticed on the next skill, long enough that a session
#: running six skills does not re-shell six times.
PROJECT_CACHE_TTL_SECONDS = 900


@dataclass(frozen=True)
class Finding:
    """One thing the agent has to act on, and where the rules for it live."""

    scope: str  # "project" | "skill" | "end-of-run"
    code: str
    section: str  # the `preflight-detail.md` section to read
    facts: dict[str, object] = field(default_factory=dict)


@dataclass
class Verdict:
    verdict: str  # "ok" | "action"
    findings: list[Finding] = field(default_factory=list)
    project_cached: bool = False

    def to_json(self) -> str:
        payload: dict[str, object] = {"verdict": self.verdict}
        if self.findings:
            payload["findings"] = [asdict(f) for f in self.findings]
        if self.project_cached:
            payload["project_cached"] = True
        return json.dumps(payload, indent=2, sort_keys=True)


# --- project scope ------------------------------------------------------------------


def _snapshot_findings(lock: Lock, root: Path) -> list[Finding]:
    local = root / LOCAL_LOCK_NAME
    if not local.exists():
        return [
            Finding(
                "project",
                "snapshot-never-fetched",
                "step-2",
                {"method": lock.method},
            )
        ]
    try:
        from .lockfile import parse as parse_lock

        local_lock = parse_lock(local.read_text(encoding="utf-8"))
    except MalformedLock as exc:
        return [Finding("project", "snapshot-unreadable", "step-2", {"error": str(exc)})]
    drift = {
        key: {"project": getattr(lock, key), "machine": getattr(local_lock, key)}
        for key in ("ref", "commit")
        if getattr(lock, key) is not None and getattr(lock, key) != getattr(local_lock, key)
    }
    if drift:
        return [Finding("project", "snapshot-drift", "step-2", {"differs": drift})]
    return []


def _floor_findings(lock: Lock, installed: dict[str, str] | None) -> list[Finding]:
    if lock.url and lock.url != TRUSTED_MARKETPLACE:
        return [Finding("project", "untrusted-marketplace", "step-3", {"url": lock.url})]
    if installed is None:
        # Unknown, never absent.  Say nothing and let the run continue: this
        # is the ordinary state of a sandboxed session, not a fault.
        return []
    missing = [name for name in lock.plugins if name not in installed]
    outdated = []
    for name in lock.plugins:
        current = installed.get(name)
        if current is None or lock.min_version is None:
            continue
        try:
            if below(current, lock.min_version):
                outdated.append({"plugin": name, "installed": current, "floor": lock.min_version})
        except InvalidVersion as exc:
            return [Finding("project", "version-unparsable", "step-3", {"error": str(exc)})]
    if not missing and not outdated:
        return []
    return [
        Finding(
            "project",
            "below-floor",
            "step-3",
            {"missing": missing, "outdated": outdated, "restart_required": True},
        )
    ]


def project_findings(root: Path, installed: dict[str, str] | None) -> list[Finding]:
    """Everything true of the checkout rather than of one skill."""
    lock = load(root / LOCK_NAME)
    if lock is None:
        # A supported end state, not a fault: the marketplace install
        # without adoption, or nothing at all.  Skill scope decides whether
        # anything is actually missing.
        return []
    if lock.method in SNAPSHOT_METHODS:
        return _snapshot_findings(lock, root)
    if lock.method == "marketplace":
        return _floor_findings(lock, installed)
    return [Finding("project", "unknown-method", "step-2", {"method": lock.method})]


# --- skill scope --------------------------------------------------------------------


def _read_stamp(root: Path) -> dict[str, object]:
    path = root / LOCAL_DIR / STAMP_NAME
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _resolves(root: Path, name: str) -> bool:
    return (root / LOCAL_DIR / name).exists() or (root / OVERRIDES_DIR / name).exists()


def configured_at_all(root: Path) -> bool:
    """Has anything ever been configured or adopted here?

    All three absent means there is nothing to reconcile, and the whole
    fingerprint comparison is skipped in silence.
    """
    return any((root / part).exists() for part in (LOCK_NAME, LOCAL_DIR, OVERRIDES_DIR))


def skill_findings(
    root: Path,
    skill: str,
    surface_hash: str | None,
    requires: list[str],
) -> list[Finding]:
    """This skill's fingerprint against the stamp, and its `requires_config`."""
    findings: list[Finding] = []
    missing = [name for name in requires if not _resolves(root, name)]
    if missing:
        findings.append(Finding("skill", "config-missing", "step-7", {"files": missing}))

    if not configured_at_all(root) or not surface_hash:
        # Nothing to reconcile, or a check that cannot read its own input:
        # say nothing rather than guessing.
        return findings

    lock = load(root / LOCK_NAME)
    stamp = _read_stamp(root)
    raw_local = stamp.get("skills")
    local_skills: dict[str, str] = (
        {str(k): str(v) for k, v in raw_local.items()} if isinstance(raw_local, dict) else {}
    )
    lock_skills: dict[str, str] = lock.reconciled.skills if lock and lock.reconciled else {}

    # The local store wins where both name this skill: `config` on one
    # machine and `adopt` on another is an expected transitional state.
    stamped = local_skills.get(skill) or lock_skills.get(skill)

    raw_ack = stamp.get("acknowledged")
    acknowledged: dict[str, object] = raw_ack if isinstance(raw_ack, dict) else {}
    ack_skills = acknowledged.get("skills")
    ack_for_skill = ack_skills.get(skill) if isinstance(ack_skills, dict) else None

    if stamped is None:
        has_any_stamp = bool(local_skills or lock_skills or stamp.get("version"))
        if not has_any_stamp and acknowledged.get("sweep") is None:
            # A sweep declined against the version the stamp itself records
            # stays declined until that version moves -- which is exactly
            # when new drift can have arrived.
            findings.append(Finding("skill", "sweep-never-run", "step-4", {"skill": skill}))
        return findings

    if stamped != surface_hash and ack_for_skill != surface_hash:
        # Shown once per hash: `acknowledged.skills[<name>]` equal to the
        # current fingerprint means this exact change was already put to the
        # user, and repeating it every invocation is how a useful nudge
        # becomes noise people learn to skip.
        findings.append(
            Finding(
                "skill",
                "fingerprint-moved",
                "step-4",
                {
                    "skill": skill,
                    "stamped": stamped,
                    "current": surface_hash,
                    # Which half moved decides which fix is proposed: an
                    # unresolved entry is a `config` problem, everything
                    # resolving means an anchor moved instead.
                    "cause": "requires_config" if missing else "anchors",
                    "in_both_stores": skill in local_skills and skill in lock_skills,
                },
            )
        )
    return findings


# --- end-of-run scope ---------------------------------------------------------------


def _parse_day(text: object) -> date | None:
    if not isinstance(text, str):
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def verify_findings(root: Path, interval_days: int, today: date | None = None) -> list[Finding]:
    """Whether the periodic `/magpie-setup verify` suggestion is due."""
    if interval_days <= 0:
        return []
    stamp = _read_stamp(root)
    lock = load(root / LOCK_NAME)
    candidates = [
        _parse_day(stamp.get("verified_at")),
        _parse_day(stamp.get("verify_suggested_at")),
    ]
    if not any(candidates):
        candidates.append(_parse_day(stamp.get("at")))
        if lock and lock.reconciled:
            candidates.append(_parse_day(lock.reconciled.at))
    known = [day for day in candidates if day is not None]
    if not known:
        return []
    age = ((today or date.today()) - max(known)).days
    if age < interval_days:
        return []
    return [
        Finding(
            "end-of-run",
            "verify-overdue",
            "step-10",
            {"days_since": age, "interval_days": interval_days},
        )
    ]


# --- memoising the project scope ----------------------------------------------------


def _cache_key(root: Path, installed: dict[str, str] | None) -> str:
    parts: list[str] = []
    for name in (LOCK_NAME, LOCAL_LOCK_NAME):
        path = root / name
        parts.append(
            f"{name}:{path.stat().st_mtime_ns}:{path.stat().st_size}" if path.exists() else f"{name}:-"
        )
    parts.append("installed:" + ("?" if installed is None else json.dumps(installed, sort_keys=True)))
    return "|".join(parts)


def cached_project_findings(
    root: Path,
    installed: dict[str, str] | None,
    *,
    now: float | None = None,
) -> tuple[list[Finding], bool]:
    """Project findings, reusing a recent verdict computed from the same inputs.

    Returns `(findings, was_cached)`.  The cache lives in the gitignored
    `.apache-magpie-local/`, is keyed on the lock files' identity and the
    plugin listing, and expires so that a plugin installed mid-session is
    picked up by the next skill rather than at the end of the day.  A
    project with no local directory is not cached at all — writing one
    would create the very state whose absence the skill scope reads as
    "never configured".
    """
    local_dir = root / LOCAL_DIR
    if not local_dir.is_dir():
        return project_findings(root, installed), False

    stamp_now = now if now is not None else time.time()
    key = _cache_key(root, installed)
    cache_path = local_dir / CACHE_NAME
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
        if (
            isinstance(cached, dict)
            and cached.get("key") == key
            and isinstance(cached.get("at"), (int, float))
            and stamp_now - float(cached["at"]) < PROJECT_CACHE_TTL_SECONDS
        ):
            entries = cached.get("findings")
            if isinstance(entries, list):
                return [Finding(**entry) for entry in entries], True

    findings = project_findings(root, installed)
    payload = {"key": key, "at": stamp_now, "findings": [asdict(f) for f in findings]}
    tmp = cache_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(cache_path)
    return findings, False
