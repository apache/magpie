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
from __future__ import annotations

import time
from pathlib import Path

from adversarial_review.backends import RunContext
from adversarial_review.runner import run_all, run_one

FINDING = {"severity": "high", "file": "app.py", "line": 2, "claim": "wrong value", "evidence": "return 2"}
CODEX_OK = (
    "import json, sys\n"
    "a = sys.argv\n"
    f"open(a[a.index('-o') + 1], 'w').write(json.dumps({{'findings': [{FINDING!r}]}}))\n"
)


def ctx(tmp_path: Path, name: str) -> RunContext:
    return RunContext(
        repo_dir=tmp_path,
        prompt="THE PROMPT",
        brief_path=tmp_path / "brief.md",
        schema_path=tmp_path / "schema.json",
        last_message_path=tmp_path / f"{name}-last.json",
    )


def test_ok(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("codex", CODEX_OK)
    r = run_one("codex", ctx(tmp_path, "codex"), 30, {"PATH": str(bin_dir)})
    assert r.status == "ok" and [f.claim for f in r.findings] == ["wrong value"]


def test_prompt_reaches_the_reviewer_on_stdin(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "claude",
        "import json, sys\n"
        "data = sys.stdin.read()\n"
        "finding = {'severity': 'low', 'file': 'app.py', 'line': 1, 'claim': 'got ' + data, 'evidence': ''}\n"
        "print(json.dumps({'is_error': False, 'result': json.dumps({'findings': [finding]})}))\n",
    )
    r = run_one("claude", ctx(tmp_path, "claude"), 30, {"PATH": str(bin_dir)})
    assert r.status == "ok" and r.findings[0].claim == "got THE PROMPT"


def test_missing_binary_is_unavailable(stub_bin, tmp_path):
    bin_dir, _ = stub_bin
    r = run_one("gemini", ctx(tmp_path, "gemini"), 30, {"PATH": str(bin_dir)})
    assert r.status == "unavailable" and r.reason == "not on PATH"


def test_auth_failure_is_unavailable(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("gemini", "import sys; sys.stderr.write('Error: please log in with `gemini auth`\\n'); sys.exit(1)")
    r = run_one("gemini", ctx(tmp_path, "gemini"), 30, {"PATH": str(bin_dir)})
    assert r.status == "unavailable" and "log in" in r.reason


def test_other_failure_is_error(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("gemini", "import sys; sys.stderr.write('segfault\\n'); sys.exit(139)")
    r = run_one("gemini", ctx(tmp_path, "gemini"), 30, {"PATH": str(bin_dir)})
    assert r.status == "error" and r.reason == "exit 139: segfault"


def test_malformed_reply_is_error_and_keeps_the_raw_text(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("copilot", "print('Looks fine to me.')")
    r = run_one("copilot", ctx(tmp_path, "copilot"), 30, {"PATH": str(bin_dir)})
    assert r.status == "error" and r.reason.startswith("malformed output:")
    assert "Looks fine to me." in r.raw


def test_timeout_kills_the_whole_process_group(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "copilot",
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"  # inherits stdout
        "time.sleep(60)\n",
    )
    start = time.monotonic()
    r = run_one("copilot", ctx(tmp_path, "copilot"), 1, {"PATH": str(bin_dir)})
    assert r.status == "timeout" and time.monotonic() - start < 10


def test_reviewers_run_in_parallel_and_keep_order(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("codex", "import time; time.sleep(1.5)\n" + CODEX_OK)
    make(
        "gemini",
        "import json, time; time.sleep(1.5)\nprint(json.dumps({'response': json.dumps({'findings': []})}))\n",
    )
    contexts = {n: ctx(tmp_path, n) for n in ("gemini", "codex")}
    start = time.monotonic()
    results = run_all(["gemini", "codex"], contexts, 30, {"PATH": str(bin_dir)})
    assert time.monotonic() - start < 2.8
    assert [(r.reviewer, r.status) for r in results] == [("gemini", "ok"), ("codex", "ok")]


def test_one_timeout_does_not_block_the_others(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("codex", CODEX_OK)
    make("gemini", "import time; time.sleep(60)")
    contexts = {n: ctx(tmp_path, n) for n in ("codex", "gemini")}
    results = {r.reviewer: r for r in run_all(["codex", "gemini"], contexts, 1, {"PATH": str(bin_dir)})}
    assert results["codex"].status == "ok" and results["gemini"].status == "timeout"


def test_a_finished_answer_is_kept_when_a_helper_lingers(stub_bin, tmp_path):
    """Review finding: with pipes, a helper holding stdout turned a finished
    reply into a timeout. The reviewer's own exit must end the wait."""
    bin_dir, make = stub_bin
    make(
        "copilot",
        "import json, subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"print(json.dumps({{'findings': [{FINDING!r}]}}))\n",
    )
    start = time.monotonic()
    r = run_one("copilot", ctx(tmp_path, "copilot"), 5, {"PATH": str(bin_dir)})
    assert r.status == "ok" and len(r.findings) == 1
    assert time.monotonic() - start < 4


def test_timeout_is_bounded_even_when_a_helper_escapes_the_group(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "copilot",
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import os, time; os.setsid(); time.sleep(60)'])\n"
        "time.sleep(60)\n",
    )
    start = time.monotonic()
    r = run_one("copilot", ctx(tmp_path, "copilot"), 1, {"PATH": str(bin_dir)})
    assert r.status == "timeout" and time.monotonic() - start < 10


def test_terminate_all_kills_running_reviewers(stub_bin, tmp_path):
    import threading

    from adversarial_review.runner import terminate_all

    bin_dir, make = stub_bin
    make("gemini", "import time; time.sleep(60)")
    results = []
    worker = threading.Thread(
        target=lambda: results.append(run_one("gemini", ctx(tmp_path, "gemini"), 60, {"PATH": str(bin_dir)}))
    )
    start = time.monotonic()
    worker.start()
    time.sleep(1)
    terminate_all()
    worker.join(timeout=10)
    assert results and results[0].status == "error" and time.monotonic() - start < 10


def test_auth_words_in_stdout_are_not_an_auth_failure(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "claude",
        "import sys\nprint('the login endpoint lacks a check; error at line 401 in credentials.json')\n"
        "sys.stderr.write('crashed\\n'); sys.exit(1)\n",
    )
    r = run_one("claude", ctx(tmp_path, "claude"), 30, {"PATH": str(bin_dir)})
    assert r.status == "error"


def test_gemini_auth_method_message_is_unavailable(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "gemini",
        "import sys; sys.stderr.write('Please set an Auth method in settings.json\\n'); sys.exit(41)",
    )
    r = run_one("gemini", ctx(tmp_path, "gemini"), 30, {"PATH": str(bin_dir)})
    assert r.status == "unavailable"


def test_a_bad_finding_does_not_cost_the_good_ones(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "copilot",
        "import json\n"
        f"print(json.dumps({{'findings': [{FINDING!r}, {{'severity': 'high', 'claim': ''}}]}}))\n",
    )
    r = run_one("copilot", ctx(tmp_path, "copilot"), 30, {"PATH": str(bin_dir)})
    assert r.status == "ok" and len(r.findings) == 1
    assert r.reason.startswith("skipped 1 malformed finding(s)") and r.raw


def test_paths_are_normalised_against_the_repo(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    make(
        "copilot",
        f"import json\nprint(json.dumps({{'findings': [{{**{FINDING!r}, 'file': './app.py'}}]}}))\n",
    )
    r = run_one("copilot", ctx(tmp_path, "copilot"), 30, {"PATH": str(bin_dir)})
    assert r.findings[0].file == "app.py"
