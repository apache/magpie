<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

A framework helper crashed during a run. The pre-flight drift check reported
that the local snapshot is behind the committed pin, and a quick look at
`apache/magpie` `main` shows the helper was already rewritten to handle this
case two weeks ago. The crash only happens on the stale snapshot on this
machine.
