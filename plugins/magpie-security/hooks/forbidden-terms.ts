// SPDX-License-Identifier: Apache-2.0
//
// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements.  See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership.  The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License.  You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied.  See the License for the
// specific language governing permissions and limitations
// under the License.

// Generated from tools/vcs/src/magpie_vcs/publication.py:DEFAULT_TERMS. Do not edit.

export interface CanonicalForbiddenTerm {
  name: string;
  pattern: string;
  flags: string;
}

export const CANONICAL_FORBIDDEN_TERMS: ReadonlyArray<CanonicalForbiddenTerm> = [

  { name: "CVE id", pattern: "\\bCVE-\\d{4}-\\d{4,}\\b", flags: "i" },
  { name: "CVE", pattern: "\\bCVEs?\\b", flags: "i" },
  { name: "vulnerability", pattern: "\\bvulnerab(?:le|ility|ilities)\\b", flags: "i" },
  { name: "security fix", pattern: "\\bsecurity[\\s_-]+fix(?:es|ed)?\\b", flags: "i" },
  { name: "advisory", pattern: "\\badvisor(?:y|ies)\\b", flags: "i" },
  { name: "security@", pattern: "\\bsecurity@", flags: "i" },
  { name: "CVE-tool URL", pattern: "cveprocess\\.apache\\.org", flags: "i" },
  { name: "exploit", pattern: "\\bexploit(?:s|able|ed)?\\b", flags: "i" },
  { name: "SSRF", pattern: "\\bSSRF\\b", flags: "i" },
  { name: "XSS", pattern: "\\bXSS\\b", flags: "i" },
  { name: "CSRF", pattern: "\\bCSRF\\b", flags: "i" },
  { name: "RCE", pattern: "\\bRCE\\b", flags: "i" },
  { name: "SQL injection", pattern: "\\bSQL[\\s_-]+injection\\b", flags: "i" },
  { name: "path traversal", pattern: "\\b(?:path|directory)[\\s_-]+traversal\\b", flags: "i" },
  { name: "remote code execution", pattern: "\\b(?:remote|arbitrary)[\\s_-]+code[\\s_-]+execution\\b", flags: "i" },
  { name: "privilege escalation", pattern: "\\bprivilege[\\s_-]+escalation\\b", flags: "i" },
  { name: "auth bypass", pattern: "\\b(?:auth|authentication|authorization)[\\s_-]+bypass\\b", flags: "i" },
  { name: "buffer overflow", pattern: "\\b(?:buffer|heap|stack)[\\s_-]+overflow\\b", flags: "i" },
  { name: "use-after-free", pattern: "\\buse[\\s_-]+after[\\s_-]+free\\b", flags: "i" },
];
