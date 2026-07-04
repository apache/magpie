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

"""Command line interface for the Bitbucket bridge."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from typing import Any

from magpie_bitbucket import cloud, datacenter, normalize
from magpie_bitbucket.client import BitbucketConfig, load_config


def main(argv: Sequence[str] | None = None) -> int:
    """Run the magpie-bitbucket command line interface."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_config()

    result = _dispatch(args, config)
    _print_json(result)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="magpie-bitbucket",
        description="Bitbucket Cloud and Data Center bridge for Apache Magpie.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("auth-check", help="Verify configured Bitbucket repository access.")

    repo_parser = subparsers.add_parser("repo", help="Interact with Bitbucket repositories.")
    repo_subparsers = repo_parser.add_subparsers(dest="repo_action", required=True)
    repo_subparsers.add_parser("get", help="Fetch repository metadata.")

    pr_parser = subparsers.add_parser("pr", help="Interact with Bitbucket pull requests.")
    pr_subparsers = pr_parser.add_subparsers(dest="pr_action", required=True)
    pr_subparsers.add_parser("list-open", help="List open pull requests.")

    pr_get = pr_subparsers.add_parser("get", help="Fetch one pull request.")
    pr_get.add_argument("pull_request_id", help="Pull request ID to fetch.")

    return parser


def _dispatch(args: argparse.Namespace, config: BitbucketConfig) -> dict[str, Any]:
    """Dispatch parsed CLI arguments to the selected backend."""
    backend = _backend(config)

    if args.subcommand == "auth-check":
        raw = backend.get_repository(config)
        return {
            "ok": True,
            "backend": "bitbucket-cloud" if config.kind == "cloud" else "bitbucket-datacenter",
            "repository": normalize.repository(config.kind, raw),
        }

    if args.subcommand == "repo" and args.repo_action == "get":
        raw = backend.get_repository(config)
        return normalize.repository(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "list-open":
        raw = backend.list_open_pull_requests(config)
        return normalize.pull_request_list(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "get":
        raw = backend.get_pull_request(config, args.pull_request_id)
        return normalize.pull_request(config.kind, raw)

    msg = "Unsupported command"
    raise ValueError(msg)


def _backend(config: BitbucketConfig) -> Any:
    """Return the module implementing the configured Bitbucket backend."""
    if config.kind == "cloud":
        return cloud
    return datacenter


def _print_json(data: dict[str, Any]) -> None:
    """Print JSON output to stdout."""
    print(json.dumps(data, indent=2, sort_keys=True))
