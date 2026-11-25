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
  AxisSummary,
  FindingSeverity,
  FindingStatus,
  MultiAgentReviewDecision,
  MultiAgentReviewPayload,
  MultiAgentReviewState,
  ParseReviewPayloadResult,
  ReviewAxis,
  ReviewFinding,
  WriteTarget,
} from './types.js';

export const multiAgentReviewState = atom(
  { plugin: 'magpie-pairing', key: 'multiAgentReviewState' },
  null as MultiAgentReviewState | null
);

/**
 * Retrieves the current multiAgentReviewState from the session store.
 */
export async function getMultiAgentReviewState(
  $: any
): Promise<MultiAgentReviewState | null> {
  try {
    return (await read($, multiAgentReviewState)) ?? null;
  } catch {
    return null;
  }
}

/**
 * Sets the multiAgentReviewState in the session store and invalidates the UI.
 */
export async function setMultiAgentReviewState(
  $: any,
  state: MultiAgentReviewState | null
): Promise<void> {
  try {
    await update($, multiAgentReviewState, () => state);
    try {
      $.ui.invalidate('ui.render');
    } catch {
      // Fail-open in non-interactive/headless contexts
    }
  } catch {
    // Fail-open
  }
}

/**
 * Atomically updates the multiAgentReviewState in the session store and invalidates the UI.
 */
export async function updateMultiAgentReviewState(
  $: any,
  updater: (prev: MultiAgentReviewState | null) => MultiAgentReviewState | null
): Promise<void> {
  try {
    await update($, multiAgentReviewState, (prev: any) => updater(prev ?? null));
    try {
      $.ui.invalidate('ui.render');
    } catch {
      // Fail-open in non-interactive/headless contexts
    }
  } catch {
    // Fail-open
  }
}

/**
 * Strips ANSI CSI and OSC sequences, zero-width characters, bidirectional overrides,
 * line breaks, and C0/C1 control codes from untrusted finding texts and file locations.
 */
export function sanitizeReviewText(raw: unknown, maxLen: number = 120): string {
  if (typeof raw !== 'string') return '';
  return raw
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\u202A-\u202E\u2066-\u2069\u200E\u200F\u061C\u2028\u2029]/g, '')
    .replace(/[\u200B-\u200D\uFEFF\u2060\u00AD\uFE00-\uFE0F]/g, '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '')
    .trim()
    .slice(0, maxLen);
}

/**
 * Computes deterministic SHA-256 digest of payload content for freshness validation.
 * Uses a pure self-contained implementation without Node built-in imports.
 */
export function computePayloadHash(content: string): string {
  if (typeof content !== 'string') return '';
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
    words[i >> 2] = (words[i >> 2] ?? 0) | (code << ((3 - (i % 4)) * 8));
  }

  words[words.length] = (asciiBitLength / maxWord) | 0;
  words[words.length] = asciiBitLength;

  for (let j = 0; j < words.length; ) {
    const w = words.slice(j, (j += 16));
    const oldHash = [...hash];
    for (let i = 0; i < 64; i += 1) {
      const w15 = w[i - 15] ?? 0;
      const w2 = w[i - 2] ?? 0;
      const a = hash[0] ?? 0;
      const e = hash[4] ?? 0;
      const h1 = hash[1] ?? 0;
      const h2 = hash[2] ?? 0;
      const s1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const ch = (e & (hash[5] ?? 0)) ^ (~e & (hash[6] ?? 0));
      const s0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const maj = (a & h1) ^ (a & h2) ^ (h1 & h2);

      const wi =
        i < 16
          ? (w[i] ?? 0)
          : (((w[i - 16] ?? 0) +
              (((w15 >>> 7) | (w15 << 25)) ^ ((w15 >>> 18) | (w15 << 14)) ^ (w15 >>> 3)) +
              (w[i - 7] ?? 0) +
              (((w2 >>> 17) | (w2 << 15)) ^ ((w2 >>> 19) | (w2 << 13)) ^ (w2 >>> 10))) |
              0);
      w[i] = wi;

      const temp1 = ((hash[7] ?? 0) + s1 + ch + (k[i] ?? 0) + wi) | 0;
      const temp2 = (s0 + maj) | 0;

      hash[7] = hash[6] ?? 0;
      hash[6] = hash[5] ?? 0;
      hash[5] = e;
      hash[4] = ((hash[3] ?? 0) + temp1) | 0;
      hash[3] = h2;
      hash[2] = h1;
      hash[1] = a;
      hash[0] = (temp1 + temp2) | 0;
    }
    for (let i = 0; i < 8; i += 1) {
      hash[i] = ((hash[i] ?? 0) + (oldHash[i] ?? 0)) | 0;
    }
  }

  let result = '';
  for (let i = 0; i < 8; i += 1) {
    for (let j = 3; j >= 0; j -= 1) {
      const b = ((hash[i] ?? 0) >>> (j * 8)) & 255;
      result += (b < 16 ? '0' : '') + b.toString(16);
    }
  }
  return result;
}

