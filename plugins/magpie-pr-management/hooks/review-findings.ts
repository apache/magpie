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

export interface CuratedFindingsPayload {
  schema_version: 1;
  pr?: number | null;
  source_sha256?: string | null;
  invalidated?: boolean;
  findings: Record<string, unknown>[];
}

/**
 * Computes deterministic SHA-256 hex digest of UTF-8 string in pure JS/TS
 * without external module imports, adhering to mod import boundaries.
 */
export function computeFindingsHash(content: string): string {
  const ascii = unescape(encodeURIComponent(content));
  const mathPow = Math.pow;
  const maxWord = mathPow(2, 32);
  const words: number[] = [];
  const asciiBitLength = ascii.length * 8;
  const hash: number[] = [];
  const k: number[] = [];
  let primeCounter = 0;
  const isComposite: Record<number, number> = {};

  for (let candidate = 2; primeCounter < 64; candidate += 1) {
    if (!isComposite[candidate]) {
      for (let i = 0; i < 313; i += candidate) {
        isComposite[i] = candidate;
      }
      hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0;
      k[primeCounter] = (mathPow(candidate, 1 / 3) * maxWord) | 0;
      primeCounter += 1;
    }
  }

  let padded = ascii + '\x80';
  while (padded.length % 64 !== 56) {
    padded += '\x00';
  }

  for (let i = 0; i < padded.length; i += 1) {
    const code = padded.charCodeAt(i);
    words[i >> 2] |= code << ((3 - (i % 4)) * 8);
  }

  words[words.length] = (asciiBitLength / maxWord) | 0;
  words[words.length] = asciiBitLength;

  for (let j = 0; j < words.length; ) {
    const w = words.slice(j, (j += 16));
    const oldHash = [...hash];
    for (let i = 0; i < 64; i += 1) {
      const w15 = w[i - 15];
      const w2 = w[i - 2];
      const a = hash[0];
      const e = hash[4];
      const s1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const ch = (e & hash[5]) ^ (~e & hash[6]);
      const s0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const maj = (a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]);

      const wi =
        i < 16
          ? w[i]
          : ((w[i - 16] +
              (((w15 >>> 7) | (w15 << 25)) ^ ((w15 >>> 18) | (w15 << 14)) ^ (w15 >>> 3)) +
              w[i - 7] +
              (((w2 >>> 17) | (w2 << 15)) ^ ((w2 >>> 19) | (w2 << 13)) ^ (w2 >>> 10))) |
              0);
      w[i] = wi;

      const temp1 = (hash[7] + s1 + ch + k[i] + wi) | 0;
      const temp2 = (s0 + maj) | 0;

      hash[7] = hash[6];
      hash[6] = hash[5];
      hash[5] = hash[4];
      hash[4] = (hash[3] + temp1) | 0;
      hash[3] = hash[2];
      hash[2] = hash[1];
      hash[1] = hash[0];
      hash[0] = (temp1 + temp2) | 0;
    }
    for (let i = 0; i < 8; i += 1) {
      hash[i] = (hash[i] + oldHash[i]) | 0;
    }
  }

  let result = '';
  for (let i = 0; i < 8; i += 1) {
    for (let j = 3; j >= 0; j -= 1) {
      const b = (hash[i] >>> (j * 8)) & 255;
      result += (b < 16 ? '0' : '') + b.toString(16);
    }
  }
  return result;
}

/**
 * Validates whether a curated findings sidecar JSON content matches the current
 * active PR number and source findings file content without being invalidated.
 */
export function isCuratedSidecarValid(
  curatedJsonContent: string | null | undefined,
  prNumber: number | null | undefined,
  sourceFileContent: string
): boolean {
  if (!curatedJsonContent) return false;
  try {
    const parsed = JSON.parse(curatedJsonContent);
    if (!parsed || typeof parsed !== 'object') return false;
    if (parsed.invalidated === true) return false;
    if (
      parsed.pr !== undefined &&
      parsed.pr !== null &&
      prNumber !== undefined &&
      prNumber !== null
    ) {
      if (Number(parsed.pr) !== Number(prNumber)) return false;
    }
    const expectedHash = computeFindingsHash(sourceFileContent);
    if (parsed.source_sha256 && parsed.source_sha256 !== expectedHash) {
      return false;
    }
    return Array.isArray(parsed.findings);
  } catch {
    return false;
  }
}

export const reviewFindingsState = atom(
  { plugin: 'magpie-pr-management', key: 'reviewFindingsState' },
  null as ReviewFindingsState | null
);

export async function setReviewFindingsState(
  $: any,
  state: ReviewFindingsState | null
): Promise<void> {
  await update($, reviewFindingsState, () => state);
  try {
    $.ui.invalidate('ui.render');
  } catch {
    // UI invalidation optional in non-interactive / headless contexts
  }
}

