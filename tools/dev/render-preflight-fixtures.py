#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Render the pre-flight eval cases from what the checker actually prints.

The `setup/preflight-floor` eval suite asks a model what the shared pre-flight
block does with a given repository and machine state. The block itself no
longer works anything out: it runs `python3 -m setup_preflight` and acts on
the verdict that prints. So a case is only meaningful if it carries that
verdict, exactly as the checker would print it for that state.

Hand-written verdicts drift. The suite went stale the first time the checker
changed — its cases still described the floor check the block used to do in
prose — and six of eight failed on `main` with nothing in CI noticing. So the
verdict is rendered, never written:

* each case directory holds a `state.json` describing the state;
* this script builds that state as a scratch git repository, runs the real
  checker against it, and writes the printed verdict into the case's
  `report.md`, below the case's own prose;
* `--check` renders the same way and fails when any report differs, which is
  what the `render-preflight-fixtures` hook runs on every change to the
  checker, its rules sections, or the cases.

`state.json` keys:

* `lock` — the committed `.apache-magpie.lock` lines, or `null` for none.
  A lock also gets `.apache-magpie-overrides/project.md`.
* `plugins` — `[[name, version], ...]` for the running harness's listing,
  or the string `"unreadable"` for output that cannot be parsed. Codex
  entries are wrapped in its `installed` / `available` JSON envelope.
* `requires` — `requires_config:` entries passed as `--requires`.
* `skill`, `hash` — the invoking skill's `name:` and `surface_hash:`.
* `reconciled` — dict written to personal layer `reconciled.json`, or `null`.
* `harness` — the harness whose session the case runs in (`codex`,
  `copilot`, `antigravity`, or `claude`). The renderer puts that harness's
  session markers in the environment and a stub listing command on `PATH`
  that prints `plugins`, so the checker detects the harness itself and
  reads the listing the way that harness's session would produce it.
  Left out for no markers at all, which the checker reports as an unknown
  harness.
* `welcome` — `true` to include the skill family's first-run welcome guide.
  Left out otherwise (`--no-welcome`), so a floor case is about the floor
  and not about which family its skill happens to belong to.
* `check` — `"welcome-due"` runs `python3 -m setup_preflight.welcome due`
  instead of the full pre-flight: the hard-coded welcome check the `setup`
  skill runs, since the setup family carries no shared pre-flight block.
  Only `skill` and `reconciled` apply to it.

Each suite in `SUITES` is rendered the same way; a `welcome-due` case's
verdict follows `WELCOME_MARKER` rather than `MARKER`.

Usage:

    python3 tools/dev/render-preflight-fixtures.py           # rewrite reports
    python3 tools/dev/render-preflight-fixtures.py --check   # fail on drift
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SUITES = (
    Path("tools/skill-evals/evals/setup/preflight-floor/fixtures"),
    Path("tools/skill-evals/evals/setup/welcome-first-run/fixtures"),
)
CHECKER = Path("plugins/magpie-setup/skills/setup")
MARKER = "\nThe pre-flight command printed:\n"
WELCOME_MARKER = "\nThe welcome check printed:\n"
WELCOME_DUE = "welcome-due"
DEFAULT_SKILL = "issue-triage"
DEFAULT_HASH = "sha256:2edc90a1b7f3440d"

#: The session markers each harness self-detects by, mirroring the
#: checker's own `HARNESS_LISTINGS` marker order (the listing command is
#: the checker's business, not the renderer's).
HARNESS_ENV: dict[str, dict[str, str]] = {
    "codex": {"CODEX_SANDBOX": "1"},
    "copilot": {"COPILOT_CLI": "1"},
    "antigravity": {"ANTIGRAVITY_CONVERSATION_ID": "probe"},
    "claude": {"CLAUDECODE": "1"},
}
#: The listing executable, where it is not named after the harness.
HARNESS_BIN: dict[str, str] = {"antigravity": "agy"}


