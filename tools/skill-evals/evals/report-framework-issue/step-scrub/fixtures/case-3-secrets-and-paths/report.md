<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: framework repo (apache/magpie)
Type: bug

What's broken: `setup-isolated-setup-doctor` prints a raw Python
traceback instead of a clean "proxy unreachable" message when the
egress proxy is down.

Which layer: skills/setup-isolated-setup-doctor/

How to reproduce: stop the egress proxy, then run the doctor. It
raised:

  Traceback (most recent call last):
    File "/Users/jdoe/work/example-sec/.apache-magpie/tools/agent-isolation/doctor.py", line 88
  ConnectionError: failed to reach http://127.0.0.1:8899/health
  (the run had GH_TOKEN=ghp_A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8 exported)

Expected vs actual: expected a one-line diagnostic; got the
traceback.

Environment: Claude Code, macOS, sandbox on.
