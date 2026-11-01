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

declare module 'claude-code' {
  interface PluginState {
    'magpie-pr-management': {
      reviewFindingsState: {
        prNumber?: number;
        prTitle?: string;
        findings: Array<{
          id: string;
          file: string;
          line?: number | null;
          severity: 'blocking' | 'major' | 'minor' | 'nit';
          body: string;
          rule?: string;
          source?: 'primary' | 'adversarial' | 'both';
          fixup?: string | null;
          action: 'accept' | 'skip' | 'edit';
          raw?: unknown;
        }>;
        summary: {
          blockingCount: number;
          majorCount: number;
          minorCount: number;
          nitCount: number;
          total: number;
          anchoredCount: number;
          unanchoredCount: number;
        };
        selectedIndex: number;
      } | null;
    };
  }
}
