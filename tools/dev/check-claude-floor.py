#!/usr/bin/env python3
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
Validate the marketplace and each plugin with the ``claude-code`` floor release.

Installs ``min_version`` from ``tools/agent-isolation/pinned-versions.toml``
into a throwaway directory and runs ``claude plugin validate`` on
``.claude-plugin/marketplace.json`` and every plugin it lists. It skips
``--strict``, since fields newer than the floor only warn there, and
``claude plugin test``, which the floor lacks; ``check-claude-mods`` tests the
mods on its newer pin.

npm runs with ``--ignore-scripts`` and the package's ``install.cjs`` runs
explicitly, since npm may skip unapproved install scripts and leave only a
placeholder binary. The npm cache and Claude Code config stay in the throwaway
directory. Needs ``node``, ``npm`` and the npm registry.

Exits 1 when the floor rejects the marketplace or a plugin.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PINNED_VERSIONS = REPO_ROOT / "tools" / "agent-isolation" / "pinned-versions.toml"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"

PACKAGE = "@anthropic-ai/claude-code"

#: Exact X.Y.Z only: in an npm spec, a range would install its newest match.
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

Runner = Callable[..., subprocess.CompletedProcess[Any]]


class FloorError(Exception):
    """A problem that stops the check before anything is validated."""


def floor_version(manifest: Path = PINNED_VERSIONS) -> str:
    """``[tools.claude-code] min_version``: the oldest release Magpie supports."""
    try:
        version = tomllib.loads(manifest.read_text(encoding="utf-8"))["tools"]["claude-code"]["min_version"]
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise FloorError(f"{manifest}: cannot read [tools.claude-code] min_version ({exc!r})") from exc
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise FloorError(f"{manifest}: min_version {version!r} is not an exact X.Y.Z release")
    return version


def plugin_dirs(marketplace: Path = MARKETPLACE) -> list[Path]:
    """Every plugin the marketplace lists, relative to the marketplace root.

    A source outside this repository fails the check instead of being skipped.
    """
    root = marketplace.parent.parent
    try:
        entries = json.loads(marketplace.read_text(encoding="utf-8"))["plugins"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise FloorError(f"{marketplace}: cannot read the plugins list ({exc!r})") from exc
    if not isinstance(entries, list) or not entries:
        raise FloorError(f"{marketplace}: lists no plugins")
    dirs: list[Path] = []
    for entry in entries:
        source = entry.get("source") if isinstance(entry, dict) else None
        name = entry.get("name", source) if isinstance(entry, dict) else entry
        if not isinstance(source, str) or not source.startswith("./") or ".." in Path(source).parts:
            raise FloorError(
                f"{marketplace}: plugin {name!r} has source {source!r}; "
                "only a ./ path inside this repository can be validated here"
            )
        path = Path(source)
        if not (root / path / ".claude-plugin" / "plugin.json").is_file():
            raise FloorError(f"{marketplace}: plugin {name!r}: {source} has no .claude-plugin/plugin.json")
        dirs.append(path)
    return dirs


@contextmanager
def workdir() -> Generator[Path, None, None]:
    """A throwaway directory for the install, npm cache and configuration.

    Falls back to the git directory when a sandbox blocks the system temp
    directory, as ``check-claude-mods.sh`` does.
    """
    try:
        tmp = tempfile.TemporaryDirectory(prefix="claude-floor.")
    except OSError:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--absolute-git-dir"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tmp = tempfile.TemporaryDirectory(prefix="claude-floor.", dir=git_dir)
    with tmp as path:
        yield Path(path)


def install(version: str, into: Path, run: Runner = subprocess.run) -> Path:
    """Install ``PACKAGE@version`` under ``into`` and return the path of its ``claude``."""
    prefix = into / "claude-code"
    run(
        [
            "npm",
            "install",
            f"{PACKAGE}@{version}",
            "--prefix",
            str(prefix),
            "--cache",
            str(into / "npm-cache"),
            "--ignore-scripts",
            "--no-save",
            "--no-package-lock",
            "--no-audit",
            "--no-fund",
            "--no-update-notifier",
        ],
        check=True,
        cwd=into,
    )
    package = prefix / "node_modules" / PACKAGE
    postinstall = package / "install.cjs"
    if not postinstall.is_file():
        raise FloorError(
            f"{PACKAGE}@{version} ships no install.cjs, so its packaging changed; "
            "update the install step in tools/dev/check-claude-floor.py"
        )
    run(["node", str(postinstall)], check=True, cwd=package)
    return prefix / "node_modules" / ".bin" / "claude"


def claude_env(config_dir: Path) -> dict[str, str]:
    """The environment ``claude`` runs in, with a throwaway configuration and updates turned off."""
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env["DISABLE_AUTOUPDATER"] = "1"
    return env


def check(
    claude: Path,
    version: str,
    targets: Sequence[Path],
    env: dict[str, str],
    run: Runner = subprocess.run,
    cwd: Path = REPO_ROOT,
) -> int:
    """Validate every target, even after one fails; return 1 if any did."""
    reported = run([str(claude), "--version"], capture_output=True, text=True, env=env, cwd=cwd)
    output = f"{reported.stdout}{reported.stderr}".strip()
    if reported.returncode != 0 or not re.search(rf"^{re.escape(version)}\b", reported.stdout, re.M):
        print(f"check-claude-floor: {claude} is not Claude Code {version}: {output}", file=sys.stderr)
        return 1
    status = 0
    for target in targets:
        print(f"== {target}", flush=True)
        if run([str(claude), "plugin", "validate", str(target)], env=env, cwd=cwd).returncode != 0:
            status = 1
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.parse_args(argv)

    try:
        version = floor_version()
        targets = [MARKETPLACE.relative_to(REPO_ROOT), *plugin_dirs()]
    except FloorError as exc:
        print(f"check-claude-floor: {exc}", file=sys.stderr)
        return 1
    missing = [tool for tool in ("node", "npm") if shutil.which(tool) is None]
    if missing:
        print(
            f"check-claude-floor: {' and '.join(missing)} not on the PATH; "
            f"the check installs Claude Code {version} with npm.",
            file=sys.stderr,
        )
        return 1

    print(
        f"check-claude-floor: Claude Code {version}, the claude-code floor "
        f"(min_version in {PINNED_VERSIONS.relative_to(REPO_ROOT)})",
        flush=True,
    )
    with workdir() as into:
        try:
            claude = install(version, into)
        except (subprocess.CalledProcessError, FloorError) as exc:
            print(f"check-claude-floor: installing {PACKAGE}@{version} failed: {exc}", file=sys.stderr)
            return 1
        config = into / "config"
        config.mkdir()
        return check(claude, version, targets, claude_env(config))


if __name__ == "__main__":
    sys.exit(main())