export async function getReviewFindingsState(
  $: any
): Promise<ReviewFindingsState | null> {
  try {
    return (await read($, reviewFindingsState)) ?? null;
  } catch {
    return null;
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

export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 3))}...`;
}

export function sanitizeFindingText(input: string | unknown): string {
  if (typeof input !== 'string' || !input) {
    return '';
  }
  return input
    .replace(/\x1b\][^\x07\x1b]*(\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '');
}

export function formatFindingDescription(
  rule?: string,
  body?: string,
  maxLength = 80
): string {
  const cleanRule = sanitizeFindingText(rule || '').trim();
  const cleanBody = sanitizeFindingText(body || '').trim();
  let full = '';
  if (cleanRule && cleanBody) {
    full = `${cleanRule} \u2014 ${cleanBody}`;
  } else {
    full = cleanRule || cleanBody || '';
  }
  return truncateText(full, maxLength);
}

export function renderFindingsPane($: any, e: any, state: ReviewFindingsState): any {
  const findings = state.findings || [];
  if (findings.length === 0) {
    return null;
  }

  let Box: any;
  let Text: any;
  let Button: any;
  try {
    const resolved = $.ui.resolve(e);
    Box = resolved.Box;
    Text = resolved.Text;
    Button = typeof resolved.Button === 'function' ? resolved.Button : undefined;
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
      const cleanPath = sanitizeFindingText(f.file);
      const shortPath = truncateFilePath(cleanPath);
      const desc = formatFindingDescription(f.rule, f.body, 80);

      const globalIdx = findings.indexOf(f);
      const isSelected = globalIdx === state.selectedIndex;
      const cursor = isSelected ? '> ' : '  ';
      const actionNode = Button
        ? Button({
            key: `toggle-${i + 1}`,
            label: actionSpec.label.slice(0, 3),
            onPress: async () => {
              const updated = toggleFindingActionInState(state, globalIdx);
              await updateAndSyncReviewFindingsState($, updated);
            },
          })
        : Text({
            children: [actionSpec.label.slice(0, 3)],
            color: actionSpec.color,
            bold: actionSpec.bold,
          });

      anchoredRows.push(
        Box({
          children: [
            Text({
              children: [cursor],
              color: isSelected ? 'info' : 'dim',
              bold: isSelected,
            }),
            actionNode,
            Text({
              children: [` ${i + 1}. `],
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
              children: [`\u2014 ${desc}`],
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
      const cleanPath = sanitizeFindingText(f.file);
      const shortPath = truncateFilePath(cleanPath);
      const desc = formatFindingDescription(f.rule, f.body, 80);

      const globalIdx = findings.indexOf(f);
      const isSelected = globalIdx === state.selectedIndex;
      const cursor = isSelected ? '> ' : '  ';
      const actionNode = Button
        ? Button({
            key: `toggle-general-${unanchored.indexOf(f) + 1}`,
            label: actionSpec.label.slice(0, 3),
            onPress: async () => {
              const updated = toggleFindingActionInState(state, globalIdx);
              await updateAndSyncReviewFindingsState($, updated);
            },
          })
        : Text({
            children: [actionSpec.label.slice(0, 3)],
            color: actionSpec.color,
            bold: actionSpec.bold,
          });

      unanchoredRows.push(
        Box({
          children: [
            Text({
              children: [cursor],
              color: isSelected ? 'info' : 'dim',
              bold: isSelected,
            }),
            actionNode,
            Text({
              children: [' \u2022 '],
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
              children: [`\u2014 ${desc}`],
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
              `... showing ${visibleCount} of ${findings.length} findings`,
            ],
            color: 'dim',
          }),
        ],
      })
    );
  }

  if (Button) {
    contentBoxes.push(
      Box({
        paddingTop: 1,
        children: [
          Button({
            key: 'accept-all',
            label: '[All]',
            onPress: async () => {
              const updated = setBulkActionInState(state, 'accept');
              await updateAndSyncReviewFindingsState($, updated);
            },
          }),
          Text({ children: [' '] }),
          Button({
            key: 'skip-all',
            label: '[None]',
            onPress: async () => {
              const updated = setBulkActionInState(state, 'skip');
              await updateAndSyncReviewFindingsState($, updated);
            },
          }),
          Text({ children: [' '] }),
          Button({
            key: 'prev-finding',
            label: '[Prev]',
            onPress: async () => {
              const updated = updateSelectedIndexInState(state, 'up');
              await setReviewFindingsState($, updated);
            },
          }),
          Text({ children: [' '] }),
          Button({
            key: 'next-finding',
            label: '[Next]',
            onPress: async () => {
              const updated = updateSelectedIndexInState(state, 'down');
              await setReviewFindingsState($, updated);
            },
          }),
        ],
      })
    );
  } else {
    contentBoxes.push(
      Box({
        paddingTop: 1,
        children: [
          Text({
            children: [
              'Commands: /magpie-findings [all|none|keep <indices>|drop <indices>|status]',
            ],
            color: 'dim',
          }),
        ],
      })
    );
  }

  if (state.syncError) {
    contentBoxes.push(
      Box({
        paddingTop: 1,
        children: [
          Text({
            children: [
              `[!] Warning: Curation sync to disk failed (${state.syncError}). Sidecars invalidated; Step 7b will use original findings.`,
            ],
            color: 'warning',
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

/**
 * Deterministically cycles finding action between accept, skip, and edit.
 */
export function cycleFindingAction(action: FindingAction): FindingAction {
  switch (action) {
    case 'accept':
      return 'skip';
    case 'skip':
      return 'edit';
    case 'edit':
      return 'accept';
  }
}

/**
 * Resolves a 0-based finding index from a string ID or 1-based index identifier.
 */
export function resolveFindingIndex(
  state: ReviewFindingsState,
  identifier: string | number
): number {
  const anchored = state.findings.filter(isAnchored);
  const unanchored = state.findings.filter((f) => !isAnchored(f));

  if (typeof identifier === 'number') {
    if (identifier >= 1 && identifier <= anchored.length) {
      const target = anchored[identifier - 1];
      return state.findings.indexOf(target);
    }
    return -1;
  }

  const trimmed = identifier.trim();

  // 1. Direct ID match (e.g. 'gen-1', 'inline-1')
  const byId = state.findings.findIndex((f) => f.id === trimmed);
  if (byId !== -1) {
    return byId;
  }

  // 2. General finding identifier prefix: g<N> or G<N> (e.g. 'g1', 'g2')
  const generalMatch = trimmed.match(/^[gG](\d+)$/);
  if (generalMatch) {
    const generalIndex = Number.parseInt(generalMatch[1], 10);
    if (generalIndex >= 1 && generalIndex <= unanchored.length) {
      const target = unanchored[generalIndex - 1];
      return state.findings.indexOf(target);
    }
    return -1;
  }

  // 3. Digit string strictly addresses 1-based inline comments (1..anchored.length)
  if (/^\d+$/.test(trimmed)) {
    const parsed = Number.parseInt(trimmed, 10);
    if (parsed >= 1 && parsed <= anchored.length) {
      const target = anchored[parsed - 1];
      return state.findings.indexOf(target);
    }
    return -1;
  }

  return -1;
}

/**
 * Updates a finding at the specified 0-based index immutably and recalculates summary.
 */
export function updateFindingInState(
  state: ReviewFindingsState,
  findingIndex: number,
  updates: Partial<ReviewFinding>
): ReviewFindingsState {
  if (
    !Number.isInteger(findingIndex) ||
    findingIndex < 0 ||
    findingIndex >= state.findings.length
  ) {
    return state;
  }
  const current = state.findings[findingIndex];
  if (!current) {
    return state;
  }
  const updated: ReviewFinding = {
    ...current,
    ...updates,
    raw: current.raw,
  };
  const newFindings = [...state.findings];
  newFindings[findingIndex] = updated;
  return {
    ...state,
    findings: newFindings,
    summary: calculateSummary(newFindings),
  };
}

/**
 * Toggles a finding action at index cycling accept -> skip -> edit -> accept.
 */
export function toggleFindingActionInState(
  state: ReviewFindingsState,
  findingIndex: number
): ReviewFindingsState {
  if (
    !Number.isInteger(findingIndex) ||
    findingIndex < 0 ||
    findingIndex >= state.findings.length
  ) {
    return state;
  }
  const current = state.findings[findingIndex];
  const nextAction = cycleFindingAction(current.action);
  return updateFindingInState(state, findingIndex, { action: nextAction });
}

/**
 * Sets bulk action across all findings or anchored findings only.
 */
export function setBulkActionInState(
  state: ReviewFindingsState,
  action: 'accept' | 'skip',
  anchoredOnly = false
): ReviewFindingsState {
  const newFindings = state.findings.map((f) => {
    if (anchoredOnly && !isAnchored(f)) {
      return f;
    }
    if (action === 'accept' && f.action === 'edit') {
      return f;
    }
    return { ...f, action };
  });
  return {
    ...state,
    findings: newFindings,
    summary: calculateSummary(newFindings),
  };
}

/**
 * Updates selected finding index with boundary clamping.
 */
export function updateSelectedIndexInState(
  state: ReviewFindingsState,
  deltaOrIndex: 'up' | 'down' | number
): ReviewFindingsState {
  const count = state.findings.length;
  if (count === 0) {
    return { ...state, selectedIndex: 0 };
  }
  let next = state.selectedIndex ?? 0;
  if (deltaOrIndex === 'up') {
    next = Math.max(0, next - 1);
  } else if (deltaOrIndex === 'down') {
    next = Math.min(count - 1, next + 1);
  } else if (typeof deltaOrIndex === 'number' && Number.isInteger(deltaOrIndex)) {
    next = Math.max(0, Math.min(count - 1, deltaOrIndex));
  }
  return {
    ...state,
    selectedIndex: next,
  };
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
export function serializeFindingsForRender(
  findings: readonly ReviewFinding[],
  options?: { pr?: number | null; sourceHash?: string | null }
): string {
  // Anchored findings are preserved (rendered or folded via render --keep).
  // Unanchored general findings marked 'skip' are omitted so render does not post them.
  const activeFindings = findings.filter((f) => isAnchored(f) || f.action !== 'skip');

  const payload = activeFindings.map((f) => {
    const raw = f.raw;
    const base: Record<string, unknown> =
      typeof raw === 'object' && raw !== null && !Array.isArray(raw)
        ? { ...(raw as Record<string, unknown>) }
        : {};
    for (const key of ALIAS_KEYS) {
      delete base[key];
    }
    if (f.action === 'edit') {
      delete base.suggestion;
      delete base.comment;
      delete base.suggestion_block;
      delete base.fixup;
      if (f.body) {
        base.explanation = f.body;
      }
    } else if (
      base.explanation === undefined &&
      base.suggestion === undefined &&
      f.body
    ) {
      base.explanation = f.body;
    }
    if (base.rule_id === undefined && base.category === undefined && f.rule) {
      base.rule_id = f.rule;
    }
    return { ...base, file: f.file, line: f.line, severity: f.severity };
  });

  if (options && (options.pr !== undefined || options.sourceHash !== undefined)) {
    const envelope: CuratedFindingsPayload = {
      schema_version: 1,
      pr: options.pr ?? null,
      source_sha256: options.sourceHash ?? null,
      findings: payload,
    };
    return JSON.stringify(envelope, null, 2);
  }

  return JSON.stringify(payload, null, 2);
}

/**
 * Derives the file paths for curated findings and keep recommendation beside original findings.
 */
export function getCuratedFindingsPaths(originalPath: string): {
  curatedJsonPath: string;
  curatedKeepPath: string;
} {
  // `<file>.curated.json` / `<file>.curated.keep`: the names `code-review render` looks for.
  return {
    curatedJsonPath: `${originalPath}.curated.json`,
    curatedKeepPath: `${originalPath}.curated.keep`,
  };
}

/**
 * Marks curated findings files (.curated.json and .curated.keep) as invalidated.
 * Called when findings become empty, stale, or during cleanup after write failures.
 * Only writes invalidation markers if curated sidecar files already exist on disk,
 * ensuring orphaned files are not created beside non-existent findings files.
 */
export async function cleanCuratedFindingsFiles(
  $: any,
  originalPath: string
): Promise<void> {
  if (!originalPath) return;
  try {
    const { curatedJsonPath, curatedKeepPath } = getCuratedFindingsPaths(originalPath);
    let jsonExists = false;
    let keepExists = false;
    try {
      jsonExists = await $.fs.exists(curatedJsonPath);
    } catch {
      jsonExists = false;
    }
    try {
      keepExists = await $.fs.exists(curatedKeepPath);
    } catch {
      keepExists = false;
    }

    if (!jsonExists && !keepExists) {
      return;
    }

    let jsonIsRegular = jsonExists;
    if (jsonExists) {
      try {
        const stat = await $.fs.stat(curatedJsonPath);
        const isSymlink =
          stat &&
          ((typeof stat.isSymbolicLink === 'function' && stat.isSymbolicLink()) ||
            stat.isSymbolicLink === true ||
            (typeof stat.isFile === 'function' && !stat.isFile()));
        // A symlinked or non-regular sidecar is left alone; the keep file is still invalidated.
        if (isSymlink) jsonIsRegular = false;
      } catch {
        // fail-open
      }
    }
    if (jsonIsRegular) {
      const invalidEnvelope: CuratedFindingsPayload = {
        schema_version: 1,
        pr: null,
        source_sha256: null,
        invalidated: true,
        findings: [],
      };
      await $.fs.write(curatedJsonPath, JSON.stringify(invalidEnvelope, null, 2));
    }
    if (keepExists) {
      try {
        const stat = await $.fs.stat(curatedKeepPath);
        const isSymlink =
          stat &&
          ((typeof stat.isSymbolicLink === 'function' && stat.isSymbolicLink()) ||
            stat.isSymbolicLink === true ||
            (typeof stat.isFile === 'function' && !stat.isFile()));
        if (isSymlink) return;
      } catch {
        // fail-open
      }
      await $.fs.write(curatedKeepPath, 'INVALIDATED');
    }
  } catch {
    // Fail-open
  }
}

/**
 * Writes curated findings payload (.curated.json) and keep parameter (.curated.keep)
 * to disk beside the original findings file using $.fs.write.
 */
export async function syncCuratedStateToDisk(
  $: any,
  state: ReviewFindingsState | null,
  sourceContent?: string
): Promise<{ success: boolean; jsonPath?: string; keepPath?: string; error?: string }> {
  if (!state || !state.findingsPath || !state.findings) {
    return { success: true };
  }
  if (state.findings.length === 0) {
    await cleanCuratedFindingsFiles($, state.findingsPath);
    return { success: true };
  }
  try {
    // Verify that the original source findings file exists before writing sidecars
    const exists = await $.fs.exists(state.findingsPath);
    if (!exists) {
      await cleanCuratedFindingsFiles($, state.findingsPath);
      return {
        success: false,
        error: `Source findings file does not exist: ${state.findingsPath}`,
      };
    }

    let rawSource = sourceContent;
    if (rawSource === undefined) {
      try {
        rawSource = await $.fs.read(state.findingsPath);
      } catch {
        rawSource = '';
      }
    }
    const sourceHash = state.sourceHash || computeFindingsHash(rawSource || '');

    const { curatedJsonPath, curatedKeepPath } = getCuratedFindingsPaths(state.findingsPath);

    for (const targetPath of [curatedJsonPath, curatedKeepPath]) {
      try {
        const exists = await $.fs.exists(targetPath);
        if (exists) {
          const stat = await $.fs.stat(targetPath);
          const isSymlink =
            stat &&
            ((typeof stat.isSymbolicLink === 'function' && stat.isSymbolicLink()) ||
              stat.isSymbolicLink === true ||
              (typeof stat.isFile === 'function' && !stat.isFile()));
          if (isSymlink) {
            return {
              success: false,
              error: `Refusing to write to symlink or non-regular file: ${targetPath}`,
            };
          }
        }
      } catch {
        // fail-open
      }
    }

    const jsonContent = serializeFindingsForRender(state.findings, {
      pr: state.prNumber,
      sourceHash,
    });
    const keepContent = formatKeepAnswer(state.findings);
    await $.fs.write(curatedJsonPath, jsonContent);
    await $.fs.write(curatedKeepPath, keepContent);
    return { success: true, jsonPath: curatedJsonPath, keepPath: curatedKeepPath };
  } catch (err: any) {
    // Fail-open: invalidate sidecars on disk so Step 7b falls back to original findings
    try {
      await cleanCuratedFindingsFiles($, state.findingsPath);
    } catch {
      // Safe no-op
    }
    return {
      success: false,
      error: err?.message || String(err),
    };
  }
}

/**
 * Updates reviewFindingsState atom and synchronizes curated findings to disk.
 * If disk sync fails, records syncError in state for display in pane footer.
 */
export async function updateAndSyncReviewFindingsState(
  $: any,
  updatedState: ReviewFindingsState | null
): Promise<{ success: boolean; error?: string }> {
  if (!updatedState) {
    await setReviewFindingsState($, null);
    return { success: true };
  }
  const syncResult = await syncCuratedStateToDisk($, updatedState);
  if (!syncResult.success) {
    updatedState = {
      ...updatedState,
      syncError: syncResult.error || 'Failed to write curated files to disk',
    };
  } else if (updatedState.syncError) {
    updatedState = {
      ...updatedState,
      syncError: null,
    };
  }
  await setReviewFindingsState($, updatedState);
  return syncResult;
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
    const rawBody =
      item.body ?? item.explanation ?? item.comment ?? item.suggestion ?? item.title ?? '';
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
 * UI render event handler for Claude Code mod.
 *
 * Renders the review findings pane when state is populated on ui.render (Pane).
 * If no state exists or no findings are present, delegates to next hook.
 */
export async function handleRenderPane($: any, e: any, next: any): Promise<any> {
  let state: ReviewFindingsState | null = null;
  try {
    state = await read($, reviewFindingsState);
  } catch {
    state = null;
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
 * UI press event handler for Claude Code mod.
 *
 * Handles button click actions from the interactive review findings pane:
 * - toggle-<N>: cycles action of anchored finding at index N (accept -> skip -> edit -> accept)
 * - toggle-general-<N>: cycles action of unanchored general observation at index N
 * - accept-all: marks all findings as accepted
 * - skip-all: marks all findings as skipped
 * - prev-finding: decrements selectedIndex
 * - next-finding: increments selectedIndex
 */
export async function handleUiPress($: any, e: any, next: any): Promise<any> {
  if (!e || typeof e.element !== 'string') {
    if (typeof next === 'function') {
      return next(e);
    }
    return;
  }

  let state: ReviewFindingsState | null = null;
  try {
    state = await read($, reviewFindingsState);
  } catch {
    state = null;
  }

  if (!state || !state.findings || state.findings.length === 0) {
    if (typeof next === 'function') {
      return next(e);
    }
    return;
  }

  const element = e.element.trim();

  if (element.startsWith('toggle-general-')) {
    const numStr = element.slice('toggle-general-'.length);
    const parsed = Number.parseInt(numStr, 10);
    const unanchored = state.findings.filter((f) => !isAnchored(f));
    if (Number.isInteger(parsed) && parsed >= 1 && parsed <= unanchored.length) {
      const target = unanchored[parsed - 1];
      const targetIdx = state.findings.indexOf(target);
      if (targetIdx !== -1) {
        const updated = toggleFindingActionInState(state, targetIdx);
        await updateAndSyncReviewFindingsState($, updated);
        return { handled: true };
      }
    }
  } else if (element.startsWith('toggle-')) {
    const idOrNum = element.slice(7);
    const targetIdx = resolveFindingIndex(state, idOrNum);
    if (targetIdx !== -1) {
      const updated = toggleFindingActionInState(state, targetIdx);
      await updateAndSyncReviewFindingsState($, updated);
      return { handled: true };
    }
  } else if (element === 'accept-all') {
    const updated = setBulkActionInState(state, 'accept');
    await updateAndSyncReviewFindingsState($, updated);
    return { handled: true };
  } else if (element === 'skip-all') {
    const updated = setBulkActionInState(state, 'skip');
    await updateAndSyncReviewFindingsState($, updated);
    return { handled: true };
  } else if (element === 'prev-finding') {
    const updated = updateSelectedIndexInState(state, 'up');
    await setReviewFindingsState($, updated);
    return { handled: true };
  } else if (element === 'next-finding') {
    const updated = updateSelectedIndexInState(state, 'down');
    await setReviewFindingsState($, updated);
    return { handled: true };
  }

  if (typeof next === 'function') {
    return next(e);
  }
}


/**
 * Extracts findings file path from a CLI command string (--findings <path>).
 */
export function extractFindingsPathFromCommand(command: string): string | null {
  const normalized = command.replace(/\\(?:\r?\n|\r)\s*/g, ' ');
  const match = normalized.match(/--findings(?:[=\s]+)(?:"([^"]+)"|'([^']+)'|([^\s]+))/);
  if (!match) return null;
  return match[1] ?? match[2] ?? match[3] ?? null;
}

/**
 * Extracts PR number from a CLI command string (--pr <N>).
 */
export function extractPrNumberFromCommand(command: string): number | undefined {
  const match = command.match(/--pr(?:[=\s]+)(\d+)/);
  if (!match) return undefined;
  const parsed = Number.parseInt(match[1], 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

/**
 * Resolves a file path relative to a base directory without requiring node:path.
 */
export function resolveRelativePath(baseDir: string, filePath: string): string {
  if (!baseDir || filePath.startsWith('/') || /^[A-Za-z]:[\/\\]/.test(filePath)) {
    return filePath.replace(/\\/g, '/');
  }
  const cleanBase = baseDir.replace(/\\/g, '/').replace(/\/+$/, '');
  const cleanPath = filePath.replace(/\\/g, '/').replace(/^\.\//, '');
  return `${cleanBase}/${cleanPath}`;
}

/**
 * Matches an incoming finding to an existing finding from prior state
 * to preserve maintainer curation across disposition re-runs.
 */
export function findMatchingExistingFinding(
  target: ReviewFinding,
  existingFindings: readonly ReviewFinding[],
  consumedIndices?: Set<number>
): ReviewFinding | undefined {
  if (target.id && !target.id.startsWith('finding-')) {
    const idx = existingFindings.findIndex(
      (e, i) => (!consumedIndices || !consumedIndices.has(i)) && e.id === target.id
    );
    if (idx !== -1) {
      if (consumedIndices) consumedIndices.add(idx);
      return existingFindings[idx];
    }
  }
  if (isAnchored(target)) {
    const idx = existingFindings.findIndex((e, i) => {
      if (consumedIndices && consumedIndices.has(i)) return false;
      if (!isAnchored(e) || e.file !== target.file || e.line !== target.line) return false;
      return Boolean((target.rule && e.rule === target.rule) || e.body === target.body);
    });
    if (idx !== -1) {
      if (consumedIndices) consumedIndices.add(idx);
      return existingFindings[idx];
    }
  } else {
    const idx = existingFindings.findIndex((e, i) => {
      if (consumedIndices && consumedIndices.has(i)) return false;
      if (isAnchored(e) || e.file !== target.file) return false;
      return Boolean((target.rule && e.rule === target.rule) || e.body === target.body);
    });
    if (idx !== -1) {
      if (consumedIndices) consumedIndices.add(idx);
      return existingFindings[idx];
    }
  }
  return undefined;
}

/**
 * Bash tool.call event handler for Claude Code mod (Fail-Open).
 *
 * Intercepts pr-management code-review disposition command executions,
 * reads the findings file from disk via $.fs.read, parses the findings,
 * and hydrates reviewFindingsState so the interactive pane mounts live findings.
 * Always delegates to next(e) to ensure tool execution proceeds normally.
 */
export async function handleBashToolCall($: any, e: any, next: any): Promise<any> {
  if (e && typeof e.command === 'string') {
    try {
      const command = e.command;
      const isDisposition =
        /code-review(?:\.cli)?\s+disposition\b/.test(command) &&
        /--findings[=\s]/.test(command);

      if (isDisposition) {
        const rawPath = extractFindingsPathFromCommand(command);
        if (rawPath) {
          let sessionRoot: string | undefined;
          try {
            sessionRoot = await $.session.root();
          } catch {
            sessionRoot = undefined;
          }

          let sessionCwd: string | undefined;
          try {
            sessionCwd = await $.session.cwd();
          } catch {
            sessionCwd = undefined;
          }

          const base = sessionCwd || sessionRoot || '';
          const candidatePath = base ? resolveRelativePath(base, rawPath) : rawPath;

          let effectivePath: string | null = null;
          let fileContent: string | null = null;
          try {
            fileContent = await $.fs.read(candidatePath);
            effectivePath = candidatePath;
          } catch {
            try {
              fileContent = await $.fs.read(rawPath);
              effectivePath = rawPath;
            } catch {
              fileContent = null;
              effectivePath = null;
            }
          }

          if (fileContent && typeof fileContent === 'string' && fileContent.trim().length > 0) {
            const parsed = parseFindings(fileContent);
            if (parsed.findings.length > 0) {
              const prNumber = extractPrNumberFromCommand(command);

              let existingState: ReviewFindingsState | null = null;
              try {
                existingState = await read($, reviewFindingsState);
              } catch {
                existingState = null;
              }

              let finalFindings = parsed.findings;
              if (
                existingState &&
                existingState.findings &&
                existingState.findings.length > 0 &&
                (!existingState.prNumber || !prNumber || existingState.prNumber === prNumber)
              ) {
                const consumed = new Set<number>();
                finalFindings = parsed.findings.map((f) => {
                  const match = findMatchingExistingFinding(f, existingState.findings, consumed);
                  if (match) {
                    return {
                      ...f,
                      action: match.action,
                      body: match.action === 'edit' ? match.body : f.body,
                    };
                  }
                  return f;
                });
              }

              const targetFindingsFile = effectivePath || rawPath;
              const sourceHash = computeFindingsHash(fileContent);

              const nextState: ReviewFindingsState = {
                prNumber,
                findingsPath: targetFindingsFile,
                sourceHash,
                findings: finalFindings,
                summary: calculateSummary(finalFindings),
                selectedIndex: 0,
              };
              await setReviewFindingsState($, nextState);

              // Check if curated sidecars already exist on disk from earlier curation
              const { curatedJsonPath } = getCuratedFindingsPaths(targetFindingsFile);
              let hasExistingCuratedJson = false;
              try {
                hasExistingCuratedJson = await $.fs.exists(curatedJsonPath);
              } catch {
                hasExistingCuratedJson = false;
              }

              if (hasExistingCuratedJson) {
                let existingDiskJson: any = null;
                try {
                  const rawCurated = await $.fs.read(curatedJsonPath);
                  existingDiskJson = JSON.parse(rawCurated);
                } catch {
                  existingDiskJson = null;
                }

                const isAlreadyInvalidated =
                  !existingDiskJson ||
                  typeof existingDiskJson !== 'object' ||
                  existingDiskJson.invalidated === true;

                const matchesPr =
                  !isAlreadyInvalidated &&
                  existingDiskJson.pr !== undefined &&
                  existingDiskJson.pr !== null &&
                  prNumber !== undefined &&
                  prNumber !== null &&
                  Number(existingDiskJson.pr) === Number(prNumber);

                if (matchesPr && finalFindings.length > 0) {
                  // Re-sync sidecars with merged curation state and updated source hash
                  await syncCuratedStateToDisk($, nextState, fileContent);
                } else if (!isAlreadyInvalidated) {
                  // PR mismatch or empty findings: invalidate sidecars on disk
                  await cleanCuratedFindingsFiles($, targetFindingsFile);
                }
              }
              // NOTE: Never write .curated.* files at initial disposition.
              // Curated files are only written when curated sidecars exist or when curated in UI.
            } else {
              await cleanCuratedFindingsFiles($, effectivePath || rawPath);
              await setReviewFindingsState($, null);
            }
          } else {
            await cleanCuratedFindingsFiles($, effectivePath || rawPath);
            await setReviewFindingsState($, null);
          }
        }
      }
    } catch {
      // Safe no-op on any parsing or I/O failure (fail-open)
    }
  }

  if (typeof next === 'function') {
    return next(e);
  }
}

export interface ParsedFindingTokens {
  valid: boolean;
  error?: string;
  anchoredIndices: Set<number>;
  generalIndices: Set<number>;
}

/**
 * Validates and parses finding indices for /magpie-findings keep and drop.
 * Strictly requires every token to be an integer >= 1 (e.g. 1, 3) or general observation (e.g. g1, g2).
 * Rejects arbitrary strings (e.g. abc).
 */
export function parseFindingTokens(raw: string): ParsedFindingTokens {
  const parts = raw.split(',').map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) {
    return {
      valid: false,
      error: 'No finding indices specified',
      anchoredIndices: new Set(),
      generalIndices: new Set(),
    };
  }

  const anchoredIndices = new Set<number>();
  const generalIndices = new Set<number>();

  for (const token of parts) {
    if (/^\d+$/.test(token)) {
      const num = Number.parseInt(token, 10);
      if (num >= 1) {
        anchoredIndices.add(num);
      } else {
        return {
          valid: false,
          error: `Invalid index "${token}": indices must be >= 1`,
          anchoredIndices: new Set(),
          generalIndices: new Set(),
        };
      }
    } else if (/^[gG]\d+$/.test(token)) {
      const num = Number.parseInt(token.slice(1), 10);
      if (num >= 1) {
        generalIndices.add(num);
      } else {
        return {
          valid: false,
          error: `Invalid general index "${token}": indices must be >= 1`,
          anchoredIndices: new Set(),
          generalIndices: new Set(),
        };
      }
    } else {
      return {
        valid: false,
        error: `Invalid token "${token}". Only numeric indices (e.g. 1, 3) and general observation indices (e.g. g1, g2) are allowed.`,
        anchoredIndices: new Set(),
        generalIndices: new Set(),
      };
    }
  }

  return {
    valid: true,
    anchoredIndices,
    generalIndices,
  };
}

/**
 * Slash command handler for /magpie-findings (zero-token).
 *
 * Allows inspecting and curating review findings directly from the terminal prompt:
 * - /magpie-findings status (or empty): prints current findings status & keep answer
 * - /magpie-findings all: accepts all findings
 * - /magpie-findings none: skips all findings
 * - /magpie-findings keep <indices>: marks specified 1-based indices as accepted, others skipped
 * - /magpie-findings drop <indices>: marks specified 1-based indices as skipped
 * - /magpie-findings edit <index> <note>: marks finding at index as edit with updated body
 */
export async function handleFindingsCommand($: any, e: any): Promise<{ text: string }> {
  let state: ReviewFindingsState | null = null;
  try {
    state = await read($, reviewFindingsState);
  } catch {
    state = null;
  }

  if (!state || !state.findings || state.findings.length === 0) {
    return {
      text: 'No active PR review findings in session. Run code-review Step 6 (disposition) first.',
    };
  }

  const rawArgs = (e?.args || '').trim();
  if (!rawArgs || rawArgs === 'status') {
    const s = state.summary;
    const lines: string[] = [
      state.prNumber
        ? `PR #${state.prNumber}: Review Findings Status`
        : 'Review Findings Status',
      `Summary: ${s.anchoredCount} inline, ${s.unanchoredCount} general (${s.blockingCount} blocking, ${s.majorCount} major, ${s.minorCount} minor, ${s.nitCount} nit)`,
      `Keep parameter (--keep): ${formatKeepAnswer(state.findings)}`,
      '',
    ];

    const anchored = state.findings.filter(isAnchored);
    if (anchored.length > 0) {
      lines.push('Inline comments:');
      for (let i = 0; i < anchored.length; i += 1) {
        const f = anchored[i];
        const indicator = formatActionIndicator(f.action);
        lines.push(`  ${indicator.label.slice(0, 3)} ${i + 1}. [${f.severity.toUpperCase()}] ${f.file}:${f.line} - ${truncateText(f.body, 60)}`);
      }
    }

    const unanchored = state.findings.filter((f) => !isAnchored(f));
    if (unanchored.length > 0) {
      if (anchored.length > 0) {
        lines.push('');
      }
      lines.push('General observations (unanchored):');
      for (let i = 0; i < unanchored.length; i += 1) {
        const f = unanchored[i];
        const indicator = formatActionIndicator(f.action);
        lines.push(`  ${indicator.label.slice(0, 3)} g${i + 1}. [${f.severity.toUpperCase()}] ${f.file} - ${truncateText(f.body, 60)}`);
      }
    }
    if (state.syncError) {
      lines.push('');
      lines.push(`[!] Warning: Curation sync to disk failed (${state.syncError}).`);
    }
    return { text: lines.join('\n') };
  }

  if (rawArgs === 'all') {
    const updated = setBulkActionInState(state, 'accept');
    const syncRes = await updateAndSyncReviewFindingsState($, updated);
    const warnSuffix = syncRes.error ? ` (Warning: sync to disk failed: ${syncRes.error})` : '';
    return {
      text: `Accepted all review findings. Keep parameter: ${formatKeepAnswer(updated.findings)}${warnSuffix}`,
    };
  }

  if (rawArgs === 'none') {
    const updated = setBulkActionInState(state, 'skip');
    const syncRes = await updateAndSyncReviewFindingsState($, updated);
    const warnSuffix = syncRes.error ? ` (Warning: sync to disk failed: ${syncRes.error})` : '';
    return {
      text: `Skipped all review findings. Keep parameter: NONE${warnSuffix}`,
    };
  }

  const keepMatch = rawArgs.match(/^keep(?:\s+([\s\S]+))?$/i);
  if (keepMatch) {
    if (!keepMatch[1] || keepMatch[1].trim() === '') {
      return { text: 'Usage: /magpie-findings keep <indices> (e.g. 1,3 or g1)' };
    }
    const parsedTokens = parseFindingTokens(keepMatch[1]);
    if (!parsedTokens.valid) {
      return { text: `Error: ${parsedTokens.error}` };
    }

    const { anchoredIndices, generalIndices } = parsedTokens;
    const anchored = state.findings.filter(isAnchored);
    const unanchored = state.findings.filter((f) => !isAnchored(f));

    for (const idx of anchoredIndices) {
      if (idx > anchored.length) {
        return {
          text: `Error: Anchored finding index ${idx} out of range (1-${anchored.length})`,
        };
      }
    }
    for (const gIdx of generalIndices) {
      if (gIdx > unanchored.length) {
        return {
          text: `Error: General observation index g${gIdx} out of range (g1-g${unanchored.length})`,
        };
      }
    }

    const hasAnchoredSpec = anchoredIndices.size > 0;
    const hasGeneralSpec = generalIndices.size > 0;

    const newFindings = state.findings.map((f) => {
      if (isAnchored(f)) {
        if (!hasAnchoredSpec) return f;
        const anchoredIndex = anchored.indexOf(f) + 1;
        const isKept = anchoredIndices.has(anchoredIndex);
        return {
          ...f,
          action: isKept ? (f.action === 'edit' ? ('edit' as const) : ('accept' as const)) : ('skip' as const),
        };
      }
      if (!hasGeneralSpec) return f;
      const genIndex = unanchored.indexOf(f) + 1;
      const isKept = generalIndices.has(genIndex);
      return {
        ...f,
        action: isKept ? (f.action === 'edit' ? ('edit' as const) : ('accept' as const)) : ('skip' as const),
      };
    });

    const updated: ReviewFindingsState = {
      ...state,
      findings: newFindings,
      summary: calculateSummary(newFindings),
    };
    const syncRes = await updateAndSyncReviewFindingsState($, updated);
    const keptList: string[] = [];
    if (hasAnchoredSpec) {
      keptList.push(...Array.from(anchoredIndices).sort((a, b) => a - b).map(String));
    }
    if (hasGeneralSpec) {
      keptList.push(...Array.from(generalIndices).sort((a, b) => a - b).map((g) => `g${g}`));
    }
    const warnSuffix = syncRes.error ? ` (Warning: sync to disk failed: ${syncRes.error})` : '';
    return {
      text: `Curated findings. Kept: ${keptList.join(',')}. Keep parameter: ${formatKeepAnswer(updated.findings)}${warnSuffix}`,
    };
  }

  const dropMatch = rawArgs.match(/^drop(?:\s+([\s\S]+))?$/i);
  if (dropMatch) {
    if (!dropMatch[1] || dropMatch[1].trim() === '') {
      return { text: 'Usage: /magpie-findings drop <indices> (e.g. 2 or g1)' };
    }
    const parsedTokens = parseFindingTokens(dropMatch[1]);
    if (!parsedTokens.valid) {
      return { text: `Error: ${parsedTokens.error}` };
    }

    const { anchoredIndices, generalIndices } = parsedTokens;
    const anchored = state.findings.filter(isAnchored);
    const unanchored = state.findings.filter((f) => !isAnchored(f));

    for (const idx of anchoredIndices) {
      if (idx > anchored.length) {
        return {
          text: `Error: Anchored finding index ${idx} out of range (1-${anchored.length})`,
        };
      }
    }
    for (const gIdx of generalIndices) {
      if (gIdx > unanchored.length) {
        return {
          text: `Error: General observation index g${gIdx} out of range (g1-g${unanchored.length})`,
        };
      }
    }

    const hasAnchoredSpec = anchoredIndices.size > 0;
    const hasGeneralSpec = generalIndices.size > 0;

    const newFindings = state.findings.map((f) => {
      if (isAnchored(f)) {
        if (!hasAnchoredSpec) return f;
        const anchoredIndex = anchored.indexOf(f) + 1;
        return {
          ...f,
          action: anchoredIndices.has(anchoredIndex) ? ('skip' as const) : f.action,
        };
      }
      if (!hasGeneralSpec) return f;
      const genIndex = unanchored.indexOf(f) + 1;
      return {
        ...f,
        action: generalIndices.has(genIndex) ? ('skip' as const) : f.action,
      };
    });

    const updated: ReviewFindingsState = {
      ...state,
      findings: newFindings,
      summary: calculateSummary(newFindings),
    };
    const syncRes = await updateAndSyncReviewFindingsState($, updated);
    const droppedList: string[] = [];
    if (hasAnchoredSpec) {
      droppedList.push(...Array.from(anchoredIndices).sort((a, b) => a - b).map(String));
    }
    if (hasGeneralSpec) {
      droppedList.push(...Array.from(generalIndices).sort((a, b) => a - b).map((g) => `g${g}`));
    }
    const warnSuffix = syncRes.error ? ` (Warning: sync to disk failed: ${syncRes.error})` : '';
    return {
      text: `Dropped findings: ${droppedList.join(',')}. Keep parameter: ${formatKeepAnswer(updated.findings)}${warnSuffix}`,
    };
  }

  const editMatch = rawArgs.match(/^edit\s+([a-zA-Z0-9_-]+)\s+([\s\S]+)$/i);
  if (editMatch) {
    const idOrNum = editMatch[1];
    const newNote = editMatch[2].trim();
    const targetIdx = resolveFindingIndex(state, idOrNum);
    if (targetIdx !== -1) {
      const updated = updateFindingInState(state, targetIdx, {
        action: 'edit',
        body: newNote,
      });
      const syncRes = await updateAndSyncReviewFindingsState($, updated);
      const warnSuffix = syncRes.error ? ` (Warning: sync to disk failed: ${syncRes.error})` : '';
      return {
        text: `Updated finding #${idOrNum} (marked edit with custom note). Keep parameter: ${formatKeepAnswer(updated.findings)}${warnSuffix}`,
      };
    }
    return { text: `Finding #${idOrNum} not found in active review findings.` };
  }

  return {
    text: 'Usage: /magpie-findings [all|none|keep <1,3>|drop <2>|edit <idx> <note>|status]',
  };
}

