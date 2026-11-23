# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Terms never published before disclosure, matched case-insensitively.

Generated from tools/vcs/src/magpie_vcs/publication.py:DEFAULT_TERMS by
tools/dev/sync-forbidden-terms.py. Do not edit.
"""

DEFAULT_TERMS: tuple[tuple[str, str], ...] = (
    ("CVE id", r"\bCVE-\d{4}-\d{4,}\b"),
    ("CVE", r"\bCVEs?\b"),
    ("vulnerability", r"\bvulnerab(?:le|ility|ilities)\b"),
    ("security fix", r"\bsecurity[\s_-]+fix(?:es|ed)?\b"),
    ("advisory", r"\badvisor(?:y|ies)\b"),
    ("security@", r"\bsecurity@"),
    ("CVE-tool URL", r"cveprocess\.apache\.org"),
    ("exploit", r"\bexploit(?:s|able|ed)?\b"),
    ("SSRF", r"\bSSRF\b"),
    ("XSS", r"\bXSS\b"),
    ("CSRF", r"\bCSRF\b"),
    ("RCE", r"\bRCE\b"),
    ("SQL injection", r"\bSQL[\s_-]+injection\b"),
    ("path traversal", r"\b(?:path|directory)[\s_-]+traversal\b"),
    ("remote code execution", r"\b(?:remote|arbitrary)[\s_-]+code[\s_-]+execution\b"),
    ("privilege escalation", r"\bprivilege[\s_-]+escalation\b"),
    ("auth bypass", r"\b(?:auth|authentication|authorization)[\s_-]+bypass\b"),
    ("buffer overflow", r"\b(?:buffer|heap|stack)[\s_-]+overflow\b"),
    ("use-after-free", r"\buse[\s_-]+after[\s_-]+free\b"),
)
