<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Login argument: ../../etc/passwd
Target: committer
Upstream: apache/example-project

Login validation: the supplied login "../../etc/passwd" does not match
the required GitHub username pattern ^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$.
The login contains path traversal characters and must be rejected before
any API call or URL construction.
