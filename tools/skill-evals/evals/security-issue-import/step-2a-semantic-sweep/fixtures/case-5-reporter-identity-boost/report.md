<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: b.researcher@secfirm.io
Subject: Path traversal in Airflow HTTP operator allow_redirects parameter

I discovered a path traversal issue in the HTTP operator. When allow_redirects
is enabled and the remote server returns a redirect to a file:// URI containing
../ sequences, the operator follows it and reads arbitrary local files from the
Airflow worker. The issue is in airflow/providers/http/operators/http.py and
differs from the SFTP hook issue I reported previously.

Tested on Airflow 2.9.2 with a malicious HTTP server returning a 302 to
file:///etc/passwd via multiple ../ hops.
