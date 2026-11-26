#
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
"""
Batches of private-tracker writes: one checked manifest, one confirmation.

``vetted-op-read --caller <name> batch-check <manifest.json>``
    checks a manifest against the approved policy and prints its summary and
    digest; runs nothing (allowlisted, like every read).
``vetted-op-tracker-batch --caller <name> --expect <digest> <manifest.json>``
    checks the same manifest again and runs every entry in order, stopping at
    the first failure. Kept on ``ask``; runs a policy set to ``batch`` or ``none``.
``vetted-op-tracker-batch-unprompted …`` (same arguments)
    the same, but refuses unless the selected policy sets ``none``. It is the
    only batch entry point an adopter may ``allow``: whichever approved policy
    the caller selects (``--policy-from`` or ``cd``), an unprompted run can
    never act on a policy whose adopter asked for a prompt per batch.

A manifest names operations and their positional parameters, exactly as they
would be passed to ``vetted-op`` one call at a time::

    {"version": 1,
     "ops": [{"op": "issue-add-label", "params": ["12", "needs triage"]},
             {"op": "rollup-append", "params": ["12", "import", "/ws/rollup-12.md"]}]}

Nothing in a manifest widens what a single call could do. Every entry passes
the same parameter validation and the same builder as one ``vetted-op`` call,
and on top of that:

- the operation must be one of `BATCHABLE`, the writes whose only destination
  is the private tracker or its project board; anything public or outbound
  (a public repository, an advisory, a CVE record, an email) is refused by name
  and keeps its own confirmation;
- the built command must address the policy's tracker (or board), checked on
  the argv itself, not only on the operation's name;
- the caller must be granted every operation in the manifest;
- the approved policy must turn batching on (``[approval]
  private_tracker_writes = "batch"`` or ``"none"``);
- on GitHub, the tracker repository must report itself private, and the board,
  when a board operation is in the manifest, must report itself not public.

All of that happens before the first write: one invalid entry refuses the whole
batch with nothing run. The digest covers the policy (its bytes' hash, tracker,
backend, board and resolved workspace), the manifest, every body and title file
it names, and every entry's built command; the run refuses a digest that does
not match, so the confirmation the user gives for ``--expect <digest>`` is a
confirmation of exactly what ``batch-check`` summarised, against the same
destination, not of a path whose content (or whose policy) can change.

A failed entry's outcome is unknown (the write may have landed before the error
was reported); the entries after it did not run. Body and title files are kept
until every entry has succeeded, so a recovery manifest still validates; the
manifest itself is removed after any run, so it cannot be blindly rerun.

Where the prompt comes from is the harness, not this module: one command is one
permission prompt under an ``ask`` rule, and no prompt under an ``allow`` rule.
The batch entry points are console scripts of their own so that each can have a
rule of its own: ``vetted-op-tracker-batch`` always ``ask``, and only
``vetted-op-tracker-batch-unprompted``, which refuses any policy but ``none``,
ever ``allow`` (see the design note
docs/designs/2026-11-26-vetted-ops-batch-tracker-writes.md).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from . import ops as ops_mod
from . import procedures, tracker_backends
from .config import Config, ConfigError, load
from .git_ops import check_policy_from_upstream, policy_from_checkout
from .safe_read import unlink_regular_file

EXIT_OK = 0
EXIT_POLICY = 3


@dataclass(frozen=True)
class SingleCall:
    """The single-call machinery a batch reuses, handed in by `cli`.

    The dependency runs one way: `cli` imports this module and passes its own
    parameter validation, builder, dispatcher and file consumer here, so every
    batch entry goes through exactly the code one `vetted-op` call does, and
    this module imports nothing from `cli`.
    """

    validate: Callable[[ops_mod.Op, list[str], Config], tuple[dict[str, str], bytes | None]]
    build: Callable[[ops_mod.Op, dict[str, str], Config], object]
    dispatch: Callable[[ops_mod.Op, object, dict[str, str], bytes | None, argparse.Namespace, Config], int]
    consume: Callable[[ops_mod.Op, list[str], Config], None]
    reject_repeated_caller: Callable[[Sequence[str]], None]


MANIFEST_VERSION = 1
#: Enough for a scan import's second phase (labels, rollups and board moves for
#: a few dozen findings); a longer list is split, so each summary stays readable.
MAX_ENTRIES = 200
#: The digest prefix the summary prints and ``--expect`` takes.
DIGEST_CHARS = 16

#: The private-tracker writes a batch may contain. Each builds a `gh` call on
#: ``--repo <tracker>`` / ``repos/<tracker>/…``, a procedure whose runner is
#: pinned to the tracker, a mutation on the policy's project board, or (on a
#: non-GitHub tracker) the backend's own call. Everything else — writes to the
#: public upstream repository, advisory comments, CVE-tool calls, the local
#: tracker's push — is absent on purpose and keeps one confirmation per call.
BATCHABLE = frozenset(
    {
        "issue-create",
        "issue-create-labeled",
        "issue-add-label",
        "issue-remove-label",
        "issue-set-milestone",
        "issue-add-assignee",
        "issue-remove-assignee",
        "issue-comment",
        "issue-edit-body",
        "issue-edit-title",
        "issue-close",
        "issue-reopen",
        "comment-update",
        "milestone-create",
        "milestone-close",
        "rollup-append",
        "rollup-amend-latest",
        "rollup-fold",
        "body-field-set",
        "board-add-item",
        "board-set-status",
        "board-archive-item",
    }
)
BOARD_OPS = frozenset({"board-add-item", "board-set-status", "board-archive-item"})

_BOARD_PUBLIC_QUERY = "query($id:ID!){node(id:$id){... on ProjectV2{public}}}"


class BatchRefused(RuntimeError):
    """The batch as a whole is refused; nothing has run."""


@dataclass(frozen=True)
class Entry:
    """One checked manifest entry, ready to run."""

    index: int
    op: ops_mod.Op
    raw: list[str]
    params: dict[str, str]
    body: bytes | None
    command: object


@dataclass(frozen=True)
class Batch:
    """A checked manifest: its entries in order and the digest that binds them."""

    manifest: Path
    entries: tuple[Entry, ...]
    digest: str

    @property
    def short(self) -> str:
        return self.digest[:DIGEST_CHARS]


def _parse(data: bytes) -> list[tuple[str, list[str]]]:
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BatchRefused(f"the manifest is not UTF-8 JSON: {exc}") from None
    if not isinstance(doc, dict) or set(doc) != {"version", "ops"}:
        raise BatchRefused("the manifest must be an object with exactly the keys 'version' and 'ops'")
    if doc["version"] != MANIFEST_VERSION:
        raise BatchRefused(f"manifest version must be {MANIFEST_VERSION}, got {doc['version']!r}")
    entries = doc["ops"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise BatchRefused(f"'ops' must be a list of 1 to {MAX_ENTRIES} entries")
    parsed: list[tuple[str, list[str]]] = []
    for i, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or set(entry) != {"op", "params"}:
            raise BatchRefused(f"entry {i}: must be an object with exactly the keys 'op' and 'params'")
        name, params = entry["op"], entry["params"]
        if not isinstance(name, str) or not isinstance(params, list):
            raise BatchRefused(f"entry {i}: 'op' must be a string and 'params' a list")
        if not all(isinstance(p, str) for p in params):
            raise BatchRefused(f"entry {i}: every parameter must be a string")
        parsed.append((name, list(params)))
    return parsed


def _check_target(op: ops_mod.Op, command: object, config: Config) -> None:
    """Refuse a built command that does not address the private tracker or its board."""
    if isinstance(command, tracker_backends.BackendCall):
        return  # a non-GitHub tracker: the backend call reaches nothing else
    if op.backend == "procedure":
        if not isinstance(command, procedures.Plan) or command.tracker != config.tracker_repo:
            raise BatchRefused(f"{op.name!r} did not plan against the tracker")
        return
    if op.backend != "gh" or not isinstance(command, list) or command[:1] != ["gh"] or len(command) < 3:
        raise BatchRefused(f"{op.name!r} did not build a gh call")
    tracker = config.tracker_repo
    if op.name in BOARD_OPS:
        board = config.as_mapping().get("board_project_id")
        if command[1:3] != ["api", "graphql"] or not board or f"project={board}" not in command:
            raise BatchRefused(f"{op.name!r} does not address the policy's project board")
        return
    if command[1] == "issue":
        repos = [command[i + 1] for i, a in enumerate(command[:-1]) if a in ("--repo", "-R")]
        if repos != [tracker]:
            raise BatchRefused(f"{op.name!r} does not address the tracker {tracker!r}")
        return
    if command[1] == "api":
        paths = [a for a in command[2:] if a.startswith("repos/")]
        if not paths or not all(p.startswith(f"repos/{tracker}/") for p in paths):
            raise BatchRefused(f"{op.name!r} does not address the tracker {tracker!r}")
        return
    raise BatchRefused(f"{op.name!r} built a gh {command[1]!r} call, not a tracker write")


def _destination(config: Config) -> bytes:
    """The policy identity and everything in it that decides where a batch writes."""
    backend = config.tracker_backend
    return json.dumps(
        {
            "policy_sha256": config.policy_sha256,
            "tracker_repo": config.tracker_repo,
            "tracker_backend": dict(sorted(vars(backend).items())) if backend is not None else "github",
            "board_project_id": config.as_mapping().get("board_project_id"),
            "workspace": str(config.workspace),
            "private_tracker_writes": config.private_tracker_writes,
        },
        sort_keys=True,
        default=str,
    ).encode("utf-8")


def _built(command: object) -> bytes:
    """A canonical form of one entry's built command, for the digest."""
    if isinstance(command, tracker_backends.BackendCall):
        shape: object = {"backend": command.op, "argv": command.argv}
    elif isinstance(command, procedures.Plan):
        shape = {
            "procedure": command.op,
            "tracker": command.tracker,
            "params": dict(sorted(command.params.items())),
        }
    else:
        shape = {"argv": command}
    return json.dumps(shape, sort_keys=True, default=str).encode("utf-8")