/**
 * Event hook registration entry point for Claude Code mod.
 *
 * Registers:
 * - session.start: command registration and test fixture hydration
 * - ui.render (Pane): renders the interactive review findings pane when state is populated
 * - ui.press: handles button press interactions from the review findings pane
 * - tool.call (Bash): intercepts code-review disposition to hydrate findings from disk
 * - command.run (magpie-findings): zero-token command for inspecting and curating findings
 */
export function register(on: any): void {
  on('session.start', async ($: any, e: any, next: any) => {
    try {
      await $.command.register({
        name: 'magpie-findings',
        description: 'Inspect and curate PR review findings (zero-token)',
        argumentHint: '[all|none|keep <indices>|drop <indices>|edit <idx> <note>|status]',
      });
    } catch {
      // Safe no-op on command register exception
    }

    if (e && e.findings) {
      try {
        const parsed = parseFindings(e.findings);
        await setReviewFindingsState($, {
          prNumber: e.prNumber,
          prTitle: e.prTitle,
          findings: parsed.findings,
          summary: parsed.summary,
          selectedIndex: 0,
        });
      } catch {
        try {
          await setReviewFindingsState($, null);
        } catch {
          // Safe no-op
        }
      }
    } else {
      try {
        await setReviewFindingsState($, null);
      } catch {
        // Safe no-op
      }
    }
    if (typeof next === 'function') {
      return next(e);
    }
  });

  on('ui.render', { component: 'Pane' }, handleRenderPane);
  on('ui.press', handleUiPress);
  on('tool.call', { tool: 'Bash' }, handleBashToolCall);
  on('command.run', { command: 'magpie-findings' }, handleFindingsCommand);
}

export default register;
