<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Write lock.** Before this step's first write, read [write-lock.md](write-lock.md) and follow it:
take this skill's write lock, post nothing while another run holds it, re-read each item just before writing it,
and release the lock after the recap and when a post fails.
