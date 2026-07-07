<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Base ref: origin/main (merge base def5678)
Files changed: 1 (1 modified)
Diff size: 12 additions, 4 deletions

Classified findings:
  correctness:
    - blocking | airflow/providers/http/hooks/http.py:94-101
      summary: ConnectionError caught but response is unbound on error path
      evidence: "        except requests.exceptions.ConnectionError as e:\n            self.log.error(\"Connection failed: %s\", e)\n        return response"
  security: no findings
  conventions: no findings
