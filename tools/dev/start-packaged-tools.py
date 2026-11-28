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
"""Start every tool once from its packaged plugin copy.

`tools/dev/check-family-plugins.py` copies framework tools into `plugins/` and
rewrites each copied `pyproject.toml` so it resolves without the uv workspace.
Nothing started those copies, so a copy uv could not resolve shipped twice
(#1357, #1937). This copies each plugin's `tools/` tree outside the checkout
and starts every tool in it: its `[project.scripts]` entry with `--help`, or,
for a library with no scripts, an import of its package. With no workspace
above the copy, uv resolves exactly what an adopter installs.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

PLUGINS = Path("plugins")
TOOLS = "tools"
UV = shutil.which("uv") or "uv"
TIMEOUT = 120


@dataclass(frozen=True)
class PackagedTool:
    plugin: str
    path: Path
    scripts: tuple[str, ...]
    modules: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.plugin}/{self.path.as_posix()}"


def scripts_of(data: dict) -> tuple[str, ...]:
    return tuple(data.get("project", {}).get("scripts", {}))


def modules_of(data: dict) -> tuple[str, ...]:
    """The importable package names, from the wheel target or the project name."""
    wheel = data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})
    packages = wheel.get("packages", [])
    if packages:
        return tuple(Path(package).name.replace("-", "_") for package in packages)
    name = data.get("project", {}).get("name", "")
    return (name.replace("-", "_"),) if name else ()


SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules"}


def _tool_dirs(tools_root: Path):
    """Every directory under a plugin's `tools/` that holds a pyproject, following links."""
    seen: set[Path] = set()
    for current, dirs, files in os.walk(tools_root, followlinks=True):
        real = Path(current).resolve()
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if "pyproject.toml" in files:
            yield Path(current)


def discover(root: Path) -> list[PackagedTool]:
    tools: list[PackagedTool] = []
    for plugin_dir in sorted((root / PLUGINS).iterdir()):
        tools_root = plugin_dir / TOOLS
        if not tools_root.is_dir():
            continue
        for tool_dir in _tool_dirs(tools_root):
            data = tomllib.loads((tool_dir / "pyproject.toml").read_text(encoding="utf-8"))
            tools.append(
                PackagedTool(
                    plugin=plugin_dir.name,
                    path=Path(TOOLS, *tool_dir.relative_to(tools_root).parts),
                    scripts=scripts_of(data),
                    modules=modules_of(data),
                )
            )
    return sorted(tools, key=lambda tool: tool.label)


def probes(tool: PackagedTool, project: Path) -> list[tuple[str, list[str]]]:
    """The command that starts the tool, and a label for the log.

    `--all-extras` covers frontends that live behind an optional extra, such as
    `oauth-draft-mcp` and its `mcp` SDK. Only one copied tool declares extras,
    so the cost is one dependency set.
    """
    if tool.scripts:
        return [
            (
                f"{script} --help",
                [UV, "run", "--all-extras", "--project", str(project), script, "--help"],
            )
            for script in tool.scripts
        ]
    return [
        (
            f"import {module}",
            [UV, "run", "--all-extras", "--project", str(project), "python", "-c", f"import {module}"],
        )
        for module in tool.modules
    ]


def probe_env() -> dict[str, str]:
    """The caller's environment without any virtualenv that would win over the copy."""
    return {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")}


def run_probe(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=probe_env(), timeout=TIMEOUT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--only", default="", help="only tools whose label contains this")
    parser.add_argument("--keep", action="store_true", help="keep the temporary copies")
    args = parser.parse_args()

    root = args.root.resolve()
    tools = [tool for tool in discover(root) if args.only in tool.label]
    if not tools:
        print(f"no packaged tools found under {root / PLUGINS}", file=sys.stderr)
        return 1

    workspace = Path(tempfile.mkdtemp(prefix="magpie-packaged-tools-"))
    copied: set[str] = set()
    started = 0
    failed = 0
    try:
        for tool in tools:
            plugin_root = workspace / tool.plugin
            if tool.plugin not in copied:
                shutil.copytree(
                    root / PLUGINS / tool.plugin / TOOLS,
                    plugin_root / TOOLS,
                    symlinks=False,
                    dirs_exist_ok=True,
                )
                copied.add(tool.plugin)
            project = plugin_root / tool.path
            commands = probes(tool, project)
            if not commands:
                print(f"FAIL {tool.label}: no [project.scripts] entry and no package to import")
                failed += 1
                continue
            for label, command in commands:
                started += 1
                try:
                    result = run_probe(command, workspace)
                except subprocess.TimeoutExpired:
                    print(f"FAIL {tool.label}: {label} did not finish in {TIMEOUT}s")
                    failed += 1
                    continue
                if result.returncode == 0:
                    print(f"PASS {tool.label}: {label}")
                    continue
                failed += 1
                print(f"FAIL {tool.label}: {label} (exit {result.returncode})")
                sys.stdout.write(result.stdout)
                sys.stderr.write(result.stderr)
    finally:
        if args.keep:
            print(f"copies kept at {workspace}")
        else:
            shutil.rmtree(workspace, ignore_errors=True)

    print(f"{started - failed}/{started} probes passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
