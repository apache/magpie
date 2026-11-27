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

export type ContributorLauncherSkill = 'activity-sweep' | 'nomination';

export interface ContributorCandidateItem {
  handle: string;
  displayName: string;
  prCount: number;
  reviewCount: number;
  window: string;
  note: string;
  updatedAt: string;
}

export interface StagedContributorAction {
  handle: string;
  skill: ContributorLauncherSkill;
  command: string;
  stagedAt: string;
}

export interface ContributorSweepState {
  items: ContributorCandidateItem[];
  selectedHandle: string | null;
  lastLaunchedAction: StagedContributorAction | null;
  syncError: string | null;
  queuePath?: string;
  updatedAt: string;
}

declare module 'claude-code' {
  interface PluginState {
    'magpie-contributor-growth': {
      contributorSweepState: ContributorSweepState | null;
    };
  }
}
