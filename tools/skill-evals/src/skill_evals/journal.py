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
Append-only run journal for skill evals.

Every live ``--cli`` run of the eval runner appends one JSON record to
``evals/<skill>/runs.jsonl``: which skill, at which commit, with which
model and inputs, what the outcome was, and what it cost. The *Run
history* table in ``evals/<skill>/README.md`` is **generated from that
journal**, never edited by hand, so the table cannot drift from what was
actually run and every row can be traced back to the record that
produced it.

The journal is the evidence; the table is a view. Two rules keep the
evidence trustworthy:

* **Append only.** A record is never edited or removed. A wrong record
  is corrected by appending another one that says so in ``notes``.
  ``check --against <ref>`` fails when a committed journal is not a
  prefix of the working copy.
* **One record per run.** The runner writes the record; a human writes
  one only to import a pre-journal table (``import-readme``), and such a
  record is marked ``"legacy": true`` so a reader knows the per-run
  detail is not available for it.

Record shape (schema 1). Keys the runner always writes:

    schema        1
    skill         eval directory name, e.g. "issue-triage"
    date          YYYY-MM-DD (UTC)
    timestamp     ISO-8601 UTC instant the run finished
    ref           short commit SHA the run was made at
    branch        branch name, or "HEAD" when detached
    dirty         true when the working tree had uncommitted changes
    model         model name as the CLI uses it, or null when unknown
    model_source  where model came from: journal-model, cli-flag,
                  env:ANTHROPIC_MODEL, settings:<scope>, or null
    cli           the --cli command string
    grader_cli    the --grader-cli command string, or null under --exact
    path          the eval path argument, repo-relative
    tags          the --tag filters applied ([] when none)
    cases         number of cases run
    passed / failed / manual / errored
                  per-outcome counts
    failed_cases  case labels that FAILed, sorted
    errored_cases case labels that ended in ERROR, sorted
    cost          {"wall_seconds": float, "cli_calls": int, "grader_calls": int}
    notes         free text given with --journal-note, or ""

