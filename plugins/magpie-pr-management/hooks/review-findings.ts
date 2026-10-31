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

import type {
  FindingAction,
  FindingSeverity,
  FindingSource,
  ParseFindingsResult,
  ReviewFinding,
  ReviewFindingsSummary,
} from './types.ts';

/**
 * Normalizes severity string to valid FindingSeverity, mapping common synonyms.
 * Records unrecognized severities in errors and defaults safely to 'minor'.
 */
export function normalizeSeverity(raw: unknown, errors?: string[]): FindingSeverity {
  if (typeof raw !== 'string') {
    return 'minor';
  }
  const clean = raw.trim().toLowerCase();
  switch (clean) {
    case 'blocking':
    case 'critical':
    case 'blocker':
      return 'blocking';
    case 'major':
    case 'high':
      return 'major';
    case 'minor':
    case 'low':
      return 'minor';
    case 'nit':
    case 'trivial':
    case 'info':
      return 'nit';
    default:
      if (errors) {
        errors.push(`Unrecognized severity '${raw}'; defaulted to 'minor'`);
      }
      return 'minor';
  }
}

/**
 * Normalizes file path replacing Windows backslashes with forward slashes
 * and stripping leading current-directory prefixes.
 */
export function normalizeFilePath(raw: unknown): string {
  if (typeof raw !== 'string') {
    return 'general';
  }
  let path = raw.trim().replace(/\\/g, '/');
  while (path.startsWith('./')) {
    path = path.slice(2);
  }
  return path || 'general';
}

/**
 * Normalizes line numbers into positive integers or null.
 * Strictly requires integer digit strings (matching /^\d+$/).
 * Prefixes or malformed strings are treated as unanchored (null) and recorded in errors.
 */
export function normalizeLine(raw: unknown, errors?: string[]): number | null {
  if (typeof raw === 'number') {
    return Number.isInteger(raw) && raw >= 1 ? raw : null;
  }
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed) return null;
    if (/^\d+$/.test(trimmed)) {
      const parsed = Number.parseInt(trimmed, 10);
      return parsed >= 1 ? parsed : null;
    }
    if (errors) {
      errors.push(`Malformed line number '${raw}'; treated as unanchored`);
    }
    return null;
  }
  return null;
}

/**
 * Normalizes source to primary, adversarial, or both.
 */
export function normalizeSource(raw: unknown): FindingSource {
  if (typeof raw !== 'string') {
    return 'primary';
  }
  const clean = raw.trim().toLowerCase();
  if (clean === 'adversarial' || clean === 'both' || clean === 'primary') {
    return clean;
  }
  return 'primary';
}

/**
 * Normalizes user action choice.
 * Missing or undefined defaults to 'accept' (matching picker 'A' default).
 * Unrecognized actions are recorded in errors and treated as 'skip' so an unwanted comment never posts.
 */
export function normalizeAction(raw: unknown, errors?: string[]): FindingAction {
  if (raw === undefined || raw === null) {
    return 'accept';
  }
  if (typeof raw !== 'string') {
    if (errors) {
      errors.push(`Invalid action type '${typeof raw}'; treated as 'skip'`);
    }
    return 'skip';
  }
  const clean = raw.trim().toLowerCase();
  if (clean === 'accept' || clean === 'skip' || clean === 'edit') {
    return clean;
  }
  if (errors) {
    errors.push(`Unrecognized action '${raw}'; treated as 'skip'`);
  }
  return 'skip';
}

/**
 * Checks whether a finding is anchored with a valid line number.
 * Matches render's filtering logic where finding.line >= 1.
 */
export function isAnchored(finding: { line?: number | null }): boolean {
  return finding.line !== null && finding.line !== undefined && finding.line >= 1;
}

/**
 * Computes summary counts across findings.
 */
export function calculateSummary(findings: readonly ReviewFinding[]): ReviewFindingsSummary {
  let blockingCount = 0;
  let majorCount = 0;
  let minorCount = 0;
  let nitCount = 0;
  let anchoredCount = 0;

  for (const finding of findings) {
    switch (finding.severity) {
      case 'blocking':
        blockingCount += 1;
        break;
      case 'major':
        majorCount += 1;
        break;
      case 'minor':
        minorCount += 1;
        break;
      case 'nit':
        nitCount += 1;
        break;
    }
    if (isAnchored(finding)) {
      anchoredCount += 1;
    }
  }

  const total = findings.length;
  const unanchoredCount = total - anchoredCount;

  return {
    blockingCount,
    majorCount,
    minorCount,
    nitCount,
    total,
    anchoredCount,
    unanchoredCount,
  };
}

/**
 * Converts finding action states into inline-picker keep answer format
 * compatible with code-review render keep parameter.
 * Numbers over exactly the anchored list that render reads.
 * Both 'accept' and 'edit' count as kept in the picker grammar.
 */
