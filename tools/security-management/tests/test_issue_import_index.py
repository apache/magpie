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

"""Local structured deduplication of already-fetched tracker bodies."""

from security_management.issue_import import dedup

THREAD = "19d2f402867e957e"


def issue(body: str, number: int = 7) -> dict:
    return {
        "number": number,
        "title": "Synthetic security report",
        "state": "OPEN",
        "url": f"https://example.invalid/issues/{number}",
        "body": body,
    }


def field(value: str) -> str:
    return "### Security mailing list thread\n\n" + value + "\n"


def test_backtick_wrapped_gmail_thread_is_tracked() -> None:
    body = field(f"No public archive URL — tracked privately on Gmail thread `{THREAD}`.")
    result = dedup.attribute_index([THREAD], [issue(body)])

    assert result["complete"]
    assert result["untracked"] == []
    assert [x["number"] for x in result["tracked"][THREAD]] == [7]
    assert "body" not in result["tracked"][THREAD][0]


def test_description_text_does_not_count_as_a_thread() -> None:
    body = (
        "### The issue description\n\n"
        f"This report mentions `{THREAD}` as an example.\n\n"
        "### Security mailing list thread\n\n"
        "_No response_\n"
    )
    result = dedup.attribute_index([THREAD], [issue(body)])

    assert result["tracked"] == {}
    assert result["untracked"] == [THREAD]


def test_longer_identifier_does_not_match_substring() -> None:
    body = field(f"No public archive URL — tracked privately on Gmail thread `{THREAD}999`.")
    result = dedup.attribute_index([THREAD], [issue(body)])

    assert result["tracked"] == {}
    assert result["untracked"] == [THREAD]


def test_root_message_id_matches_exactly() -> None:
    root = "<report@example.org>"
    body = field(
        f"No public archive URL — tracked privately on Gmail thread `{THREAD}`.\nRoot Message-ID: `{root}`"
    )
    result = dedup.attribute_index([root], [issue(body)])

    assert root in result["tracked"]
    assert result["untracked"] == []


def test_ambiguous_field_does_not_produce_false_negative() -> None:
    body = (
        field(f"No public archive URL — tracked privately on Gmail thread `{THREAD}`.")
        + "\n"
        + field("No public archive URL — tracked privately on Gmail thread `aaaaaa111111`.")
    )
    result = dedup.attribute_index(["bbbbbb222222"], [issue(body)])

    assert not result["complete"]
    assert result["untracked"] == []
    assert result["undecided"]


def test_full_index_does_not_produce_false_negative() -> None:
    result = dedup.attribute_index(
        ["bbbbbb222222"],
        [issue("_No response_", number=n) for n in range(3)],
        limit=3,
    )

    assert result["truncated"]
    assert not result["complete"]
    assert result["untracked"] == []


def test_dedup_index_cli(capsys, tmp_path) -> None:
    import json

    from security_management.cli import main

    ids_path = tmp_path / "thread-ids.json"
    issues_path = tmp_path / "issue-index.json"

    ids_path.write_text(json.dumps([THREAD]), encoding="utf-8")
    issues_path.write_text(
        json.dumps([issue(field(f"No public archive URL — tracked privately on Gmail thread `{THREAD}`."))]),
        encoding="utf-8",
    )

    code = main(
        [
            "issue-import",
            "dedup-index",
            "--thread-ids",
            str(ids_path),
            "--issues",
            str(issues_path),
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert code == 0
    assert result["complete"]
    assert THREAD in result["tracked"]
    assert result["untracked"] == []
    assert "body" not in json.dumps(result)


def test_dedup_index_cli_refuses_invalid_limit(capsys, tmp_path) -> None:
    import json

    from security_management.cli import main

    ids_path = tmp_path / "ids.json"
    issues_path = tmp_path / "issues.json"
    ids_path.write_text(json.dumps([THREAD]), encoding="utf-8")
    issues_path.write_text("[]", encoding="utf-8")

    code = main(
        [
            "issue-import",
            "dedup-index",
            "--thread-ids",
            str(ids_path),
            "--issues",
            str(issues_path),
            "--limit",
            "1001",
        ]
    )

    assert code != 0


def test_missing_issue_body_prevents_negative_result() -> None:
    record = {
        "number": 42,
        "title": "Synthetic tracker issue",
        "state": "OPEN",
        "url": "https://example.invalid/issues/42",
    }

    result = dedup.attribute_index([THREAD], [record])

    assert not result["complete"]
    assert result["untracked"] == []
    assert result["undecided"]


def test_archive_only_ponymail_identifier_matches() -> None:
    archive_id = "19d2f402867e957e"
    body = field(f"https://lists.apache.org/thread/{archive_id}")

    result = dedup.attribute_index([archive_id], [issue(body)])

    assert archive_id in result["tracked"]
    assert result["untracked"] == []


def test_secondary_gmail_thread_matches() -> None:
    secondary = "aaaaaa111111"
    body = field(
        f"No public archive URL — tracked privately on Gmail thread `{THREAD}`.\n"
        f"Relayed by security team via Gmail thread `{secondary}`."
    )

    result = dedup.attribute_index([secondary], [issue(body)])

    assert secondary in result["tracked"]


def test_ambiguous_identity_cannot_be_declared_untracked() -> None:
    body = field(
        "Relayed by security team via Gmail thread `aaaaaa111111`.\n"
        "Relayed by security team via Gmail thread `bbbbbb222222`."
    )

    result = dedup.attribute_index(["cccccc333333"], [issue(body)])

    assert not result["complete"]
    assert result["untracked"] == []