A legacy record (imported from a hand-written table) carries ``legacy``,
``runs`` (how many identical runs the row summarised) and ``result`` (the
row's Result cell, verbatim), and omits the per-case keys.

Rendering groups records by (date, ref, branch, model) into one table
row per batch, newest first, and reports each failing case as
"`label` failed k of n", the same wording the hand-maintained tables
used.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

SCHEMA_VERSION = 1
JOURNAL_NAME = "runs.jsonl"
EVALS_REL = Path("tools/skill-evals/evals")
RUN_HISTORY_HEADING = "## Run history"
TABLE_HEADER = "| Date | Ref | Model | Runs | Result | Notes |"
TABLE_RULE = "|---|---|---|---|---|---|"

# Prose written above the table when a README has no Run history section
# yet. Existing sections keep whatever prose they have; only the table is
# regenerated.
RUN_HISTORY_PREAMBLE = (
    "Live model runs over this whole eval directory, newest first.\n"
    "Generated from [`runs.jsonl`](runs.jsonl) by `skill-eval-journal render`;\n"
    "do not edit the table by hand.\n"
    "Columns and rules: [Recording runs](../../README.md#recording-runs).\n"
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def skill_dir_for(path: Path, evals_root: Path) -> Path | None:
    """Return ``<evals_root>/<skill>`` that contains ``path``, or None.

    Both paths are resolved first so a relative argument and a symlinked
    checkout compare equal. ``path`` may be the skill dir itself, a step dir,
    a fixtures dir or a single case dir.
    """
    try:
        rel = path.resolve().relative_to(evals_root.resolve())
    except ValueError:
        return None
    if not rel.parts:
        return None
    return evals_root / rel.parts[0]


def journal_path_for(path: Path, evals_root: Path) -> Path | None:
    skill_dir = skill_dir_for(path, evals_root)
    return None if skill_dir is None else skill_dir / JOURNAL_NAME


# ---------------------------------------------------------------------------
# Reading and writing
# ---------------------------------------------------------------------------


def append_record(journal: Path, record: dict, *, within: Path | None = None) -> None:
    """Append one record as a single JSON line. Never rewrites the file.

    The runner may run outside the sandbox (the eval wrapper does), and the
    tree is writable inside it, so the write must not be redirectable: a
    ``runs.jsonl`` that is a symlink is refused and the file is opened with
    ``O_NOFOLLOW``. With ``within``, the journal's resolved directory must
    also stay under that resolved root, so a symlinked skill directory
    cannot point the write elsewhere either.
    """
    if record.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"record schema must be {SCHEMA_VERSION}, got {record.get('schema')!r}")
    line = json.dumps(record, sort_keys=True, ensure_ascii=False)
    if "\n" in line:
        raise ValueError("record serialised with an embedded newline")
    journal.parent.mkdir(parents=True, exist_ok=True)
    if within is not None and not journal.parent.resolve().is_relative_to(within.resolve()):
        raise OSError(f"refusing to write {journal}: it resolves outside {within}")
    if journal.is_symlink():
        raise OSError(f"refusing to write {journal}: it is a symlink")
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(journal, flags, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_records(journal: Path) -> list[dict]:
    """Parse every line of ``journal``. A malformed line names its number."""
    records: list[dict] = []
    if not journal.exists():
        return records
    with journal.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{journal}:{lineno}: not valid JSON ({exc.msg})") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{journal}:{lineno}: record is not a JSON object")
            if record.get("schema") != SCHEMA_VERSION:
                raise ValueError(
                    f"{journal}:{lineno}: unsupported schema {record.get('schema')!r} "
                    f"(this tool reads schema {SCHEMA_VERSION})"
                )
            for key in ("skill", "date", "ref", "model"):
                if key not in record:
                    raise ValueError(f"{journal}:{lineno}: record lacks required key {key!r}")
            records.append(record)
    return records


def git_text(args: list[str], cwd: Path) -> str | None:
    """Run a read-only git command; None when git is unavailable or fails."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout if proc.returncode == 0 else None


def git_snapshot(cwd: Path) -> dict:
    """The commit the run was made at: short SHA, branch, dirty flag."""
    sha = (git_text(["rev-parse", "--short=8", "HEAD"], cwd) or "").strip()
    branch = (git_text(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or "").strip()
    status = git_text(["status", "--porcelain", "--untracked-files=no"], cwd)
    return {
        "ref": sha or "unknown",
        "branch": branch or "HEAD",
        "dirty": bool(status.strip()) if status is not None else None,
    }


_REDACTED = "<redacted>"
# A leading VAR=value word (an inline environment assignment, never a flag).
_ENV_ASSIGN_RE = re.compile(r"(?:(?<=\s)|^)([A-Za-z_][A-Za-z0-9_]*)=(?:\"[^\"]*\"|'[^']*'|\S+)")
# The value of a flag that carries a credential or a request header.
_SECRET_FLAG_RE = re.compile(
    r"(?i)(--(?:api[-_]?key|key|token|access[-_]token|auth[-_]token|bearer|password|secret|header)|-H)"
    r"(=|\s+)(?:\"[^\"]*\"|'[^']*'|\S+)"
)


def redact_cli(cli: str | None) -> str | None:
    """``cli`` with credentials removed, for a record that gets committed.

    The journal is committed to a public repository, and a CLI may be spelled
    with an inline secret (``ANTHROPIC_API_KEY=sk-… claude -p``,
    ``tool --api-key …``, ``-H 'Authorization: …'``). Inline environment
    assignments and the values of credential and header flags are replaced
    with ``<redacted>``; the rest, including ``--model``, is kept.
    """
    if not cli:
        return cli
    cli = _ENV_ASSIGN_RE.sub(lambda m: f"{m.group(1)}={_REDACTED}", cli)
    return _SECRET_FLAG_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", cli)


def model_from_cli(cli: str) -> str | None:
    """Return the value of a ``--model X`` / ``--model=X`` flag in ``cli``."""
    match = re.search(r"--model(?:=|\s+)(\S+)", cli)
    return match.group(1).strip("'\"") if match else None


def _settings_model(path: Path) -> str | None:
    """The ``model`` a Claude Code settings file pins, or None."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    model = data.get("model") if isinstance(data, dict) else None
    return model.strip() if isinstance(model, str) and model.strip() else None


def _is_claude_cli(cli: str) -> bool:
    try:
        first = shlex.split(cli)[0]
    except (ValueError, IndexError):
        return False
    return Path(first).name == "claude"


def resolve_model(
    cli: str,
    explicit: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
    home: Path | None = None,
) -> tuple[str | None, str | None]:
    """Return ``(model, source)`` for the run, best evidence first.

    1. ``explicit``: the operator said so (``--journal-model``).
    2. A ``--model`` flag in the ``--cli`` string.
    3. For a ``claude`` CLI only, what that CLI will itself use when no flag is
       given: ``ANTHROPIC_MODEL``, then the ``model`` key of the settings files
       in Claude Code's own precedence order (project local, project, user).
       Best effort: managed settings and an ``env.ANTHROPIC_MODEL`` inside a
       settings file are not read.

    The sandboxed eval wrapper takes exactly one argument and runs
    ``claude -p`` with no flag, so (3) is how its runs get a model at all. A
    value found nowhere is recorded as None and renders as unrecorded next to
    the ``--cli`` string, never guessed. ``source`` names where the value came from so a reader can
    weigh it: a settings default is weaker evidence than an explicit flag.
    """
    if explicit:
        return explicit, "journal-model"
    flagged = model_from_cli(cli)
    if flagged:
        return flagged, "cli-flag"
    if not _is_claude_cli(cli):
        return None, None
    environ: Mapping[str, str] = os.environ if env is None else env
    declared = environ.get("ANTHROPIC_MODEL", "").strip()
    if declared:
        return declared, "env:ANTHROPIC_MODEL"
    cwd = Path.cwd() if cwd is None else cwd
    home = Path.home() if home is None else home
    for label, path in (
        ("settings:project-local", cwd / ".claude" / "settings.local.json"),
        ("settings:project", cwd / ".claude" / "settings.json"),
        ("settings:user", home / ".claude" / "settings.json"),
    ):
        found = _settings_model(path)
        if found:
            return found, label
    return None, None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _row_key(record: dict) -> tuple[str, str, str, str]:
    # With no recorded model, key on the CLI instead, so runs of two
    # different tools at one ref on one day never share a row.
    model = str(record.get("model") or "")
    if not model and record.get("cli"):
        model = f"{UNRECORDED_CLI_PREFIX}{record['cli']}"
    return (
        str(record.get("date", "")),
        str(record.get("ref", "")),
        str(record.get("branch", "main") or "main"),
        model,
    )


def _fmt_ref(ref: str, branch: str) -> str:
    cell = f"`{ref}`"
    if branch not in ("main", "", "HEAD"):
        cell += f" ({branch})"
    return cell


UNRECORDED_CLI_PREFIX = "\0cli:"


def _fmt_model(model: str) -> str:
    if model.startswith(UNRECORDED_CLI_PREFIX):
        return f"(unrecorded, `{model[len(UNRECORDED_CLI_PREFIX) :]}`)"
    return f"`{model}`" if model else "(unrecorded)"


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def summarise_batch(records: list[dict]) -> tuple[int, str, str]:
    """Return (runs, result, notes) for one group of records."""
    runs = 0
    legacy_results: list[str] = []
    fail_counts: Counter[str] = Counter()
    error_counts: Counter[str] = Counter()
    # A case's denominator is the number of runs that graded it. A record
    # without ``graded_cases`` (written before the field existed) counts as
    # having graded every case, which is what the table showed before.
    graded_counts: Counter[str] = Counter()
    untracked_runs = 0
    graded_total = 0
    manual_total = 0
    live_runs = 0
    notes: list[str] = []
    for record in records:
        n = int(record.get("runs", 1))
        runs += n
        note = str(record.get("notes") or "").strip()
        if note and note not in notes:
            notes.append(note)
        if record.get("legacy"):
            text = str(record.get("result") or "").strip()
            if text and text not in legacy_results:
                legacy_results.append(text)
            continue
        live_runs += n
        manual_total += int(record.get("manual") or 0)
        if "graded_cases" in record:
            graded = [str(label) for label in record.get("graded_cases") or []]
            graded_counts.update(graded)
            graded_total += len(graded)
        else:
            untracked_runs += n
            graded_total += int(record.get("passed") or 0) + int(record.get("failed") or 0)
            graded_total += int(record.get("errored") or 0)
        for label in record.get("failed_cases") or []:
            fail_counts[str(label)] += 1
        for label in record.get("errored_cases") or []:
            error_counts[str(label)] += 1

    parts: list[str] = list(legacy_results)
    if live_runs:

        def of(label: str) -> int:
            return graded_counts[label] + untracked_runs

        live_parts = [f"`{label}` failed {k} of {of(label)}" for label, k in sorted(fail_counts.items())]
        live_parts += [f"`{label}` errored {k} of {of(label)}" for label, k in sorted(error_counts.items())]
        if live_parts:
            parts.append("; ".join(live_parts))
        elif graded_total == 0 and manual_total > 0:
            parts.append("manual")
        else:
            parts.append("pass")
    return runs, "; ".join(parts), "; ".join(notes)


def render_table(records: list[dict]) -> str:
    """Render the Run history table, newest first, one row per batch."""
    groups: dict[tuple[str, str, str, str], list[dict]] = {}
    last_seen: dict[tuple[str, str, str, str], int] = {}
    for index, record in enumerate(records):
        key = _row_key(record)
        groups.setdefault(key, []).append(record)
        last_seen[key] = index

    def sort_key(item: tuple[tuple[str, str, str, str], list[dict]]) -> tuple[str, str, int]:
        # Newest first: by date, then by the latest timestamp in the batch,
        # then by journal order (a later line is a later run), which is all a
        # legacy record without a timestamp has.
        key, batch = item
        newest = max(str(r.get("timestamp") or "") for r in batch)
        return (key[0], newest, last_seen[key])

    lines = [TABLE_HEADER, TABLE_RULE]
    for (date, ref, branch, model), batch in sorted(groups.items(), key=sort_key, reverse=True):
        runs, result, notes = summarise_batch(batch)
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(date),
                    _fmt_ref(ref, branch),
                    _fmt_model(model),
                    str(runs),
                    _escape_cell(result),
                    _escape_cell(notes),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _find_table_span(lines: list[str], start: int) -> tuple[int, int] | None:
    """Return [begin, end) of the first Markdown table at or after ``start``.

    Stops at the next heading so a table in a later section is not taken.
    """
    i = start
    while i < len(lines) and not lines[i].startswith("#"):
        if lines[i].startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            return i, j
        i += 1
    return None


def render_readme(readme_text: str, table: str) -> str:
    """Return ``readme_text`` with its Run history table replaced by ``table``.

    Appends a whole section when the README has none.
    """
    lines = readme_text.split("\n")
    heading_idx = next(
        (i for i, line in enumerate(lines) if line.strip().lower() == RUN_HISTORY_HEADING.lower()),
        None,
    )
    table_lines = table.rstrip("\n").split("\n")
    if heading_idx is None:
        body = readme_text.rstrip("\n")
        section = f"{RUN_HISTORY_HEADING}\n\n{RUN_HISTORY_PREAMBLE}\n{table}"
        return f"{body}\n\n{section}" if body else section
    span = _find_table_span(lines, heading_idx + 1)
    if span is None:
        # Section exists but has no table yet: add one at the section's end.
        end = heading_idx + 1
        while end < len(lines) and not lines[end].startswith("#"):
            end += 1
        while end > heading_idx + 1 and not lines[end - 1].strip():
            end -= 1
        new_lines = [*lines[:end], "", *table_lines, *lines[end:]]
    else:
        begin, end = span
        new_lines = lines[:begin] + table_lines + lines[end:]
    text = "\n".join(new_lines)
    return text if text.endswith("\n") else text + "\n"


# ---------------------------------------------------------------------------
# Importing a hand-written table (one-time migration)
# ---------------------------------------------------------------------------

_LEGACY_IMPORT_NOTE = "imported from the hand-maintained Run history table"


def parse_readme_table(readme_text: str) -> list[dict[str, str]]:
    """Return the rows of the README's Run history table as dicts."""
    lines = readme_text.split("\n")
    heading_idx = next(
        (i for i, line in enumerate(lines) if line.strip().lower() == RUN_HISTORY_HEADING.lower()),
        None,
    )
    if heading_idx is None:
        return []
    span = _find_table_span(lines, heading_idx + 1)
    if span is None:
        return []
    begin, end = span
    header = [c.strip() for c in lines[begin].strip().strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[begin + 2 : end]:
        cells = [c.strip() for c in _split_row(line)]
        if len(cells) != len(header):
            raise ValueError(f"table row has {len(cells)} cells, header has {len(header)}: {line!r}")
        rows.append(dict(zip(header, cells, strict=True)))
    return rows


def _split_row(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    # Split on unescaped pipes only.
    return [part.replace("\\|", "|") for part in re.split(r"(?<!\\)\|", body)]


def legacy_records_from_rows(rows: list[dict[str, str]], skill: str) -> list[dict]:
    """Turn hand-written table rows into legacy journal records, oldest first.

    The table is newest first; the journal is chronological, so the order is
    reversed. The Result cell is kept verbatim so the regenerated table
    reproduces the hand-written one.
    """
    records: list[dict] = []
    for row in reversed(rows):
        ref_cell = row.get("Ref", "")
        ref_match = re.match(r"`([^`]+)`(?:\s+\(([^)]+)\))?", ref_cell)
        ref = ref_match.group(1) if ref_match else ref_cell.strip("`")
        branch = ref_match.group(2) if ref_match and ref_match.group(2) else "main"
        model_cell = row.get("Model", "").strip("`")
        model = None if model_cell in ("", "(unrecorded)") else model_cell
        runs_cell = row.get("Runs", "1").strip()
        records.append(
            {
                "schema": SCHEMA_VERSION,
                "legacy": True,
                "skill": skill,
                "date": row.get("Date", "").strip(),
                "ref": ref,
                "branch": branch,
                "model": model,
                "runs": int(runs_cell) if runs_cell.isdigit() else 1,
                "result": row.get("Result", "").strip(),
                "notes": row.get("Notes", "").strip(),
                "import_note": _LEGACY_IMPORT_NOTE,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_append_only(committed: str, working: str) -> str | None:
    """Return a reason when ``working`` is not ``committed`` plus appended lines."""
    if not committed:
        return None
    if not committed.endswith("\n"):
        committed += "\n"
    if not working.startswith(committed):
        old_lines = committed.splitlines()
        new_lines = working.splitlines()
        for i, old in enumerate(old_lines):
            if i >= len(new_lines):
                return f"line {i + 1} was removed"
            if new_lines[i] != old:
                return f"line {i + 1} was changed"
        return "committed content is not a prefix of the working copy"
    return None


def iter_skill_dirs(target: Path, evals_root: Path) -> list[Path]:
    """Skill dirs to operate on: ``target`` itself when it is one, else all."""
    skill_dir = skill_dir_for(target, evals_root)
    if skill_dir is not None:
        return [skill_dir]
    if target.resolve() == evals_root.resolve():
        return sorted(p for p in evals_root.iterdir() if p.is_dir() and not p.name.startswith("."))
    raise ValueError(f"{target} is neither {evals_root} nor a path under it")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _repo_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def cmd_render(args: argparse.Namespace, evals_root: Path, root: Path) -> int:
    changed = 0
    for skill_dir in iter_skill_dirs(args.path, evals_root):
        journal = skill_dir / JOURNAL_NAME
        if not journal.exists():
            continue
        records = read_records(journal)
        readme = skill_dir / "README.md"
        current = readme.read_text(encoding="utf-8") if readme.exists() else ""
        rendered = render_readme(current, render_table(records))
        if rendered == current:
            continue
        changed += 1
        if args.check:
            print(f"{_repo_relative(readme, root)}: Run history table is out of date with {JOURNAL_NAME}")
        else:
            readme.write_text(rendered, encoding="utf-8")
            print(f"{_repo_relative(readme, root)}: Run history table regenerated")
    if args.check and changed:
        print(
            "run `uv run --project tools/skill-evals skill-eval-journal render tools/skill-evals/evals` "
            "to regenerate",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_check(args: argparse.Namespace, evals_root: Path, root: Path) -> int:
    problems = 0
    for skill_dir in iter_skill_dirs(args.path, evals_root):
        journal = skill_dir / JOURNAL_NAME
        if not journal.exists():
            # Deleting a whole journal is the largest edit of all.
            if args.against and git_text(["show", f"{args.against}:{_repo_relative(journal, root)}"], root):
                print(
                    f"{_repo_relative(journal, root)}: removed, but {args.against} has it (journals are append-only)",
                    file=sys.stderr,
                )
                problems += 1
            continue
        try:
            records = read_records(journal)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            problems += 1
            continue
        readme = skill_dir / "README.md"
        current = readme.read_text(encoding="utf-8") if readme.exists() else ""
        if render_readme(current, render_table(records)) != current:
            print(f"{_repo_relative(readme, root)}: Run history table is out of date with {JOURNAL_NAME}")
            problems += 1
        if args.against:
            committed = git_text(["show", f"{args.against}:{_repo_relative(journal, root)}"], root)
            if committed is None:
                # New journal, or the ref does not carry one: nothing to compare.
                continue
            reason = check_append_only(committed, journal.read_text(encoding="utf-8"))
            if reason:
                print(
                    f"{_repo_relative(journal, root)}: not append-only against {args.against} ({reason})",
                    file=sys.stderr,
                )
                problems += 1
    return 1 if problems else 0


def cmd_import_readme(args: argparse.Namespace, evals_root: Path, root: Path) -> int:
    skill_dir = skill_dir_for(args.path, evals_root)
    if skill_dir is None:
        print(f"{args.path} is not under {evals_root}", file=sys.stderr)
        return 2
    journal = skill_dir / JOURNAL_NAME
    if journal.exists() and journal.stat().st_size and not args.force:
        print(f"{_repo_relative(journal, root)} already exists; refusing to import over it", file=sys.stderr)
        return 1
    readme = skill_dir / "README.md"
    if not readme.exists():
        print(f"{_repo_relative(readme, root)} not found", file=sys.stderr)
        return 1
    rows = parse_readme_table(readme.read_text(encoding="utf-8"))
    if not rows:
        print(f"{_repo_relative(readme, root)}: no Run history table to import")
        return 0
    for record in legacy_records_from_rows(rows, skill_dir.name):
        append_record(journal, record)
    print(f"{_repo_relative(journal, root)}: imported {len(rows)} row(s)")
    return 0


def _find_repo_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / ".git").exists():
            return candidate
    raise FileNotFoundError(f"no .git found above {start}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="skill-eval-journal",
        description=(
            "Maintain the append-only eval run journal (evals/<skill>/runs.jsonl) and "
            "the Run history tables generated from it."
        ),
    )
    parser.add_argument(
        "--evals-root",
        type=Path,
        default=None,
        help=f"The evals tree (default: <repo root>/{EVALS_REL}).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_render = sub.add_parser("render", help="Regenerate each README's Run history table from its journal.")
    p_render.add_argument("path", type=Path, help="The evals root, or one skill's eval directory.")
    p_render.add_argument(
        "--check", action="store_true", help="Exit 1 if any table would change; write nothing."
    )

    p_check = sub.add_parser("check", help="Verify journals parse, tables match, and journals only grew.")
    p_check.add_argument("path", type=Path, help="The evals root, or one skill's eval directory.")
    p_check.add_argument(
        "--against",
        metavar="REF",
        default=None,
        help="Git ref whose committed journals must be a prefix of the working copies (e.g. origin/main).",
    )

    p_import = sub.add_parser(
        "import-readme",
        help="One-time: turn a hand-written Run history table into legacy journal records.",
    )
    p_import.add_argument("path", type=Path, help="One skill's eval directory.")
    p_import.add_argument("--force", action="store_true", help="Append even when a journal already exists.")

    args = parser.parse_args(argv)

    root: Path
    evals_root: Path
    if args.evals_root is not None:
        evals_root = args.evals_root
        try:
            root = _find_repo_root(evals_root)
        except FileNotFoundError:
            root = evals_root
    else:
        try:
            root = _find_repo_root(Path.cwd())
        except FileNotFoundError as exc:
            parser.error(f"{exc}; pass --evals-root")
            raise SystemExit(2) from exc  # parser.error never returns; this is for readers and analysers
        evals_root = root / EVALS_REL
    if not evals_root.is_dir():
        parser.error(f"evals root {evals_root} is not a directory")
    against = getattr(args, "against", None)
    if against is not None and (against.startswith("-") or not against.strip()):
        # The value is passed to `git show <ref>:<path>`; a leading dash would
        # make git read it as an option instead of a revision.
        parser.error(f"--against must be a git revision, got {against!r}")

    try:
        if args.command == "render":
            return cmd_render(args, evals_root, root)
        if args.command == "check":
            return cmd_check(args, evals_root, root)
        if args.command == "import-readme":
            return cmd_import_readme(args, evals_root, root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
