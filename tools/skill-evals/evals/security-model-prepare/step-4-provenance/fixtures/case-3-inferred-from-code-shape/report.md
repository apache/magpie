<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Draft claim: "Configuration files are treated as trusted input; the
library does not defend against a hostile configuration."

Evidence: none in the documentation. The drafter read `config.c` and
observed that values are used without bounds checks, and that no test
exercises a malformed configuration. No maintainer has been asked.