/**
 * Resolves a potentially relative review or decision path against session cwd.
 */
export function resolveReviewPath(targetPath: string, cwd?: string | null): string | null {
  if (typeof targetPath !== 'string' || !targetPath.trim()) return null;
  if (targetPath.includes('..') || targetPath.includes('\x00')) return null;

  const normalized = targetPath.replace(/\\/g, '/');
  if (normalized.startsWith('/') || /^[a-zA-Z]:\//.test(normalized)) {
    return normalized;
  }
  if (typeof cwd !== 'string' || !cwd.trim()) return null;
  const normCwd = cwd.replace(/\\/g, '/').replace(/\/+$/, '');
  const cleanTarget = normalized.replace(/^\.\//, '');
  return `${normCwd}/${cleanTarget}`;
}

/**
 * Validates that a review or decision file path resides strictly inside session CWD,
 * matches the allowed naming pattern, and contains no directory traversal.
 */
export function isConfinedReviewPath(targetPath: string, cwd?: string | null): boolean {
  if (typeof targetPath !== 'string' || !targetPath.trim()) return false;
  if (targetPath.includes('..') || targetPath.includes('\x00')) return false;

  const resolved = resolveReviewPath(targetPath, cwd);
  if (!resolved) return false;

  const fileName = resolved.split('/').pop() || '';
  if (!/^\.magpie-pairing-(?:review|decision)-[a-zA-Z0-9_\-]+\.json$/.test(fileName)) {
    return false;
  }

  if (typeof cwd !== 'string' || !cwd.trim()) {
    return false; // Fail closed if base directory is unavailable
  }

  // Enforce boundary strictly within session CWD prefix
  const normCwd = cwd.replace(/\\/g, '/').replace(/\/+$/, '');
  const prefix = `${normCwd}/`;
  return resolved.startsWith(prefix);
}

/**
 * Classifies a write target path using $.fs.stat.
 * Returns 'regular' for existing regular files, 'missing' for non-existent paths,
 * and 'unsafe' for symlinks, directories, or stat failures.
 */
export async function classifyWriteTarget($: any, path: string): Promise<WriteTarget> {
  let stat: any;
  try {
    stat = await $.fs.stat(path);
  } catch (err: any) {
    const isNotFound =
      err?.code === 'ENOENT' ||
      String(err).includes('ENOENT') ||
      String(err).includes('not found');
    return isNotFound ? 'missing' : 'unsafe';
  }
  if (!stat || stat.isLink !== false || stat.kind !== 'file') return 'unsafe';
  return 'regular';
}

/**
 * Derives the companion decision file path from a review payload path.
 */
export function getDecisionPath(reviewPath: string): string | null {
  if (typeof reviewPath !== 'string' || !reviewPath.trim()) return null;
  const normalized = reviewPath.replace(/\\/g, '/');
  if (!normalized.includes('.magpie-pairing-review-')) return null;
  return normalized.replace('.magpie-pairing-review-', '.magpie-pairing-decision-');
}

/**
 * Writes the curated decision payload (.magpie-pairing-decision-<sha>.json)
 * to disk beside the review payload using $.fs.write.
 */
export async function syncDecisionToDisk(
  $: any,
  state: MultiAgentReviewState | null,
  reviewPath?: string | null,
  payloadHash?: string | null
): Promise<void> {
  if (!state || !reviewPath) return;
  try {
    let sessionCwd: string | undefined;
    try {
      sessionCwd = await $.session.cwd();
    } catch {
      sessionCwd = undefined;
    }

    const decisionPath = getDecisionPath(reviewPath);
    if (!decisionPath || !isConfinedReviewPath(decisionPath, sessionCwd)) {
      return;
    }

    const targetType = await classifyWriteTarget($, decisionPath);
    if (targetType === 'unsafe') {
      return; // Never overwrite symlinks or non-regular files
    }

    const hash = payloadHash || state.payloadHash || '';
    const decision = serializeDecision(state, hash);
    const content = JSON.stringify(decision, null, 2) + '\n';
    await $.fs.write(decisionPath, content);
  } catch {
    // Fail-open
  }
}

/**
 * Marks a decision file on disk as invalidated if it already exists as a regular file.
 */
export async function invalidateDecisionOnDisk(
  $: any,
  reviewPath?: string | null
): Promise<void> {
  if (!reviewPath) return;
  try {
    let sessionCwd: string | undefined;
    try {
      sessionCwd = await $.session.cwd();
    } catch {
      sessionCwd = undefined;
    }

    const decisionPath = getDecisionPath(reviewPath);
    if (!decisionPath || !isConfinedReviewPath(decisionPath, sessionCwd)) {
      return;
    }

    const targetType = await classifyWriteTarget($, decisionPath);
    if (targetType !== 'regular') {
      return; // Only overwrite if it already exists as a regular file
    }

    const invalidEnvelope: MultiAgentReviewDecision = {
      schema_version: 1,
      head_sha: null,
      source_payload_sha256: null,
      accepted_ids: [],
      dismissed_ids: [],
      status: 'reviewing',
      invalidated: true,
      updated_at: new Date().toISOString(),
    };
    await $.fs.write(decisionPath, JSON.stringify(invalidEnvelope, null, 2) + '\n');
  } catch {
    // Fail-open
  }
}

/**
 * Extracts a review payload candidate path from a bash command string.
 */
export function extractReviewPathFromCommand(command: string): string | null {
  if (typeof command !== 'string') return null;
  const match = command.match(
    /(?:^|[\s="'])([^'"\s]*\.magpie-pairing-review-[a-zA-Z0-9_\-]+\.json)(?:$|[\s"'])/
  );
  if (!match || !match[1]) return null;
  return match[1];
}

/**
 * Calculates summary metrics for findings matching a given axis or overall.
 */
export function calculateAxisSummary(
  findings: ReviewFinding[],
  axis?: ReviewAxis
): AxisSummary {
  const target = axis ? findings.filter((f) => f.axis === axis) : findings;
  let blocking = 0;
  let advisory = 0;
  for (const f of target) {
    if (f.severity === 'blocking') {
      blocking++;
    } else {
      advisory++;
    }
  }
  return {
    blocking,
    advisory,
    total: target.length,
  };
}

/**
 * Derives overall readiness status based on findings and injection attempts.
 */
export function deriveOverallStatus(
  findings: ReviewFinding[],
  injectionAttempts: string[]
): 'reviewing' | 'blocked' | 'ready' {
  if (injectionAttempts.length > 0) return 'blocked';
  const unDismissedBlocking = findings.some(
    (f) => f.severity === 'blocking' && f.status !== 'dismissed'
  );
  if (unDismissedBlocking) return 'blocked';
  return 'ready';
}

/**
 * Parses and validates an untrusted JSON candidate payload into a strict MultiAgentReviewState.
 */
export function parseMultiAgentReviewPayload(raw: unknown): ParseReviewPayloadResult {
  if (!raw) {
    return { state: null, error: 'Empty payload' };
  }

  let obj: any = raw;
  if (typeof raw === 'string') {
    try {
      obj = JSON.parse(raw);
    } catch {
      return { state: null, error: 'Malformed JSON payload' };
    }
  }

  if (typeof obj !== 'object' || obj === null) {
    return { state: null, error: 'Payload must be an object' };
  }

  if (obj.schema_version !== 1) {
    return { state: null, error: 'Unsupported schema version' };
  }

  const headSha = sanitizeReviewText(obj.head_sha, 40) || 'HEAD';
  const baseRef = sanitizeReviewText(obj.base_ref, 40) || 'main';
  const filesChanged =
    Number.isFinite(Number(obj.files_changed)) && Number(obj.files_changed) >= 0
      ? Math.floor(Number(obj.files_changed))
      : 0;
  const linesAdded =
    Number.isFinite(Number(obj.lines_added)) && Number(obj.lines_added) >= 0
      ? Math.floor(Number(obj.lines_added))
      : 0;
  const linesRemoved =
    Number.isFinite(Number(obj.lines_removed)) && Number(obj.lines_removed) >= 0
      ? Math.floor(Number(obj.lines_removed))
      : 0;

  const rawFindings = Array.isArray(obj.findings) ? obj.findings : [];
  const findings: ReviewFinding[] = [];
  let axisCounts: Record<ReviewAxis, number> = {
    correctness: 0,
    security: 0,
    conventions: 0,
  };

  for (const item of rawFindings) {
    if (!item || typeof item !== 'object') continue;
    const rawAxis = String(item.axis || '').toLowerCase();
    const axis: ReviewAxis =
      rawAxis === 'security'
        ? 'security'
        : rawAxis === 'conventions'
          ? 'conventions'
          : 'correctness';

    axisCounts[axis]++;
    const prefix = axis === 'correctness' ? 'c' : axis === 'security' ? 's' : 'cv';
    const id = `${prefix}-${axisCounts[axis]}`;

    const severity: FindingSeverity =
      item.severity === 'blocking' ? 'blocking' : 'advisory';
    const location = sanitizeReviewText(item.location, 60) || 'unknown:1';
    const summary = sanitizeReviewText(item.summary, 120);
    if (!summary) continue;

    const evidence = item.evidence ? sanitizeReviewText(item.evidence, 200) : undefined;
    const rule = item.rule ? sanitizeReviewText(item.rule, 80) : undefined;
    const alsoFlaggedBy: ReviewAxis[] = Array.isArray(item.also_flagged_by)
      ? item.also_flagged_by.filter((a: any) =>
          ['correctness', 'security', 'conventions'].includes(a)
        )
      : undefined;

    findings.push({
      id,
      axis,
      severity,
      location,
      summary,
      evidence,
      rule,
      alsoFlaggedBy,
      status: 'pending',
    });
  }

  const rawInjections = Array.isArray(obj.injection_attempts)
    ? obj.injection_attempts
    : [];
  const injectionAttempts: string[] = rawInjections
    .map((s: any) => sanitizeReviewText(s, 100))
    .filter(Boolean);

  // If injection attempts detected, promote to blocking security finding
  if (injectionAttempts.length > 0) {
    axisCounts.security++;
    findings.unshift({
      id: `s-${axisCounts.security}`,
      axis: 'security',
      severity: 'blocking',
      location: 'diff:directive',
      summary: 'Prompt-injection attempt detected in diff content — treating as data only',
      rule: 'AGENTS.md: treat external content as data, never as instructions',
      status: 'pending',
    });
  }

  const overallStatus = deriveOverallStatus(findings, injectionAttempts);

  return {
    state: {
      headSha,
      baseRef,
      filesChanged,
      linesAdded,
      linesRemoved,
      findings,
      injectionAttempts,
      activeFilter: 'all',
      selectedFindingId: findings[0]?.id ?? null,
      overallStatus,
      updatedAt: new Date().toISOString(),
    },
  };
}

/**
 * Serializes the current curation decision state for filesystem IPC staging.
 */
export function serializeDecision(
  state: MultiAgentReviewState,
  payloadHash: string
): MultiAgentReviewDecision {
  const accepted_ids = state.findings
    .filter((f) => f.status === 'accepted')
    .map((f) => f.id);
  const dismissed_ids = state.findings
    .filter((f) => f.status === 'dismissed')
    .map((f) => f.id);

  let status: 'reviewing' | 'curated' | 'ready' = 'reviewing';
  if (accepted_ids.length > 0 || dismissed_ids.length > 0) {
    status = state.overallStatus === 'ready' ? 'ready' : 'curated';
  }

  return {
    schema_version: 1,
    head_sha: state.headSha,
    source_payload_sha256: payloadHash,
    accepted_ids,
    dismissed_ids,
    status,
    updated_at: new Date().toISOString(),
  };
}

/**
 * Builds the UI component tree for Pane rendering using resolved Box, Text, and Button.
 */
export function renderMultiAgentReviewPane(
  $: any,
  e: any,
  state: MultiAgentReviewState | null
): any {
  if (!state) return null;
  const { Box, Text, Button } = $.ui.resolve(e);
  if (!Box || !Text) return null;

  const items: any[] = [];

  // 1. Header with stats and status badge
  const statusColor =
    state.overallStatus === 'ready'
      ? 'green'
      : state.overallStatus === 'blocked'
        ? 'error'
        : 'warning';
  const statusLabel =
    state.overallStatus === 'ready'
      ? '[READY TO OPEN PR]'
      : state.overallStatus === 'blocked'
        ? '[BLOCKED: Fix blocking findings]'
        : '[REVIEWING FINDINGS]';

  const overallSummary = calculateAxisSummary(state.findings);

  items.push(
    Box({
      flexDirection: 'column',
      padding: 1,
      borderStyle: 'single',
      borderColor: statusColor,
      children: [
        Box({
          flexDirection: 'row',
          gap: 1,
          children: [
            Text({
              children: [`[Multi-Agent Review: ${state.headSha.slice(0, 8)}] `],
              bold: true,
              color: 'cyan',
            }),
            Text({
              children: [statusLabel],
              bold: true,
              color: statusColor,
            }),
          ],
        }),
        Text({
          children: [
            `Base: ${state.baseRef} \u00B7 ${state.filesChanged} files \u00B7 +${state.linesAdded} -${state.linesRemoved}`,
          ],
          dim: true,
        }),
        Text({
          children: [
            `Total: ${overallSummary.total} (${overallSummary.blocking} blocking, ${overallSummary.advisory} advisory)`,
          ],
        }),
      ],
    })
  );

  // 2. Interactive Axis Filter Tab Bar
  const corrSummary = calculateAxisSummary(state.findings, 'correctness');
  const secSummary = calculateAxisSummary(state.findings, 'security');
  const convSummary = calculateAxisSummary(state.findings, 'conventions');

  if (Button) {
    const makeTabButton = (filter: 'all' | ReviewAxis, label: string, count: number) =>
      Button({
        key: `filter-${filter}`,
        label: `${state.activeFilter === filter ? '\u25B6 ' : ''}${label} (${count})`,
        onPress: async () => {
          await updateMultiAgentReviewState($, (prev) => {
            if (!prev) return null;
            return { ...prev, activeFilter: filter };
          });
        },
      });

    items.push(
      Box({
        flexDirection: 'row',
        gap: 1,
        marginTop: 1,
        marginBottom: 1,
        children: [
          makeTabButton('all', 'All', overallSummary.total),
          makeTabButton('correctness', 'Correctness', corrSummary.total),
          makeTabButton('security', 'Security', secSummary.total),
          makeTabButton('conventions', 'Conventions', convSummary.total),
        ],
      })
    );
  }

  // 3. Filtered findings list
  const visibleFindings =
    state.activeFilter === 'all'
      ? state.findings
      : state.findings.filter((f) => f.axis === state.activeFilter);

  if (visibleFindings.length === 0) {
    items.push(
      Box({
        padding: 1,
        children: [
          Text({
            children: [`\u2713 No findings in ${state.activeFilter} axis.`],
            color: 'green',
          }),
        ],
      })
    );
  } else {
    for (const f of visibleFindings) {
      const isBlocking = f.severity === 'blocking';
      const isAccepted = f.status === 'accepted';
      const isDismissed = f.status === 'dismissed';

      const findingChildren: any[] = [
        Box({
          flexDirection: 'row',
          gap: 1,
          children: [
            Text({
              children: [`[${f.severity.toUpperCase()}]`],
              bold: true,
              color: isBlocking ? 'error' : 'warning',
            }),
            Text({
              children: [f.location],
              bold: true,
            }),
            Text({
              children: [`(${f.axis})`],
              dim: true,
            }),
            isAccepted
              ? Text({ children: ['[ACCEPTED]'], color: 'green', bold: true })
              : isDismissed
                ? Text({ children: ['[DISMISSED]'], color: 'dim', bold: true })
                : Text({ children: ['[PENDING]'], color: 'info' }),
          ],
        }),
        Text({
          children: [f.summary],
        }),
      ];

      if (f.rule) {
        findingChildren.push(
          Text({
            children: [`Rule: ${f.rule}`],
            dim: true,
          })
        );
      }

      if (f.evidence) {
        findingChildren.push(
          Text({
            children: [`> ${f.evidence}`],
            dim: true,
          })
        );
      }

      if (f.alsoFlaggedBy && f.alsoFlaggedBy.length > 0) {
        findingChildren.push(
          Text({
            children: [`Also flagged by: ${f.alsoFlaggedBy.join(', ')}`],
            color: 'cyan',
            dim: true,
          })
        );
      }

      // Interactive Action Buttons
      if (Button) {
        const actionButtons: any[] = [];
        if (f.status !== 'accepted') {
          actionButtons.push(
            Button({
              key: `accept-${f.id}`,
              label: 'Accept',
              onPress: async () => {
                await updateMultiAgentReviewState($, (prev) => {
                  if (!prev) return null;
                  const updatedFindings = prev.findings.map((item) =>
                    item.id === f.id ? { ...item, status: 'accepted' as FindingStatus } : item
                  );
                  return {
                    ...prev,
                    findings: updatedFindings,
                    overallStatus: deriveOverallStatus(updatedFindings, prev.injectionAttempts),
                    updatedAt: new Date().toISOString(),
                  };
                });
                const next = await getMultiAgentReviewState($);
                if (next && next.payloadPath) {
                  await syncDecisionToDisk($, next, next.payloadPath, next.payloadHash);
                }
              },
            })
          );
        }
        if (f.status !== 'dismissed') {
          actionButtons.push(
            Button({
              key: `dismiss-${f.id}`,
              label: 'Dismiss',
              onPress: async () => {
                await updateMultiAgentReviewState($, (prev) => {
                  if (!prev) return null;
                  const updatedFindings = prev.findings.map((item) =>
                    item.id === f.id ? { ...item, status: 'dismissed' as FindingStatus } : item
                  );
                  return {
                    ...prev,
                    findings: updatedFindings,
                    overallStatus: deriveOverallStatus(updatedFindings, prev.injectionAttempts),
                    updatedAt: new Date().toISOString(),
                  };
                });
                const next = await getMultiAgentReviewState($);
                if (next && next.payloadPath) {
                  await syncDecisionToDisk($, next, next.payloadPath, next.payloadHash);
                }
              },
            })
          );
        }
        if (f.status !== 'pending') {
          actionButtons.push(
            Button({
              key: `restore-${f.id}`,
              label: 'Reset',
              onPress: async () => {
                await updateMultiAgentReviewState($, (prev) => {
                  if (!prev) return null;
                  const updatedFindings = prev.findings.map((item) =>
                    item.id === f.id ? { ...item, status: 'pending' as FindingStatus } : item
                  );
                  return {
                    ...prev,
                    findings: updatedFindings,
                    overallStatus: deriveOverallStatus(updatedFindings, prev.injectionAttempts),
                    updatedAt: new Date().toISOString(),
                  };
                });
                const next = await getMultiAgentReviewState($);
                if (next && next.payloadPath) {
                  await syncDecisionToDisk($, next, next.payloadPath, next.payloadHash);
                }
              },
            })
          );
        }

        findingChildren.push(
          Box({
            flexDirection: 'row',
            gap: 1,
            marginTop: 1,
            children: actionButtons,
          })
        );
      }

      items.push(
        Box({
          flexDirection: 'column',
          padding: 1,
          marginBottom: 1,
          borderStyle: 'single',
          borderColor: isDismissed ? 'gray' : isAccepted ? 'green' : isBlocking ? 'red' : 'yellow',
          children: findingChildren,
        })
      );
    }
  }

  // 4. Footer summary
  const acceptedCount = state.findings.filter((f) => f.status === 'accepted').length;
  const dismissedCount = state.findings.filter((f) => f.status === 'dismissed').length;
  const pendingCount = state.findings.filter((f) => f.status === 'pending').length;

  items.push(
    Box({
      flexDirection: 'row',
      gap: 1,
      marginTop: 1,
      children: [
        Text({ children: ['Status: '], bold: true }),
        Text({ children: [`${acceptedCount} accepted \u00B7 ${dismissedCount} dismissed \u00B7 ${pendingCount} pending`], dim: true }),
      ],
    })
  );

  return Box({
    flexDirection: 'column',
    padding: 1,
    children: items,
  });
}

/**
 * Pane render handler for Claude Code mod (Fail-Open).
 */
export async function handleRenderPane($: any, e: any, next?: any): Promise<any> {
  try {
    const state = await getMultiAgentReviewState($);
    if (!state) {
      if (typeof next === 'function') return next(e);
      return;
    }

    const rendered = renderMultiAgentReviewPane($, e, state);
    if (rendered) {
      return rendered;
    }
  } catch {
    // Fail-open to next render handler
  }

  if (typeof next === 'function') {
    return next(e);
  }
}

/**
 * Handles UI button presses dispatched by Claude Code's ui.press lifecycle hook.
 */
export async function handleUiPress($: any, e: any, next?: any): Promise<any> {
  if (!e || typeof e.element !== 'string') {
    if (typeof next === 'function') return next(e);
    return;
  }

  const element = e.element.trim();
  try {
    const state = await getMultiAgentReviewState($);
    if (!state) {
      if (typeof next === 'function') return next(e);
      return;
    }

    let updated = false;

    if (element === 'filter-all') {
      await updateMultiAgentReviewState($, (prev) => (prev ? { ...prev, activeFilter: 'all' } : null));
      updated = true;
    } else if (element === 'filter-correctness') {
      await updateMultiAgentReviewState($, (prev) =>
        prev ? { ...prev, activeFilter: 'correctness' } : null
      );
      updated = true;
    } else if (element === 'filter-security') {
      await updateMultiAgentReviewState($, (prev) =>
        prev ? { ...prev, activeFilter: 'security' } : null
      );
      updated = true;
    } else if (element === 'filter-conventions') {
      await updateMultiAgentReviewState($, (prev) =>
        prev ? { ...prev, activeFilter: 'conventions' } : null
      );
      updated = true;
    } else if (element.startsWith('accept-')) {
      const findingId = element.slice('accept-'.length);
      await updateMultiAgentReviewState($, (prev) => {
        if (!prev) return null;
        const findings = prev.findings.map((f) =>
          f.id === findingId ? { ...f, status: 'accepted' as FindingStatus } : f
        );
        return {
          ...prev,
          findings,
          overallStatus: deriveOverallStatus(findings, prev.injectionAttempts),
          updatedAt: new Date().toISOString(),
        };
      });
      updated = true;
    } else if (element.startsWith('dismiss-')) {
      const findingId = element.slice('dismiss-'.length);
      await updateMultiAgentReviewState($, (prev) => {
        if (!prev) return null;
        const findings = prev.findings.map((f) =>
          f.id === findingId ? { ...f, status: 'dismissed' as FindingStatus } : f
        );
        return {
          ...prev,
          findings,
          overallStatus: deriveOverallStatus(findings, prev.injectionAttempts),
          updatedAt: new Date().toISOString(),
        };
      });
      updated = true;
    } else if (element.startsWith('restore-') || element.startsWith('reset-')) {
      const findingId = element.startsWith('restore-')
        ? element.slice('restore-'.length)
        : element.slice('reset-'.length);
      await updateMultiAgentReviewState($, (prev) => {
        if (!prev) return null;
        const findings = prev.findings.map((f) =>
          f.id === findingId ? { ...f, status: 'pending' as FindingStatus } : f
        );
        return {
          ...prev,
          findings,
          overallStatus: deriveOverallStatus(findings, prev.injectionAttempts),
          updatedAt: new Date().toISOString(),
        };
      });
      updated = true;
    }

    if (updated) {
      const nextState = await getMultiAgentReviewState($);
      if (nextState && nextState.payloadPath) {
        await syncDecisionToDisk($, nextState, nextState.payloadPath, nextState.payloadHash);
      }
    }
  } catch {
    // Fail-open
  }

  if (typeof next === 'function') {
    return next(e);
  }
}

/**
 * Observes Bash tool calls to clear the review pane on subsequent git modifications
 * or hydrate candidate review payloads.
 */
export async function handleBashToolCall($: any, e: any, next?: any): Promise<any> {
  if (e && typeof e.command === 'string') {
    try {
      const command = e.command;
      // Auto-dismiss the review pane when git checkout, commit, reset, or merge runs
      if (/\bgit\s+(?:checkout|commit|merge|rebase|switch|reset|restore)\b/i.test(command)) {
        const currentState = await getMultiAgentReviewState($);
        if (currentState && currentState.payloadPath) {
          await invalidateDecisionOnDisk($, currentState.payloadPath);
        }
        await setMultiAgentReviewState($, null);
      } else {
        const rawPath = extractReviewPathFromCommand(command);
        if (rawPath) {
          let sessionCwd: string | undefined;
          try {
            sessionCwd = await $.session.cwd();
          } catch {
            sessionCwd = undefined;
          }

          const resolved = resolveReviewPath(rawPath, sessionCwd);
          if (resolved && isConfinedReviewPath(resolved, sessionCwd)) {
            const targetType = await classifyWriteTarget($, resolved);
            if (targetType === 'regular') {
              try {
                const content = await $.fs.read(resolved);
                if (typeof content === 'string' && content.trim().length > 0) {
                  const parsed = parseMultiAgentReviewPayload(content);
                  if (parsed.state) {
                    const payloadHash = computePayloadHash(content);
                    parsed.state.payloadPath = resolved;
                    parsed.state.payloadHash = payloadHash;
                    await setMultiAgentReviewState($, parsed.state);

                    // Check if a curated decision already exists beside it on disk
                    const decisionPath = getDecisionPath(resolved);
                    if (decisionPath && (await classifyWriteTarget($, decisionPath)) === 'regular') {
                      try {
                        const rawDecision = await $.fs.read(decisionPath);
                        const decisionObj = JSON.parse(rawDecision);
                        if (
                          decisionObj &&
                          decisionObj.schema_version === 1 &&
                          !decisionObj.invalidated &&
                          decisionObj.head_sha === parsed.state.headSha &&
                          decisionObj.source_payload_sha256 === payloadHash
                        ) {
                          const acceptedSet = new Set(decisionObj.accepted_ids || []);
                          const dismissedSet = new Set(decisionObj.dismissed_ids || []);
                          const reconciledFindings = parsed.state.findings.map((f) => {
                            if (acceptedSet.has(f.id)) {
                              return { ...f, status: 'accepted' as FindingStatus };
                            }
                            if (dismissedSet.has(f.id)) {
                              return { ...f, status: 'dismissed' as FindingStatus };
                            }
                            return f;
                          });
                          parsed.state.findings = reconciledFindings;
                          parsed.state.overallStatus = deriveOverallStatus(
                            reconciledFindings,
                            parsed.state.injectionAttempts
                          );
                          await setMultiAgentReviewState($, parsed.state);
                        }
                      } catch {
                        // Ignore corrupt or unparsable existing decision
                      }
                    }

                    // Open the comparison pane and invalidate UI
                    try {
                      await $.ui.open({ component: 'Pane' });
                    } catch {
                      // Fail-open
                    }
                    try {
                      $.ui.invalidate('ui.render');
                    } catch {
                      // Fail-open
                    }
                  }
                }
              } catch {
                // Fail-open on read error
              }
            }
          }
        }
      }
    } catch {
      // Safe no-op on failure (fail-open)
    }
  }

  if (typeof next === 'function') {
    return next(e);
  }
}

/**
 * Registers the magpie-pairing multi-agent review mod hooks.
 */
export function register(hooks: any): void {
  hooks('session.start', async ($: any, e: any, next: any) => {
    try {
      await setMultiAgentReviewState($, null);
    } catch {
      // Fail-open
    }
    if (typeof next === 'function') {
      return next(e);
    }
  });

  hooks('ui.render', { component: 'Pane' }, handleRenderPane);
  hooks('ui.press', handleUiPress);
  hooks('tool.call', { tool: 'Bash' }, handleBashToolCall);
}

export default register;
