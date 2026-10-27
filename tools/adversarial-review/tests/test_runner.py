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

import subprocess
import threading
import time
from pathlib import Path

from adversarial_review import runner
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
    r = run_one("antigravity", ctx(tmp_path, "antigravity"), 30, {"PATH": str(bin_dir)})
    assert r.status == "unavailable" and r.reason == "not on PATH"


def test_auth_failure_is_unavailable(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("agy", "import sys; sys.stderr.write('Error: please log in with `agy`\\n'); sys.exit(1)")
    r = run_one("antigravity", ctx(tmp_path, "antigravity"), 30, {"PATH": str(bin_dir)})
    assert r.status == "unavailable" and "log in" in r.reason


def test_other_failure_is_error(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("agy", "import sys; sys.stderr.write('segfault\\n'); sys.exit(139)")
    r = run_one("antigravity", ctx(tmp_path, "antigravity"), 30, {"PATH": str(bin_dir)})
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

    # Each stub marks that it started, then waits for the other's mark. Run one
    # after the other, the first stub waits in vain and records False. Both a
    # wall-clock bound and a fixed 3 s overlap window failed on a loaded machine
    # (pytest-xdist workers, pre-commit), where a stub can start seconds late.
    def waits_for(name: str, other: str, body: str) -> str:
        mine, theirs = (tmp_path / f"{n}.started" for n in (name, other))
        saw = tmp_path / f"{name}.saw"
        return (
            "import os, time\n"
            f"open({str(mine)!r}, 'w').close()\n"
            "deadline = time.time() + 20\n"
            f"while not os.path.exists({str(theirs)!r}) and time.time() < deadline: time.sleep(0.05)\n"
            f"open({str(saw)!r}, 'w').write(str(os.path.exists({str(theirs)!r})))\n" + body
        )

    make("codex", waits_for("codex", "antigravity", CODEX_OK))
    make(
        "agy",
        waits_for(
            "antigravity",
            "codex",
            "import json\nprint(json.dumps({'event': 'init', 'init': {'permission_mode': 'request-review'}}))\n"
            "print(json.dumps({'event': 'result', 'result': "
            "{'status': 'SUCCESS', 'response': json.dumps({'findings': []})}}))\n",
        ),
    )
    contexts = {n: ctx(tmp_path, n) for n in ("antigravity", "codex")}
    results = run_all(["antigravity", "codex"], contexts, 60, {"PATH": str(bin_dir)})
    assert [(r.reviewer, r.status) for r in results] == [("antigravity", "ok"), ("codex", "ok")]
    assert [(tmp_path / f"{n}.saw").read_text() for n in ("antigravity", "codex")] == ["True", "True"]


def test_one_timeout_does_not_block_the_others(stub_bin, tmp_path, monkeypatch):
    """antigravity times out only after codex has answered, so the result does not
    depend on how fast a stub starts (a wall-clock budget failed under the
    parallel pre-commit run, at 1 s and again at 5 s). antigravity is listed first:
    run one after the other, codex would never start and the wait would fail."""
    bin_dir, make = stub_bin
    make("codex", CODEX_OK)
    make("agy", "import time; time.sleep(60)")
    contexts = {n: ctx(tmp_path, n) for n in ("codex", "antigravity")}
    codex_answered = threading.Event()
    antigravity_saw_codex: list[bool] = []
    execute = runner._execute

    def fake_execute(argv, stdin, timeout_s, cwd, env):
        if Path(argv[0]).name == "agy":
            antigravity_saw_codex.append(codex_answered.wait(60))
            raise subprocess.TimeoutExpired(argv, timeout_s)
        try:
            return execute(argv, stdin, timeout_s, cwd, env)
        finally:
            codex_answered.set()

    monkeypatch.setattr(runner, "_execute", fake_execute)
    results = {r.reviewer: r for r in run_all(["antigravity", "codex"], contexts, 60, {"PATH": str(bin_dir)})}
    assert antigravity_saw_codex == [True]
    assert results["codex"].status == "ok" and results["antigravity"].status == "timeout"


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
    r = run_one("copilot", ctx(tmp_path, "copilot"), 10, {"PATH": str(bin_dir)})
    assert r.status == "ok" and len(r.findings) == 1
    # Well inside the timeout, which a held stdout would have run into.
    assert time.monotonic() - start < 8


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
    make("agy", "import time; time.sleep(60)")
    results = []
    worker = threading.Thread(
        target=lambda: results.append(
            run_one("antigravity", ctx(tmp_path, "antigravity"), 60, {"PATH": str(bin_dir)})
        )
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


def test_antigravity_unauthenticated_headless_run_is_unavailable(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    # A headless agy that never signed in exits with this instead of hanging.
    make("agy", "import sys; sys.stderr.write('Error: authentication required\\n'); sys.exit(1)")
    r = run_one("antigravity", ctx(tmp_path, "antigravity"), 30, {"PATH": str(bin_dir)})
    assert r.status == "unavailable"


def test_antigravity_answer_arrives_in_the_result_event(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make(
        "agy",
        "import json, sys\n"
        "msg = json.loads(sys.stdin.readline())['message']['content']\n"
        "finding = {'severity': 'low', 'file': 'app.py', 'line': 1, 'claim': 'got ' + msg, 'evidence': ''}\n"
        "print(json.dumps({'event': 'init', 'init': {'permission_mode': 'request-review'}}))\n"
        "print(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', "
        "'response': json.dumps({'findings': [finding]})}}))\n",
    )
    r = run_one("antigravity", ctx(tmp_path, "antigravity"), 30, {"PATH": str(bin_dir)})
    assert r.status == "ok" and r.findings[0].claim == "got THE PROMPT"


def test_antigravity_is_skipped_on_a_tree_with_workspace_hooks(stub_bin, tmp_path):
    bin_dir, make = stub_bin
    make("agy", "raise SystemExit('agy must not run on this tree')")
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "hooks.json").write_text("{}", encoding="utf-8")
    r = run_one("antigravity", ctx(tmp_path, "antigravity"), 30, {"PATH": str(bin_dir)})
    assert r.status == "skipped" and ".agents/hooks.json" in r.reason


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