export function formatKeepAnswer(findings: readonly ReviewFinding[]): string {
  const anchored = findings.filter(isAnchored);

  if (anchored.length === 0) {
    return 'NONE';
  }

  const keptIndices: number[] = [];
  for (let i = 0; i < anchored.length; i += 1) {
    const item = anchored[i];
    if (item && (item.action === 'accept' || item.action === 'edit')) {
      keptIndices.push(i + 1);
    }
  }

  if (keptIndices.length === 0) {
    return 'NONE';
  }
  if (keptIndices.length === anchored.length) {
    return 'ALL';
  }

  return keptIndices.join(',');
}

/**
 * Serializes normalized review findings into the clean JSON structure
 * that code-review render consumes via its findings file parameter.
 */
export function serializeFindingsForRender(findings: readonly ReviewFinding[]): string {
  const payload = findings.map((f) => ({
    file: f.file,
    line: f.line,
    severity: f.severity,
    body: f.body,
    rule: f.rule,
    source: f.source,
    fixup: f.fixup,
  }));
  return JSON.stringify(payload, null, 2);
}

/**
 * Strips markdown code fences surrounding JSON payloads if present.
 * Matches code fences even if surrounded by conversational prose.
 */
function extractJsonPayload(text: string): string {
  const trimmed = text.trim();
  const fenceMatch = trimmed.match(/```(?:json)?\s*\n([\s\S]*?)\n```/i);
  if (fenceMatch && fenceMatch[1]) {
    return fenceMatch[1].trim();
  }
  return trimmed;
}

/**
 * Parses raw text or structured objects into validated review findings.
 * Handles markdown fences, field aliasing, unanchored items, and schema drift.
 */
export function parseFindings(input: string | unknown): ParseFindingsResult {
  const errors: string[] = [];
  const findings: ReviewFinding[] = [];

  if (input === null || input === undefined) {
    return {
      findings: [],
      errors: [],
      summary: calculateSummary([]),
    };
  }

  let rawData: unknown = input;

  if (typeof input === 'string') {
    const cleaned = extractJsonPayload(input);
    if (!cleaned) {
      return {
        findings: [],
        errors: [],
        summary: calculateSummary([]),
      };
    }
    try {
      rawData = JSON.parse(cleaned);
    } catch (err: any) {
      errors.push(`JSON parse error: ${err?.message || String(err)}`);
      return {
        findings: [],
        errors,
        summary: calculateSummary([]),
      };
    }
  }

  let rawList: unknown[] = [];
  if (Array.isArray(rawData)) {
    rawList = rawData;
  } else if (typeof rawData === 'object' && rawData !== null) {
    const dict = rawData as Record<string, unknown>;
    if (Array.isArray(dict.findings)) {
      rawList = dict.findings;
    } else if (Array.isArray(dict.items)) {
      rawList = dict.items;
    } else if (Array.isArray(dict.observations)) {
      rawList = dict.observations;
    } else if (dict.file || dict.explanation || dict.body || dict.severity) {
      rawList = [dict];
    }
  }

  for (let idx = 0; idx < rawList.length; idx += 1) {
    const rawItem = rawList[idx];
    if (typeof rawItem !== 'object' || rawItem === null) {
      errors.push(`Item at index ${idx} is not an object`);
      continue;
    }

    const item = rawItem as Record<string, unknown>;
    const file = normalizeFilePath(item.file ?? item.path ?? item.filename);
    const line = normalizeLine(item.line ?? item.lineNumber ?? item.line_number, errors);
    const severity = normalizeSeverity(item.severity ?? item.level, errors);
    const rawBody = item.body ?? item.explanation ?? item.suggestion ?? item.title ?? '';
    const body = String(rawBody).trim();
    const rawRule = item.rule ?? item.rule_id ?? item.category ?? '';
    const rule = String(rawRule).trim() || undefined;
    const rawFixup = item.fixup ?? item.suggestion_block ?? null;
    const fixup = typeof rawFixup === 'string' ? rawFixup.trimEnd() : null;
    const source = normalizeSource(item.source);
    const action = normalizeAction(item.action, errors);

    const stableId =
      typeof item.id === 'string' && item.id.trim().length > 0
        ? item.id.trim()
        : `finding-${findings.length + 1}`;

    findings.push({
      id: stableId,
      file,
      line,
      severity,
      body,
      rule,
      source,
      fixup,
      action,
      raw: rawItem,
    });
  }

  return {
    findings,
    errors,
    summary: calculateSummary(findings),
  };
}

/**
 * Event hook registration entry point for Claude Code mod.
 *
 * Note: In PR-1, session.start is a pass-through hook so that Claude Code
 * strict manifest validation (claude plugin validate --strict) and CI test
 * execution (claude plugin test) wire up the plugin module cleanly before
 * the interactive ui.render findings pane is introduced in PR-2.
 */
export function register(on: any): void {
  on('session.start', async (_$: any, e: any, next: any) => {
    if (typeof next === 'function') {
      return next(e);
    }
  });
}

export default register;
