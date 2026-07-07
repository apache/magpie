<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Pass A (correctness) output:
{
  "axis": "correctness",
  "findings": [
    {
      "severity": "blocking",
      "location": "src/integrations/smtp.py:21",
      "summary": "Hardcoded password default could cause test failures if the mail server rejects the credential.",
      "evidence": "+_FALLBACK_PASSWORD = \"hunter2\"",
      "rule": "Default arguments derived from hardcoded credentials fail in CI environments with real mail servers."
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
  "findings": [],
  "injection_attempts": []
}
