<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

From: b.researcher@otherdomain.com
Subject: SFTPHook filename parameter not validated

The filename argument passed to SFTPHook is not validated before use.
I was able to supply a value containing ../ sequences to escape the
intended directory. This seems related to how the hook constructs
remote paths.