def run_checker(state: dict[str, object], repo_root: Path, scratch: Path) -> str:
    """Build `state` as a repository under `scratch` and return the checker's stdout."""
    project = scratch / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True, env=_env(scratch))

    lock = state.get("lock")
    if lock is not None:
        if not isinstance(lock, list):
            raise ValueError("`lock` must be a list of lines or null")
        (project / ".apache-magpie.lock").write_text("\n".join(lock) + "\n", encoding="utf-8")
        overrides = project / ".apache-magpie-overrides"
        overrides.mkdir()
        (overrides / "project.md").write_text("# project\n", encoding="utf-8")

    reconciled = state.get("reconciled")
    if reconciled is not None:
        if not isinstance(reconciled, dict):
            raise ValueError("`reconciled` must be a dict or null")
        personal = (
            (project / ".apache-magpie-local") if lock is not None else (project / ".git" / "apache-magpie")
        )
        personal.mkdir(parents=True, exist_ok=True)
        (personal / "reconciled.json").write_text(json.dumps(reconciled), encoding="utf-8")

    check = state.get("check")
    if check is not None and check != WELCOME_DUE:
        raise ValueError(f"`check` must be {WELCOME_DUE!r} or left out")
    if check == WELCOME_DUE:
        env = _env(scratch)
        env["PYTHONPATH"] = str(repo_root / CHECKER)
        skill = str(state.get("skill", "setup"))
        due = [sys.executable, "-m", "setup_preflight.welcome", "due", "--skill", skill]
        due += ["--project-root", str(project)]
        result = subprocess.run(due, capture_output=True, text=True, env=env, cwd=project, check=False)
        if result.returncode != 0:
            detail = result.stderr.strip()
            raise RuntimeError(f"setup_preflight.welcome due exited {result.returncode}: {detail}")
        return result.stdout.rstrip("\n")

    harness = state.get("harness")
    listing = scratch / "plugins.json"
    plugins = state.get("plugins")
    if plugins == "unreadable":
        listing.write_text("listing unavailable\n", encoding="utf-8")
    elif isinstance(plugins, list):
        entries = [{"name": n, "version": v} for n, v in plugins]
        payload = {"installed": entries, "available": []} if harness == "codex" else entries
        listing.write_text(json.dumps(payload), encoding="utf-8")
    else:
        raise ValueError('`plugins` must be a list of [name, version] or "unreadable"')

    if harness is not None:
        # The checker must detect this harness itself, from the same session
        # markers a live session carries, and read the harness's own listing
        # command — a stub on PATH that prints the case's listing. Passing
        # `--plugin-list` would describe the listing as already read, which
        # is exactly the "the harness is then not known" case.
        if not isinstance(harness, str) or harness not in HARNESS_ENV:
            raise ValueError(f"`harness` must be one of {', '.join(sorted(HARNESS_ENV))} or null")
        markers: dict[str, str] = HARNESS_ENV[harness]
        bin_dir = scratch / "bin"
        bin_dir.mkdir()
        listing_arg = str(listing).replace("\\", "/")
        binary = HARNESS_BIN.get(harness, harness)
        stub = bin_dir / binary
        stub.write_text(f'#!/bin/sh\ncat "{listing_arg}"\n', encoding="utf-8")
        os.chmod(stub, 0o700)  # owner-only: the renderer runs it as itself
        (bin_dir / f"{binary}.bat").write_text(f'@echo off\ntype "{listing}"\r\n', encoding="utf-8")
        env = _env(scratch)
        env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
        env.update(markers)
    else:
        env = _env(scratch)
    env["PYTHONPATH"] = str(repo_root / CHECKER)

    args = [
        sys.executable,
        "-m",
        "setup_preflight",
        "--skill",
        str(state.get("skill", DEFAULT_SKILL)),
        "--hash",
        str(state.get("hash", DEFAULT_HASH)),
        "--project-root",
        str(project),
        "--no-cache",
        "--verify-interval-days",
        "0",
        "--isolated-setup-interval-days",
        "0",
    ]
    if harness is None:
        # No harness to detect: hand the checker the listing as already read.
        args += ["--plugin-list", str(listing)]
    requires = state.get("requires", [])
    if not isinstance(requires, list):
        raise ValueError("`requires` must be a list")
    for entry in requires:
        args += ["--requires", str(entry)]
    if state.get("welcome") is not True:
        args.append("--no-welcome")

    if os.name == "nt" and harness is not None:
        # CreateProcess does not search PATHEXT for a bare command name.
        # Resolve only the fixture's .bat stub; keep harness detection,
        # listing arguments, parsing and the checker itself unchanged.
        launcher = (
            "from setup_preflight import cli; "
            f"name = {harness!r}; stub = {str(bin_dir / (harness + '.bat'))!r}; "
            "[(argv.__setitem__(0, stub)) for h, _, argv in cli.HARNESS_LISTINGS "
            "if h == name and argv is not None]; "
            "raise SystemExit(cli.main())"
        )
        args[1:3] = ["-c", launcher]

    result = subprocess.run(args, capture_output=True, text=True, env=env, cwd=project, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"setup_preflight exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout.rstrip("\n")


def _env(scratch: Path) -> dict[str, str]:
    """A minimal environment, so nothing on the host leaks into a verdict."""
    home = scratch / "home"
    home.mkdir(exist_ok=True)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "LC_ALL": "C",
    }
    if os.name == "nt":
        # Windows needs these to launch batch stubs from the child Python.
        for key in ("SystemRoot", "COMSPEC"):
            if key in os.environ:
                env[key] = os.environ[key]
    return env


def render_report(prose: str, verdict: str, marker: str = MARKER) -> str:
    """The case's own prose, then the verdict block. Idempotent."""
    if marker in prose:
        prose = prose[: prose.index(marker)]
    return prose.rstrip("\n") + "\n" + marker + "\n```json\n" + verdict + "\n```\n"


def render_suite(repo_root: Path) -> dict[Path, str]:
    """Every case's report as it should read now."""
    out: dict[Path, str] = {}
    for suite in SUITES:
        for state_file in sorted((repo_root / suite).glob("case-*/state.json")):
            state = json.loads(state_file.read_text(encoding="utf-8"))
            report = state_file.parent / "report.md"
            with tempfile.TemporaryDirectory() as tmp:
                verdict = run_checker(state, repo_root, Path(tmp))
            marker = WELCOME_MARKER if state.get("check") == WELCOME_DUE else MARKER
            out[report] = render_report(report.read_text(encoding="utf-8"), verdict, marker)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when a report is stale; write nothing")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    root: Path = args.repo_root.resolve()
    cases = sorted(p for suite in SUITES for p in (root / suite).glob("case-*") if p.is_dir())
    missing = [c.name for c in cases if not (c / "state.json").is_file()]
    if missing:
        print(f"render-preflight-fixtures: no state.json in {', '.join(missing)}", file=sys.stderr)
        return 1

    stale = []
    for report, text in render_suite(root).items():
        if report.read_text(encoding="utf-8") == text:
            continue
        stale.append(report)
        if not args.check:
            report.write_text(text, encoding="utf-8", newline="\n")

    if not stale:
        return 0
    names = ", ".join(str(p.relative_to(root)) for p in stale)
    if args.check:
        print(
            f"render-preflight-fixtures: {len(stale)} report(s) no longer match the checker: {names}\n"
            "Run `python3 tools/dev/render-preflight-fixtures.py`, then check the cases' expected.json "
            "still holds against the new verdicts.",
            file=sys.stderr,
        )
    else:
        print(f"render-preflight-fixtures: re-rendered {names}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
