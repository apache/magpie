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

import { atom, read, update } from 'claude-code';
import type {
  FindingAction,
  FindingSeverity,
  FindingSource,
  ParseFindingsResult,
  ReviewFinding,
  ReviewFindingsState,
  ReviewFindingsSummary,
} from './types.ts';

export const reviewFindingsState = atom(
  { plugin: 'magpie-pr-management', key: 'reviewFindingsState' },
  null as ReviewFindingsState | null
);

let currentFindingsState: ReviewFindingsState | null = null;

export async function setReviewFindingsState(
  $: any,
  state: ReviewFindingsState | null
): Promise<void> {
  currentFindingsState = state;
  try {
    await update($, reviewFindingsState, () => state);
  } catch {
    // In test harness where atom state map is not bound to test runner $, module state serves as fallback
  }
  try {
    $.ui.invalidate('ui.render');
  } catch {
    // In environments where invalidate is not available, state update is sufficient
  }
}

export async function getReviewFindingsState(
  $: any
): Promise<ReviewFindingsState | null> {
  try {
    const val = await read($, reviewFindingsState);
    return val ?? currentFindingsState;
  } catch {
    return currentFindingsState;
  }
}

export interface SeverityBadgeSpec {
  label: string;
  color: 'error' | 'warning' | 'dim' | 'info';
  bold: boolean;
}

export function formatSeverityBadge(severity: FindingSeverity): SeverityBadgeSpec {
  switch (severity) {
    case 'blocking':
      return { label: '[BLOCKING]', color: 'error', bold: true };
    case 'major':
      return { label: '[MAJOR]', color: 'error', bold: false };
    case 'minor':
      return { label: '[MINOR]', color: 'warning', bold: false };
    case 'nit':
      return { label: '[NIT]', color: 'dim', bold: false };
  }
}

export interface ActionIndicatorSpec {
  label: string;
  color: 'success' | 'dim' | 'info';
  bold: boolean;
}

export function formatActionIndicator(action: FindingAction): ActionIndicatorSpec {
  switch (action) {
    case 'accept':
      return { label: '[x] Accept', color: 'success', bold: true };
    case 'skip':
      return { label: '[ ] Skip', color: 'dim', bold: false };
    case 'edit':
      return { label: '[E] Edit', color: 'info', bold: true };
  }
}

export function truncateFilePath(filePath: string, maxLength = 36): string {
  if (filePath.length <= maxLength) {
    return filePath;
  }
  const parts = filePath.split('/');
  if (parts.length <= 2) {
    return `...${filePath.slice(-(maxLength - 3))}`;
  }
  const last = parts[parts.length - 1];
  const prev = parts[parts.length - 2];
  const candidate = `.../${prev}/${last}`;
  if (candidate.length <= maxLength) {
    return candidate;
  }
  return `...${last.slice(-(maxLength - 3))}`;
}

export function formatFindingsTerminalFallback(state: ReviewFindingsState): string {
  const findings = state.findings || [];
  if (findings.length === 0) {
    return 'No review findings to display.';
  }

  const lines: string[] = [];
  const prPrefix = state.prNumber ? `PR #${state.prNumber} ` : '';
  lines.push(
    `${prPrefix}Review findings (${state.summary.anchoredCount} inline, ${state.summary.unanchoredCount} general):`
  );

  const anchored = findings.filter(isAnchored);
  if (anchored.length > 0) {
    lines.push('');
    lines.push('  Proposed inline comments:');
    for (let i = 0; i < anchored.length; i += 1) {
      const f = anchored[i];
      const actionLabel = f.action === 'accept' ? '[x]' : f.action === 'edit' ? '[E]' : '[ ]';
      const badge = formatSeverityBadge(f.severity).label;
      const pathStr = `${f.file}:${f.line}`;
      const desc = f.rule ? `${f.rule} \u2014 ${f.body}` : f.body;
      lines.push(`    ${actionLabel} ${i + 1}. ${badge} ${pathStr} \u2014 ${desc}`);
    }
  }

  const unanchored = findings.filter((f) => !isAnchored(f));
  if (unanchored.length > 0) {
    lines.push('');
    lines.push('  General observations (unanchored):');
    for (const f of unanchored) {
      const actionLabel = f.action === 'accept' ? '[x]' : f.action === 'edit' ? '[E]' : '[ ]';
      const badge = formatSeverityBadge(f.severity).label;
      const desc = f.rule ? `${f.rule} \u2014 ${f.body}` : f.body;
      lines.push(`    ${actionLabel} \u2022 ${badge} ${f.file} \u2014 ${desc}`);
    }
  }

  lines.push('');
  const s = state.summary;
  lines.push(
    `  Summary: ${s.blockingCount} blocking, ${s.majorCount} major, ${s.minorCount} minor, ${s.nitCount} nit (${s.total} total)`
  );

  return lines.join('\n');
}

