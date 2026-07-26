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
    repo_subparsers.add_parser("restrictions", help="Fetch repository branch restrictions.")

    issue_parser = subparsers.add_parser("issue", help="Interact with Bitbucket issues.")
    issue_subparsers = issue_parser.add_subparsers(dest="issue_action", required=True)
    issue_subparsers.add_parser("list-open", help="List open issues.")

    issue_get = issue_subparsers.add_parser("get", help="Fetch one issue.")
    issue_get.add_argument("issue_id", help="Issue ID to fetch.")

    issue_comments = issue_subparsers.add_parser("comments", help="Fetch issue comments.")
    issue_comments.add_argument("issue_id", help="Issue ID to fetch comments for.")

    issue_attachments = issue_subparsers.add_parser(
        "attachments",
        help="Fetch issue attachment metadata and links, not file contents.",
    )
    issue_attachments.add_argument(
        "issue_id",
        help="Issue ID whose attachment metadata to fetch.",
    )

    pr_parser = subparsers.add_parser("pr", help="Interact with Bitbucket pull requests.")
    pr_subparsers = pr_parser.add_subparsers(dest="pr_action", required=True)
    pr_subparsers.add_parser("list-open", help="List open pull requests.")

    pr_get = pr_subparsers.add_parser("get", help="Fetch one pull request.")
    pr_get.add_argument("pull_request_id", help="Pull request ID to fetch.")

    pr_commits = pr_subparsers.add_parser("commits", help="Fetch pull request commits.")
    pr_commits.add_argument("pull_request_id", help="Pull request ID to fetch commits for.")

    pr_diff = pr_subparsers.add_parser("diff", help="Fetch pull request diff.")
    pr_diff.add_argument("pull_request_id", help="Pull request ID to fetch diff for.")

    pr_discussion = pr_subparsers.add_parser("discussion", help="Fetch pull request discussion.")
    pr_discussion.add_argument("pull_request_id", help="Pull request ID to fetch discussion for.")

    pr_reviews = pr_subparsers.add_parser("reviews", help="Fetch pull request review-state activity.")
    pr_reviews.add_argument("pull_request_id", help="Pull request ID to fetch review state for.")

    pr_merge_checks = pr_subparsers.add_parser("merge-checks", help="Fetch pull request merge-check context.")
    pr_merge_checks.add_argument("pull_request_id", help="Pull request ID to fetch merge-check context for.")

    pr_status = pr_subparsers.add_parser("status", help="Fetch pull request build/status checks.")
    pr_status.add_argument("pull_request_id", help="Pull request ID to fetch status checks for.")

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

    if args.subcommand == "repo" and args.repo_action == "restrictions":
        raw = backend.get_repository_restrictions(config)
        return normalize.repository_restrictions(config.kind, raw)

    if args.subcommand == "issue" and args.issue_action == "list-open":
        raw = backend.list_open_issues(config)
        return normalize.issue_list(config.kind, raw)

    if args.subcommand == "issue" and args.issue_action == "get":
        raw = backend.get_issue(config, args.issue_id)
        return normalize.issue(config.kind, raw)

    if args.subcommand == "issue" and args.issue_action == "comments":
        raw = backend.get_issue_comments(config, args.issue_id)
        return normalize.issue_comments(config.kind, raw)

    if args.subcommand == "issue" and args.issue_action == "attachments":
        raw = backend.get_issue_attachments(config, args.issue_id)
        return normalize.issue_attachments(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "list-open":
        raw = backend.list_open_pull_requests(config)
        return normalize.pull_request_list(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "get":
        raw = backend.get_pull_request(config, args.pull_request_id)
        return normalize.pull_request(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "commits":
        raw = backend.get_pull_request_commits(config, args.pull_request_id)
        return normalize.pull_request_commits(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "diff":
        raw = backend.get_pull_request_diff(config, args.pull_request_id)
        return normalize.pull_request_diff(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "discussion":
        raw = backend.get_pull_request_discussion(config, args.pull_request_id)
        return normalize.pull_request_discussion(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "reviews":
        raw = backend.get_pull_request_reviews(config, args.pull_request_id)
        return normalize.pull_request_reviews(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "merge-checks":
        raw = backend.get_pull_request_merge_checks(config, args.pull_request_id)
        return normalize.pull_request_merge_checks(config.kind, raw)

    if args.subcommand == "pr" and args.pr_action == "status":
        raw = backend.get_pull_request_status(config, args.pull_request_id)
        return normalize.pull_request_status(config.kind, raw)

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
