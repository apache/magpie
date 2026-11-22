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

/**
 * Valid commit-attribution conventions per docs/setup/commit-attribution.md.
 */
export type AttributionConvention =
  | 'generated-by'
  | 'assisted-by'
  | 'co-authored-by'
  | 'none'
  | 'custom';

/**
 * Parsed configuration from a commit-attribution.toml file.
 */
export interface AttributionConfig {
  convention: AttributionConvention | 'contributor-choice';
  template?: string;
}

/**
 * Fully resolved attribution trailer and components.
 */
export interface ResolvedAttribution {
  convention: AttributionConvention;
  trailerText: string | null;
  trailerKey: string | null;
  trailerValue: string | null;
}

/**
 * Result of evaluating a shell command for unauthorized co-authorship.
 */
export interface CommitCommandEvaluation {
  blocked: boolean;
  reason?: string;
}

/**
 * Asynchronous file reader interface matching Claude Code $.fs.read.
 */
export type FsFileReader = (path: string) => Promise<string | null>;