export function renderFindingsPane($: any, e: any, state: ReviewFindingsState): any {
  const findings = state.findings || [];
  if (findings.length === 0) {
    return null;
  }

  let Box: any;
  let Text: any;
  try {
    const resolved = $.ui.resolve(e);
    Box = resolved.Box;
    Text = resolved.Text;
  } catch {
    return null;
  }
  if (!Box || !Text) {
    return null;
  }

  const anchored = findings.filter(isAnchored);
  const unanchored = findings.filter((f) => !isAnchored(f));
  const s = state.summary;

  const headerChildren = [
    Text({
      children: [
        state.prNumber ? `PR #${state.prNumber}: Review Findings` : 'Review Findings',
      ],
      bold: true,
    }),
    Text({
      children: [
        `(${s.anchoredCount} inline, ${s.unanchoredCount} general \u00B7 ${s.blockingCount} blocking, ${s.majorCount} major, ${s.minorCount} minor, ${s.nitCount} nit)`,
      ],
      color: 'dim',
    }),
  ];

  const contentBoxes: any[] = [
    Box({
      flexDirection: 'column',
      paddingBottom: 1,
      children: headerChildren,
    }),
  ];

  const MAX_VISIBLE = 10;
  let visibleCount = 0;

  if (anchored.length > 0) {
    const anchoredRows: any[] = [
      Text({
        children: ['Proposed inline comments:'],
        bold: true,
        color: 'info',
      }),
    ];

    for (let i = 0; i < anchored.length && visibleCount < MAX_VISIBLE; i += 1) {
      const f = anchored[i];
      visibleCount += 1;
      const actionSpec = formatActionIndicator(f.action);
      const severitySpec = formatSeverityBadge(f.severity);
      const shortPath = truncateFilePath(f.file);

      anchoredRows.push(
        Box({
          children: [
            Text({
              children: [`  ${actionSpec.label.slice(0, 3)} `],
              color: actionSpec.color,
              bold: actionSpec.bold,
            }),
            Text({
              children: [`${i + 1}. `],
              color: 'dim',
            }),
            Text({
              children: [`${severitySpec.label} `],
              color: severitySpec.color,
              bold: severitySpec.bold,
            }),
            Text({
              children: [`${shortPath}:${f.line} `],
              bold: true,
            }),
            Text({
              children: [`\u2014 ${f.rule || f.body}`],
              color: 'dim',
            }),
          ],
        })
      );
    }

    contentBoxes.push(
      Box({
        flexDirection: 'column',
        paddingBottom: unanchored.length > 0 ? 1 : 0,
        children: anchoredRows,
      })
    );
  }

  if (unanchored.length > 0 && visibleCount < MAX_VISIBLE) {
    const unanchoredRows: any[] = [
      Text({
        children: ['General observations (unanchored):'],
        bold: true,
        color: 'info',
      }),
    ];

    for (let i = 0; i < unanchored.length && visibleCount < MAX_VISIBLE; i += 1) {
      const f = unanchored[i];
      visibleCount += 1;
      const actionSpec = formatActionIndicator(f.action);
      const severitySpec = formatSeverityBadge(f.severity);
      const shortPath = truncateFilePath(f.file);

      unanchoredRows.push(
        Box({
          children: [
            Text({
              children: [`  ${actionSpec.label.slice(0, 3)} `],
              color: actionSpec.color,
              bold: actionSpec.bold,
            }),
            Text({
              children: ['\u2022 '],
              color: 'dim',
            }),
            Text({
              children: [`${severitySpec.label} `],
              color: severitySpec.color,
              bold: severitySpec.bold,
            }),
            Text({
              children: [`${shortPath} `],
              bold: true,
            }),
            Text({
              children: [`\u2014 ${f.rule || f.body}`],
              color: 'dim',
            }),
          ],
        })
      );
    }

    contentBoxes.push(
      Box({
        flexDirection: 'column',
        children: unanchoredRows,
      })
    );
  }

  if (findings.length > visibleCount) {
    contentBoxes.push(
      Box({
        paddingTop: 1,
        children: [
          Text({
            children: [
              `... showing ${visibleCount} of ${findings.length} findings (scroll or select in PR-3)`,
            ],
            color: 'dim',
          }),
        ],
      })
    );
  }

  return Box({
    flexDirection: 'column',
    padding: 1,
    borderStyle: 'round',
    children: contentBoxes,
  });
}

