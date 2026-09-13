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

"""Audit Apache GitHub Actions workflows for obsolete runners and macOS arch mismatches."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.request import urlopen

try:
    import yaml
except Exception:  # pragma: no cover - reported at runtime for YAML-dependent commands
    yaml = None

RETIRED_LABELS = {
    "ubuntu-20.04",
    "ubuntu-18.04",
    "ubuntu-16.04",
    "windows-2019",
    "windows-2016",
    "macos-13",
    "macos-12",
    "macos-11",
    "macos-10.15",
    "macos-13-large",
    "macos-13-xlarge",
}

MACOS_ARM = {"macos-latest", "macos-14", "macos-15", "macos-26", "macos-13-xlarge"}
MACOS_X64 = {
    "macos-15-intel",
    "macos-26-intel",
    "macos-13",
    "macos-12",
    "macos-11",
    "macos-10.15",
    "macos-13-large",
}
MACOS_ANY = MACOS_ARM | MACOS_X64

X64_TERMS = re.compile(
    r"(?i)(?:\bx64\b|\bx86_64\b|\bamd64\b|architecture:\s*['\"]?x64['\"]?|arch:\s*['\"]?(?:x64|x86_64|amd64)['\"]?)"
)
ARM_TERMS = re.compile(
    r"(?i)(?:\barm64\b|\baarch64\b|architecture:\s*['\"]?arm64['\"]?|arch:\s*['\"]?(?:arm64|aarch64)['\"]?)"
)
ARCH_KEYS = {
    "architecture",
    "arch",
    "target",
    "targets",
    "platform",
    "platforms",
    "os",
    "goarch",
    "node-arch",
}


def run(args: list[str]) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)


def gh_json(path: str) -> object | None:
    try:
        return json.loads(run(["gh", "api", path]))
    except Exception:
        return None


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=20) as response:  # nosec: auditing public GitHub URLs
        return response.read().decode("utf-8", errors="replace")


def flatten(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from flatten(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from flatten(child)
    elif value is not None:
        yield str(value)


def lower_values(value) -> list[str]:
    return [item.strip().lower() for item in flatten(value)]


def load_repos(cache_dir: Path, owner: str, refresh: bool) -> list[dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    repo_file = cache_dir / f"{owner}-repos.jsonl"
    if refresh or not repo_file.exists():
        output = run(
            [
                "gh",
                "api",
                "--paginate",
                f"/orgs/{owner}/repos?per_page=100&type=public",
                "--jq",
                ".[] | select(.archived == false) | {full_name, default_branch}",
            ]
        )
        repo_file.write_text(output, encoding="utf-8")
    return [json.loads(line) for line in repo_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_repo(full_name: str) -> dict:
    repo = gh_json(f"repos/{full_name}")
    if not isinstance(repo, dict):
        raise RuntimeError(f"Could not load repository metadata for {full_name}")
    if repo.get("archived"):
        return {}
    return {"full_name": repo.get("full_name"), "default_branch": repo.get("default_branch")}


def load_repo_file(path: Path) -> list[str]:
    repos = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            repos.append(line)
    return repos


def scope_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "scope"


def list_workflows_for_repo(repo: dict) -> list[dict]:
    full_name = repo.get("full_name")
    branch = repo.get("default_branch")
    if not full_name or not branch:
        return []
    contents = gh_json(f"repos/{full_name}/contents/.github/workflows?ref={branch}")
    if not isinstance(contents, list):
        return []
    workflows = []
    for item in contents:
        path = item.get("path", "")
        if item.get("type") == "file" and re.search(r"\.ya?ml$", path):
            workflows.append(
                {
                    "repo": full_name,
                    "branch": branch,
                    "path": path,
                    "url": item.get("download_url"),
                    "html_url": f"https://github.com/{full_name}/blob/{branch}/{path}",
                }
            )
    return workflows


def load_workflows(cache_dir: Path, owner: str, refresh: bool, workers: int) -> list[dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    workflow_file = cache_dir / f"{owner}-workflow-files.tsv"
    if refresh or not workflow_file.exists():
        repos = load_repos(cache_dir, owner, refresh)
        workflows: list[dict] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(list_workflows_for_repo, repo) for repo in repos]
            for future in as_completed(futures):
                workflows.extend(future.result())
        with workflow_file.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(
                output,
                delimiter="\t",
                fieldnames=["repo", "branch", "path", "url", "html_url"],
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(sorted(workflows, key=lambda row: (row["repo"], row["path"])))
    with workflow_file.open(newline="", encoding="utf-8") as input_file:
        return list(csv.DictReader(input_file, delimiter="\t"))


def load_workflows_for_repos(repo_names: list[str], workers: int) -> list[dict]:
    repos = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(load_repo, repo_name) for repo_name in repo_names]
        for future in as_completed(futures):
            repo = future.result()
            if repo:
                repos.append(repo)
    workflows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        workflow_futures: list[Future[list[dict]]] = [
            executor.submit(list_workflows_for_repo, repo) for repo in repos
        ]
        for workflow_future in as_completed(workflow_futures):
            workflows.extend(workflow_future.result())
    return sorted(workflows, key=lambda row: (row["repo"], row["path"]))


def yaml_load(text: str) -> object:
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install python3-yaml or pyyaml.")
    return yaml.safe_load(text) or {}


def matrix_rows(matrix: object) -> list[dict]:
    if not isinstance(matrix, dict):
        return [{}]
    keys: list[str] = []
    values: list[list] = []
    for key, value in matrix.items():
        if key in ("include", "exclude"):
            continue
        keys.append(str(key))
        values.append(value if isinstance(value, list) else [value])
    rows: list[dict[str, Any]] = [{}]
    for key, vals in zip(keys, values, strict=True):
        rows = [{**row, key: val} for row in rows for val in vals]

    excludes = matrix.get("exclude")
    if isinstance(excludes, list):

        def is_excluded(row: dict) -> bool:
            return any(
                isinstance(item, dict)
                and all(str(row.get(k)).lower() == str(v).lower() for k, v in item.items())
                for item in excludes
            )

        rows = [row for row in rows if not is_excluded(row)]

    includes = matrix.get("include")
    if isinstance(includes, list):
        rows.extend(item for item in includes if isinstance(item, dict))
    return rows or [{}]


def runner_arch(label: str) -> str | None:
    label = label.strip().lower()
    if label in MACOS_ARM:
        return "arm64"
    if label in MACOS_X64:
        return "x64"
    return None


def candidate_runner_contexts(job: dict) -> list[tuple[str, str | None, dict]]:
    runs_on_values = lower_values(job.get("runs-on"))
    contexts: list[tuple[str, str | None, dict]] = []
    for label in runs_on_values:
        if label in MACOS_ANY:
            contexts.append((label, runner_arch(label), {}))
    if "matrix." in " ".join(runs_on_values):
        rows = matrix_rows((job.get("strategy") or {}).get("matrix") or {})
        for row in rows:
            for value in lower_values(row):
                if value in MACOS_ANY:
                    contexts.append((value, runner_arch(value), row))
    seen = set()
    unique = []
    for label, arch, row in contexts:
        key = (label, arch, tuple(sorted((str(k), str(v)) for k, v in row.items())))
        if key not in seen:
            seen.add(key)
            unique.append((label, arch, row))
    return unique


def retired_hits(workflow: dict) -> list[dict]:
    try:
        data = yaml_load(fetch_text(workflow["url"]))
    except Exception:
        return []
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, dict):
        return []
    hits = []
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        run_values = lower_values(job.get("runs-on"))
        rows = matrix_rows((job.get("strategy") or {}).get("matrix") or {})
        labels = {value for value in run_values if value in RETIRED_LABELS}
        if "matrix." in " ".join(run_values):
            for row in rows:
                labels.update(value for value in lower_values(row) if value in RETIRED_LABELS)
        if any("self-hosted" in value for value in run_values):
            labels.clear()
        for label in sorted(labels):
            hits.append({**workflow, "job": str(job_name), "runner": label})
    return hits


def arch_hits(workflow: dict) -> list[dict]:
    try:
        data = yaml_load(fetch_text(workflow["url"]))
    except Exception:
        return []
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, dict):
        return []
    hits = []
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            continue
        contexts = candidate_runner_contexts(job)
        if not contexts:
            continue
        steps = job.get("steps") or []
        observed = []
        for step in steps if isinstance(steps, list) else []:
            if not isinstance(step, dict):
                continue
            step_if = str(step.get("if", "")).lower()
            skip_non_macos_branch = any(
                token in step_if
                for token in [
                    "runner.os == 'windows'",
                    'runner.os == "windows"',
                    "matrix.os == 'windows",
                    'matrix.os == "windows',
                    "runner.os == 'linux'",
                    'runner.os == "linux"',
                    "matrix.os == 'ubuntu",
                    'matrix.os == "ubuntu',
                ]
            )
            if skip_non_macos_branch:
                continue
            name = str(step.get("name", ""))
            uses = str(step.get("uses", ""))
            raw_with = step.get("with")
            action_inputs = raw_with if isinstance(raw_with, dict) else {}
            for key, value in action_inputs.items():
                key_text = str(key).lower()
                value_text = " ".join(lower_values(value))
                if key_text in ARCH_KEYS or "arch" in key_text or "platform" in key_text:
                    evidence = f"with.{key}={value}"
                    if X64_TERMS.search(f"{key_text}: {value_text}"):
                        observed.append(
                            (
                                "x64",
                                name,
                                uses,
                                evidence,
                                "setup-action" if uses.startswith("actions/setup-") else "action-input",
                            )
                        )
                    if ARM_TERMS.search(f"{key_text}: {value_text}"):
                        observed.append(
                            (
                                "arm64",
                                name,
                                uses,
                                evidence,
                                "setup-action" if uses.startswith("actions/setup-") else "action-input",
                            )
                        )
            run_script = step.get("run")
            if isinstance(run_script, str):
                for line in run_script.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if X64_TERMS.search(line):
                        observed.append(("x64", name, uses, line[:180], "script"))
                    if ARM_TERMS.search(line):
                        observed.append(("arm64", name, uses, line[:180], "script"))
        for label, arch, matrix in contexts:
            for binary_arch, step_name, uses, evidence, confidence in observed:
                if arch and binary_arch != arch:
                    hits.append(
                        {
                            **workflow,
                            "job": str(job_name),
                            "runner": label,
                            "runner_arch": arch,
                            "requested_arch": binary_arch,
                            "step": step_name,
                            "uses": uses,
                            "evidence": evidence,
                            "matrix": ",".join(f"{k}={v}" for k, v in matrix.items()),
                            "confidence": confidence,
                        }
                    )
    return hits


def parallel_scan(workflows: list[dict], scanner, workers: int) -> list[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(scanner, workflow) for workflow in workflows if workflow.get("url")]
        for future in as_completed(futures):
            results.extend(future.result())
    return sorted(
        results,
        key=lambda row: (
            row.get("repo", ""),
            row.get("path", ""),
            row.get("job", ""),
            row.get("runner", ""),
            row.get("evidence", ""),
        ),
    )


def write_tsv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(
            output, delimiter="\t", fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["retired", "macos-arch", "all"])
    parser.add_argument("--owner", default="apache")
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Repository full name, e.g. apache/polaris. May be repeated.",
    )
    parser.add_argument("--repo-file", type=Path, help="File containing repository full names, one per line.")
    parser.add_argument("--scope-name", help="Output filename prefix for explicit repo/repo-file scans.")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache"))
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    parser.add_argument("--workers", type=int, default=20)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    repo_names = list(args.repo)
    if args.repo_file:
        repo_names.extend(load_repo_file(args.repo_file))
    repo_names = sorted(set(repo_names))

    if repo_names:
        workflows = load_workflows_for_repos(repo_names, args.workers)
        if args.scope_name:
            prefix = scope_key(args.scope_name)
        elif len(repo_names) == 1:
            prefix = scope_key(repo_names[0])
        else:
            prefix = "repo-set"
    else:
        workflows = load_workflows(args.cache_dir, args.owner, args.refresh, args.workers)
        prefix = scope_key(args.scope_name or args.owner)

    if args.command in ("retired", "all"):
        retired = parallel_scan(workflows, retired_hits, args.workers)
        write_tsv(
            args.out_dir / f"{prefix}-retired-gh-runners-confirmed.tsv",
            retired,
            ["repo", "path", "job", "runner", "html_url"],
        )
        print(f"retired_runner_hits={len(retired)}", file=sys.stderr)

    if args.command in ("macos-arch", "all"):
        arch = parallel_scan(workflows, arch_hits, args.workers)
        write_tsv(
            args.out_dir / f"{prefix}-macos-arch-mismatch-candidates.tsv",
            arch,
            [
                "repo",
                "path",
                "job",
                "runner",
                "runner_arch",
                "requested_arch",
                "confidence",
                "step",
                "uses",
                "evidence",
                "matrix",
                "html_url",
            ],
        )
        setup = []
        seen = set()
        for row in arch:
            if row.get("confidence") == "setup-action":
                key = (
                    row.get("repo"),
                    row.get("path"),
                    row.get("job"),
                    row.get("runner"),
                    row.get("uses"),
                    row.get("evidence"),
                )
                if key not in seen:
                    seen.add(key)
                    setup.append(row)
        write_tsv(
            args.out_dir / f"{prefix}-macos-setup-action-arch-mismatches.tsv",
            setup,
            [
                "repo",
                "path",
                "job",
                "runner",
                "runner_arch",
                "requested_arch",
                "step",
                "uses",
                "evidence",
                "html_url",
            ],
        )
        print(f"macos_arch_candidates={len(arch)}", file=sys.stderr)
        print(f"setup_action_mismatches={len(setup)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
