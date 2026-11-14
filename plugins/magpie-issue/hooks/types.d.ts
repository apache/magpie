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

// Self-contained ambient declaration required by strict plugin validation.
// Companion TypeScript runtime definitions live in types.ts. Both type declarations
// must be kept in sync when modifying the state shape.

declare module 'claude-code' {
  interface PluginState {
    'magpie-issue': {
      duplicatePickerState: {
        targetIssue: number;
        targetTitle: string;
        targetAuthor?: string;
        candidates: Array<{
          issue_number: number;
          title: string;
          author: string;
          created_at?: string;
          similarity_score?: number;
          labels?: string[];
          excerpt?: string;
        }>;
        selectedKeptIssue: number | null;
        dismissedIssues: number[];
      } | null;
    };
  }
}