def check(config: Config, caller: str, manifest: str, single: SingleCall) -> Batch:
    """Check every entry of the manifest at ``manifest``; refuse the whole batch on any fault."""
    if config.private_tracker_writes == "each":
        raise BatchRefused(
            "batching is off: the policy sets [approval] private_tracker_writes = 'each' (the default), "
            "so every tracker write keeps its own confirmation; run each one through vetted-op-tracker "
            "or vetted-op, or ask the user to set it to 'batch' and re-approve the policy"
        )
    if config.tracker_repo is None and config.tracker_backend is None:
        raise BatchRefused("the policy declares no tracker, so there is nothing a batch may write to")
    if not manifest.endswith(".json"):
        raise BatchRefused(f"the manifest must be a .json file: {manifest!r}")
    try:
        data = ops_mod.read_body(manifest, workspace=config.workspace)
    except ops_mod.ParamError as exc:
        raise BatchRefused(f"manifest: {exc}") from None
    items = _parse(data)
    permitted = config.ops_for(caller)

    digest = hashlib.sha256(b"vetted-ops-batch/2\0")

    def feed(part: bytes) -> None:
        digest.update(len(part).to_bytes(8, "big") + part)

    # The destination first: the same manifest checked under one approved
    # policy and run under another (another tracker, board or workspace) does
    # not match.
    feed(_destination(config))
    feed(data)
    entries: list[Entry] = []
    for index, (name, values) in enumerate(items, 1):
        try:
            op = ops_mod.resolve(name)
            if name not in BATCHABLE or not op.writes:
                raise BatchRefused(
                    f"{name!r} is not a private-tracker write, so it cannot be batched; "
                    "run it on its own, where it keeps its own confirmation"
                )
            if name not in permitted:
                raise BatchRefused(f"caller {caller!r} is not permitted to run {name!r}")
            params, body = single.validate(op, values, config)
            command = single.build(op, params, config)
            _check_target(op, command, config)
        except (BatchRefused, ops_mod.ParamError, ConfigError) as exc:
            raise BatchRefused(f"entry {index} ({name}): {exc}") from None
        for part in [body or b"", *(params[t].encode("utf-8") for t in op.title_files)]:
            feed(part)
        # What runs is what was summarised: the built command itself.
        feed(_built(command))
        entries.append(Entry(index, op, list(values), params, body, command))
    return Batch(Path(manifest), tuple(entries), digest.hexdigest())


