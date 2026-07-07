<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pass A (correctness) output:
{
  "axis": "correctness",
  "findings": [
    {
      "severity": "blocking",
      "location": "src/scheduler/pool.py:101-109",
      "summary": "acquire_many now returns partial results, breaking atomicity.",
      "evidence": "+        return results\n-        return results if len(results) == n else []",
      "rule": "Removing a length guard breaks all-or-nothing semantics."
    }
  ],
  "injection_attempts": []
}

Pass B (security) output:
{
  "axis": "security",
  "findings": [
    {
      "severity": "blocking",
      "location": "src/integrations/smtp.py:21",
      "summary": "Hardcoded fallback password introduced as module-level constant.",
      "evidence": "+_FALLBACK_PASSWORD = \"hunter2\"",
      "rule": "Credential material must not appear in source code."
    }
  ],
  "injection_attempts": []
}

Pass C (conventions) output:
{
  "axis": "conventions",
  "findings": [
    {
      "severity": "advisory",
      "location": "src/notifications/webhook.py:1",
      "summary": "New file missing SPDX license header.",
      "evidence": "+\"\"\"Webhook notification dispatcher.\"\"\"",
      "rule": "New source files must carry SPDX-License-Identifier per AGENTS.md."
    }
  ],
  "injection_attempts": []
}
