<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

A Magpie skill errored with `config file not found`. Investigation shows the
adopter's own `.apache-magpie-overrides/tools/cve-tool-vulnogram/cve-json-config.toml`
was never created in this repo — the adopter skipped that setup step. The
framework code resolves the documented default path correctly; there is simply
no config file where the adopter should have placed one. Creating it in the
adopter repo resolves the error.