def confirm_private(config: Config, batch: Batch, exec_fn: procedures.ExecFn | None = None) -> str:
    """Refuse unless the tracker (and a board the batch touches) is private; return a one-line note.

    On GitHub this asks the forge rather than trusting the policy: a tracker
    pointed at a public repository by mistake would otherwise publish a batch of
    pre-disclosure text in one confirmation. A non-GitHub tracker is private by
    the security-tracker contract (a Jira security level, a local folder).
    """
    if config.tracker_backend is not None:
        return f"{config.tracker_backend.platform} tracker (private by contract)"
    run = exec_fn or procedures.subprocess_exec
    tracker = config.tracker_repo
    code, out, _ = run(["gh", "api", f"repos/{tracker}", "--jq", ".private"], None)
    if code != 0 or out.strip() != b"true":
        raise BatchRefused(
            f"could not confirm that {tracker} is a private repository; a batch writes only to a private tracker"
        )
    note = f"{tracker} (private: confirmed)"
    if any(e.op.name in BOARD_OPS for e in batch.entries):
        board = str(config.as_mapping().get("board_project_id"))
        code, out, _ = run(
            [
                "gh",
                "api",
                "graphql",
                "-F",
                f"id={board}",
                "-f",
                f"query={_BOARD_PUBLIC_QUERY}",
                "--jq",
                ".data.node.public",
            ],
            None,
        )
        if code != 0 or out.strip() != b"false":
            raise BatchRefused("could not confirm that the project board is not public")
        note += ", board not public: confirmed"
    return note


