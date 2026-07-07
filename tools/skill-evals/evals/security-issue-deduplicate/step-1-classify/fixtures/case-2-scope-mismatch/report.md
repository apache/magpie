<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

gh issue view output for issue #67 (drop tracker):

number: 67
title: "HTTP Provider: SSRF via HttpOperator redirect"
state: OPEN
labels: providers
body: |
  ### The issue description

  The HttpOperator follows redirects to file:// and internal URLs when
  redirect_filter_func is not set, allowing SSRF via provider config.

  ### Reporter credited as

  Bob Researcher

  ### Severity

  Unknown