/**
 * Normalizes severity string to valid FindingSeverity, mapping common synonyms.
 * Records unrecognized severities in errors and defaults safely to 'minor'.
 */
export function normalizeSeverity(raw: unknown, errors?: string[]): FindingSeverity {
  if (typeof raw !== 'string') {
    if (raw !== undefined && raw !== null && errors) {
      errors.push(`Invalid severity type '${typeof raw}'; defaulted to 'minor'`);
    }
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
    if (Number.isInteger(raw) && raw >= 1) return raw;
    if (raw !== 0 && errors) {
      errors.push(`Malformed line number '${raw}'; treated as unanchored`);
    }
    return null;
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

// Alias keys the parser accepts that render never reads; the serialised
// file carries the canonical key instead, so the two cannot disagree.
const ALIAS_KEYS = ['path', 'filename', 'lineNumber', 'line_number', 'level', 'action'];

/**
 * Serializes normalized review findings into the findings file that
 * code-review render reads, in render's own field names.
 *
 * Every field of the original finding is kept (explanation, rule_id,
 * quoted_rule, excerpt, suggestion_block, side, reviewers, ...), and only
 * the normalised file, line and severity override it. A finding that
 * arrived with only the parser's aliases (body, rule) gets render's names
 * for them. Render anchors on a truthy `line`, so with `line` normalised to
 * an integer >= 1 or null, its numbering over this file is formatKeepAnswer's.
 */
export function serializeFindingsForRender(findings: readonly ReviewFinding[]): string {
  const payload = findings.map((f) => {
    const raw = f.raw;
    const base: Record<string, unknown> =
      typeof raw === 'object' && raw !== null && !Array.isArray(raw)
        ? { ...(raw as Record<string, unknown>) }
        : {};
    for (const key of ALIAS_KEYS) {
      delete base[key];
    }
    if (base.explanation === undefined && base.suggestion === undefined && f.body) {
      base.explanation = f.body;
    }
    if (base.rule_id === undefined && base.category === undefined && f.rule) {
      base.rule_id = f.rule;
    }
    return { ...base, file: f.file, line: f.line, severity: f.severity };
  });
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
 * Registers:
 * - session.start: pass-through lifecycle hook for module initialization.
 * - ui.render (Pane): renders the interactive review findings pane when state is populated.
 */
export async function handleRenderPane($: any, e: any, next: any): Promise<any> {
  let state: ReviewFindingsState | null = null;
  try {
    state = await read($, reviewFindingsState);
  } catch {
    state = null;
  }
  if (!state) {
    state = currentFindingsState;
  }

  if (!state || !state.findings || state.findings.length === 0) {
    if (typeof next === 'function') {
      return next(e);
    }
    return;
  }

  try {
    const rendered = renderFindingsPane($, e, state);
    if (rendered) {
      return rendered;
    }
  } catch {
    // Fallback cleanly to next hook
  }

  if (typeof next === 'function') {
    return next(e);
  }
}

/**
 * Event hook registration entry point for Claude Code mod.
 *
 * Registers:
 * - session.start: pass-through lifecycle hook for module initialization and fixture hydration.
 * - ui.render (AbovePrompt): renders the interactive review findings pane when state is populated.
 */
export function register(on: any): void {
  on('session.start', async ($: any, e: any, next: any) => {
    if (e && e.findings) {
      try {
        const parsed = parseFindings(e.findings);
        await update($, reviewFindingsState, () => ({
          prNumber: e.prNumber,
          prTitle: e.prTitle,
          findings: parsed.findings,
          summary: parsed.summary,
          selectedIndex: 0,
        }));
      } catch {
        // Safe no-op on parsing error
      }
    }
    if (typeof next === 'function') {
      return next(e);
    }
  });

  on('ui.render', { component: 'Pane' }, handleRenderPane);
  on('ui.render', { component: 'AbovePrompt' }, handleRenderPane);
}

export default register;