def _shown(entry: Entry) -> str:
    parts = []
    for name, raw in zip(entry.op.params, entry.raw, strict=True):
        if name in entry.op.body_files:
            parts.append(f"{name}=<file, {len(entry.body or b'')} bytes>")
        elif name in entry.op.title_files:
            parts.append(f"{name}=<file, {len(entry.params[name])} chars>")
        else:
            parts.append(f"{name}={raw}")
    return f"{entry.op.name}  " + "  ".join(parts)


def summary(batch: Batch, caller: str, where: str) -> str:
    """The text the user approves: every entry, bodies by size, and the digest."""
    lines = [f"batch {batch.short}: {len(batch.entries)} private-tracker write(s) on {where}, as {caller}"]
    lines += [f"  {e.index:>3}. {_shown(e)}" for e in batch.entries]
    return "\n".join(lines)


def run(batch: Batch, config: Config, single: SingleCall, out: TextIO | None = None) -> int:
    """Run the entries in order; stop at the first that fails and report what ran.

    A failing entry's outcome is **unknown**: a write can land and still exit
    non-zero (a timeout, a dropped connection, a procedure whose write went
    through before a later read failed). The report says so, and the caller
    reads the tracker before proposing that entry again. Body and title files
    are consumed only once every entry succeeded, so after a stop each one is
    still there for the recovery manifest.
    """
    stream = out or sys.stdout
    total = len(batch.entries)
    ns = argparse.Namespace(dry_run=False, save=None)
    for entry in batch.entries:
        print(f"[{entry.index}/{total}] {_shown(entry)}", file=stream, flush=True)
        try:
            code = single.dispatch(entry.op, entry.command, entry.params, entry.body, ns, config)
        except ops_mod.ParamError as exc:
            print(f"vetted-op: refused: {exc}", file=sys.stderr)
            code = EXIT_POLICY
        if code != EXIT_OK:
            report = {
                "batch": "stopped",
                "digest": batch.short,
                "succeeded": [e.index for e in batch.entries[: entry.index - 1]],
                "unknown": entry.index,
                "op": entry.op.name,
                "not_run": [e.index for e in batch.entries[entry.index :]],
                "total": total,
            }
            print(json.dumps(report), file=stream, flush=True)
            print(
                f"vetted-op: entry {entry.index} ({entry.op.name}) failed and its outcome is unknown; "
                "read the tracker to see whether it took effect before proposing it again",
                file=sys.stderr,
            )
            # Every body and title file stays for the recovery manifest. The
            # manifest itself goes: rerunning it would repeat the entries that
            # succeeded (a second set of trackers, say), and the report above
            # already names every entry by its index.
            _remove_manifest(batch, config)
            return code
    # Every entry succeeded: only now are its files, and the manifest, spent.
    for entry in batch.entries:
        single.consume(entry.op, entry.raw, config)
    _remove_manifest(batch, config)
    print(json.dumps({"batch": "done", "digest": batch.short, "ran": total, "total": total}), file=stream)
    return EXIT_OK


def _remove_manifest(batch: Batch, config: Config) -> None:
    with contextlib.suppress(OSError, ops_mod.ParamError):
        unlink_regular_file(batch.manifest, ops_mod.checked_workspace(config.workspace))


def load_policy(policy_from: Path | None) -> Config:
    """The approved policy a batch acts on, discovered as the single-call dispatchers find it.

    Without ``--policy-from``, from the working directory. With it, under the same
    confinement as `vetted-op`: the directory must be a checkout the operator lists
    in their own operator-git.toml (checked as text before the file system is
    touched), and the approved policy found there must list that checkout for its
    upstream.
    """
    if policy_from is None:
        return load(None, approved_only=True)
    base = policy_from_checkout(policy_from)
    config = load(None, cwd=base, approved_only=True)
    check_policy_from_upstream(config, base)
    return config


def check_main(caller: str, manifest: str, policy_from: Path | None, single: SingleCall) -> int:
    """``vetted-op-read batch-check``: check and summarise, run nothing."""
    try:
        config = load_policy(policy_from)
        batch = check(config, caller, manifest, single)
        where = confirm_private(config, batch)
    except (BatchRefused, ConfigError) as exc:
        print(f"vetted-op: refused: {exc}", file=sys.stderr)
        return EXIT_POLICY
    print(summary(batch, caller, where))
    print(json.dumps({"digest": batch.short, "entries": len(batch.entries), "approved": True}))
    return EXIT_OK


#: The batch entry point an adopter may put in `allow`; it runs only a `none` policy.
UNPROMPTED_PROG = "vetted-op-tracker-batch-unprompted"


def main(argv: Sequence[str] | None, *, single: SingleCall, unprompted: bool = False) -> int:
    """The body of the `vetted-op-tracker-batch` console script (and, with ``unprompted``, its allowable twin).

    The console scripts themselves are `cli.main_batch` and `cli.main_batch_unprompted`,
    which pass `cli`'s single-call machinery in as ``single``.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    prog = UNPROMPTED_PROG if unprompted else "vetted-op-tracker-batch"
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Run a checked manifest of private-tracker writes, in order, without a prompt; "
            "only for a policy that sets [approval] private_tracker_writes = 'none'."
            if unprompted
            else "Run a checked manifest of private-tracker writes, in order, under one confirmation."
        ),
    )
    parser.add_argument("--caller", required=True, help="the skill invoking this batch")
    parser.add_argument(
        "--expect", required=True, help="the digest `vetted-op-read batch-check` printed for this manifest"
    )
    parser.add_argument(
        "--policy-from",
        metavar="DIR",
        type=Path,
        default=None,
        help="discover the approved policy from this checkout, listed in your operator-git.toml, "
        "instead of the working directory",
    )
    parser.add_argument("manifest", help="the manifest, a .json file in the workspace")
    args = parser.parse_args(raw)
    try:
        single.reject_repeated_caller(raw)
        # argparse keeps the last of a repeated option; like `vetted-op`, refuse it.
        if sum(1 for a in raw if a == "--policy-from" or a.startswith("--policy-from=")) > 1:
            raise BatchRefused("--policy-from given more than once")
        config = load_policy(args.policy_from)
        # Ahead of everything else: this entry point may run with no prompt at
        # all, so whichever approved policy the caller selected (by --policy-from
        # or cd) must be one whose adopter chose that. A `batch` policy asked for
        # a prompt per batch, and that prompt lives on the other entry point.
        if unprompted and config.private_tracker_writes != "none":
            raise BatchRefused(
                f"{prog} runs only a policy that sets [approval] private_tracker_writes = 'none'; "
                f"this one sets {config.private_tracker_writes!r}, so run the batch through "
                "vetted-op-tracker-batch, which keeps its confirmation"
            )
        batch = check(config, args.caller, args.manifest, single)
        if args.expect not in (batch.short, batch.digest):
            raise BatchRefused(
                "the manifest, a file it names, or the policy it acts under changed since it was checked "
                f"(digest {batch.short}, "
                f"expected {args.expect}); run batch-check again and show the user the new summary"
            )
        where = confirm_private(config, batch)
    except (BatchRefused, ConfigError, ops_mod.ParamError) as exc:
        print(f"vetted-op: refused: {exc}", file=sys.stderr)
        return EXIT_POLICY
    print(summary(batch, args.caller, where), flush=True)
    return run(batch, config, single)


__all__ = [
    "BATCHABLE",
    "Batch",
    "BatchRefused",
    "SingleCall",
    "check",
    "confirm_private",
    "main",
    "run",
    "summary",
]
