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
  ParsePrStatsResult,
  PrStatsAreaPressure,
  PrStatsFunnel,
  PrStatsPaneState,
  PrStatsWeeklyTotals,
} from './types.js';

export const PR_STATS_STATE_KEY = 'magpie-pr-management.prStatsPaneState';
export const DEFAULT_STATS_OUT = 'dashboard.html';
export const MAX_PRESSURE_AREAS = 8;

/**
 * Strips ANSI escapes, Unicode BiDi overrides, zero-width chars, C0/C1 controls,
 * and markdown/HTML delimiters from untrusted strings before rendering in UI Text.
 */
export function sanitizeStatsText(text: unknown, maxLen: number = 120): string {
  if (typeof text !== 'string') return '';
  return text
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\u202A-\u202E\u2066-\u2069\u200E\u200F\u061C\u2028\u2029]/g, '')
    .replace(/[\u200B-\u200D\uFEFF\u2060\u00AD\uFE00-\uFE0F]/g, '')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, ' ')
    .replace(/[`<>"']/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLen);
}

function toNonNegInt(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.floor(n);
}

function normalizePosix(p: string): string {
  const unified = p.replace(/\\/g, '/');
  if (!unified || unified.includes('\0')) return '';
  const isAbs = unified.startsWith('/');
  const out: string[] = [];
  for (const seg of unified.split('/')) {
    if (!seg || seg === '.') continue;
    if (seg === '..') return '';
    out.push(seg);
  }
  return (isAbs ? '/' : '') + out.join('/');
}

/**
 * Mirrors Python's `Path(out).with_suffix('.json')` on the final path segment.
 */
export function toStatsJsonPath(outPath: string): string {
  const norm = normalizePosix(outPath.trim());
  if (!norm) return '';
  const slash = norm.lastIndexOf('/');
  const dir = slash >= 0 ? norm.slice(0, slash + 1) : '';
  const base = slash >= 0 ? norm.slice(slash + 1) : norm;
  if (!base) return '';
  const dot = base.lastIndexOf('.');
  const stem = dot > 0 ? base.slice(0, dot) : base;
  return `${dir}${stem}.json`;
}

/**
 * Extracts the `.json` sidecar path from a `pr-management stats build` Bash command.
 * Returns null if the command is not a stats build invocation or has an unsafe `--out` path.
 */
export function extractStatsJsonPathFromCommand(command: string): string | null {
  if (typeof command !== 'string') return null;
  if (!/\bpr-management\s+stats\s+build\b/.test(command)) return null;

  const eqMatch = command.match(/--out=(?:"([^"\0]+)"|'([^'\0]+)'|([^\s\0]+))/);
  const spMatch = command.match(/--out\s+(?:"([^"\0]+)"|'([^'\0]+)'|([^\s\0]+))/);
  const rawOut =
    (eqMatch && (eqMatch[1] ?? eqMatch[2] ?? eqMatch[3])) ||
    (spMatch && (spMatch[1] ?? spMatch[2] ?? spMatch[3])) ||
    DEFAULT_STATS_OUT;

  if (!rawOut || rawOut.includes('..') || /[\x00-\x1f\x7f]/.test(rawOut)) {
    return null;
  }
  const jsonPath = toStatsJsonPath(rawOut);
  return jsonPath || null;
}

/**
 * Resolves relative paths against cwd and verifies the target lies inside
 * session roots or standard scratch/temp directories without traversal.
 */
export function resolveConfinedStatsPath(
  rawPath: string,
  sessionCwd: string | null | undefined,
  sessionRoot: string | null | undefined,
  extraRoots: readonly string[] = []
): string | null {
  if (typeof rawPath !== 'string' || !rawPath.trim()) return null;
  const trimmed = rawPath.trim();
  if (trimmed.includes('..') || trimmed.includes('\0')) return null;

  const cwdNorm = sessionCwd ? normalizePosix(sessionCwd) : '';
  const candidate = trimmed.startsWith('/') || /^[A-Za-z]:[\\/]/.test(trimmed)
    ? normalizePosix(trimmed)
    : cwdNorm
      ? normalizePosix(`${cwdNorm}/${trimmed}`)
      : '';
  if (!candidate) return null;

  const allowedBases = [
    sessionRoot ? normalizePosix(sessionRoot) : '',
    cwdNorm,
    '/tmp',
    '/private/tmp',
    '/var/folders',
    ...extraRoots.map((r) => normalizePosix(r)),
  ].filter(Boolean);

  for (const base of allowedBases) {
    const cleanBase = base.endsWith('/') ? base.slice(0, -1) : base;
    if (candidate === cleanBase || candidate.startsWith(`${cleanBase}/`)) {
      return candidate;
    }
  }
  return null;
}

/**
 * Parses the `intermediates` JSON sidecar emitted by `pr-management stats build`.
 * Preserves aggregate-only, read-only invariants (no author or per-PR drill-in data).
 */
export function parsePrStatsPayload(
  raw: string,
  jsonPath: string,
  nowIso: string = new Date().toISOString()
): ParsePrStatsResult {
  if (typeof raw !== 'string' || !raw.trim()) {
    return { ok: false, error: 'Empty PR stats payload' };
  }
  let parsed: any;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ok: false, error: 'Malformed JSON in PR stats sidecar' };
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, error: 'PR stats payload must be a JSON object' };
  }

  const repo = sanitizeStatsText(parsed.repo, 80);
  const healthRating = sanitizeStatsText(parsed.health_rating, 40);
  if (!repo || !healthRating) {
    return { ok: false, error: 'Missing required repo or health_rating in PR stats sidecar' };
  }

  const rawFunnel = parsed.funnel && typeof parsed.funnel === 'object' ? parsed.funnel : {};
  const funnel: PrStatsFunnel = {
    ready: toNonNegInt(rawFunnel.ready),
    responded: toNonNegInt(rawFunnel.responded),
    waiting_manual: toNonNegInt(rawFunnel.waiting_manual),
    waiting_ai: toNonNegInt(rawFunnel.waiting_ai),
    untriaged: toNonNegInt(rawFunnel.untriaged),
    other: toNonNegInt(rawFunnel.other),
  };

  const rawAreas = Array.isArray(parsed.pressure_areas) ? parsed.pressure_areas : [];
  const pressureAreas: PrStatsAreaPressure[] = rawAreas
    .filter((item: any) => item && typeof item === 'object' && typeof item.area === 'string')
    .map((item: any) => ({
      area: sanitizeStatsText(item.area, 48) || '(unlabeled)',
      score: toNonNegInt(item.score),
      contribs: toNonNegInt(item.contribs),
      age_4w: toNonNegInt(item.age_4w),
      age_1to4w: toNonNegInt(item.age_1to4w),
      age_rec: toNonNegInt(item.age_rec),
    }))
    .sort((a: PrStatsAreaPressure, b: PrStatsAreaPressure) => b.score - a.score)
    .slice(0, MAX_PRESSURE_AREAS);

  const rawWeekly =
    parsed.weekly_velocity_totals && typeof parsed.weekly_velocity_totals === 'object'
      ? parsed.weekly_velocity_totals
      : {};
  const weeklyVelocityTotals: PrStatsWeeklyTotals = {
    merged: toNonNegInt(rawWeekly.merged),
    closed_not_merged: toNonNegInt(rawWeekly.closed_not_merged),
  };

  const capNoteClean = parsed.cap_note ? sanitizeStatsText(parsed.cap_note, 180) : '';

  return {
    ok: true,
    state: {
      repo,
      fetchedAt: sanitizeStatsText(parsed.fetched_at, 40) || nowIso,
      cutoff: sanitizeStatsText(parsed.cutoff, 40),
      jsonPath,
      healthRating,
      openCount: toNonNegInt(parsed.open_count),
      closedCount: toNonNegInt(parsed.closed_count),
      readyCount: toNonNegInt(parsed.ready_count),
      untriagedCount: toNonNegInt(parsed.untriaged_count),
      untriaged4wCount: toNonNegInt(parsed.untriaged_4w_count),
      engagedCount: toNonNegInt(parsed.engaged_count),
      aiTriagedCount: toNonNegInt(parsed.ai_triaged_count),
      recommendationCount: toNonNegInt(parsed.recommendation_count),
      funnel,
      pressureAreas,
      weeklyVelocityTotals,
      partial: Boolean(parsed.partial),
      capNote: capNoteClean || null,
      syncError: null,
      isOpen: true,
      updatedAt: nowIso,
    },
  };
}

function renderBar(score: number, maxScore: number, width: number = 10): string {
  if (maxScore <= 0 || score <= 0) return '░'.repeat(width);
  const filled = Math.min(width, Math.max(1, Math.round((score / maxScore) * width)));
  return '█'.repeat(filled) + '░'.repeat(width - filled);
}

/**
 * Pure UI renderer for the PR Dashboard & Stats Visualizer Pane.
 */
export function renderPrStatsPane(
  Box: any,
  Text: any,
  Button: any,
  state: PrStatsPaneState
): any {
  const children: any[] = [];

  children.push(
    Text({
      key: 'ps-header',
      bold: true,
      children: `PR Backlog Stats — ${state.repo} (${state.healthRating})`,
    })
  );

  children.push(
    Text({
      key: 'ps-meta',
      dimColor: true,
      children: `Snapshot: ${state.fetchedAt}${state.cutoff ? ` • Closed since ${state.cutoff.slice(0, 10)}` : ''}`,
    })
  );

  if (state.partial || state.capNote) {
    const warnParts: string[] = [];
    if (state.partial) warnParts.push('Partial snapshot (fetch cut short)');
    if (state.capNote) warnParts.push(state.capNote);
    children.push(
      Text({
        key: 'ps-partial-warn',
        color: 'yellow',
        bold: true,
        children: `Warning: ${warnParts.join(' — ')}`,
      })
    );
  }

  if (state.syncError) {
    children.push(
      Text({
        key: 'ps-sync-error',
        color: 'red',
        children: `Warning: ${sanitizeStatsText(state.syncError, 160)}`,
      })
    );
  }

  children.push(
    Text({
      key: 'ps-hero',
      children:
        `Open: ${state.openCount} • Ready: ${state.readyCount} • Untriaged: ${state.untriagedCount}` +
        ` (>4w: ${state.untriaged4wCount}) • Engaged: ${state.engagedCount} • Closed: ${state.closedCount}` +
        ` • Recs: ${state.recommendationCount}`,
    })
  );

  children.push(
    Text({
      key: 'ps-funnel',
      children:
        `Funnel: ready=${state.funnel.ready} | responded=${state.funnel.responded}` +
        ` | waiting_manual=${state.funnel.waiting_manual} | waiting_ai=${state.funnel.waiting_ai}` +
        ` | untriaged=${state.funnel.untriaged} | other=${state.funnel.other}`,
    })
  );

  children.push(
    Text({
      key: 'ps-velocity',
      children:
        `Velocity (window): merged=${state.weeklyVelocityTotals.merged}` +
        ` | closed_not_merged=${state.weeklyVelocityTotals.closed_not_merged}`,
    })
  );

  if (state.pressureAreas.length > 0) {
    const maxScore = Math.max(...state.pressureAreas.map((a) => a.score), 1);
    children.push(
      Text({
        key: 'ps-areas-title',
        bold: true,
        children: 'Top Area Pressure (aggregate):',
      })
    );
    for (const area of state.pressureAreas) {
      children.push(
        Text({
          key: `ps-area-${area.area}`,
          children:
            `  ${area.area} ${renderBar(area.score, maxScore)} score=${area.score}` +
            ` (${area.contribs} PRs, >4w:${area.age_4w}, 1-4w:${area.age_1to4w}, <1w:${area.age_rec})`,
        })
      );
    }
  }

  children.push(
    Box({
      key: 'ps-actions',
      flexDirection: 'row',
      gap: 1,
      children: [
        Button({
          key: 'ps-btn-refresh',
          id: 'ps:refresh',
          label: 'Refresh',
          variant: 'secondary',
        }),
        Button({
          key: 'ps-btn-close',
          id: 'ps:close',
          label: 'Close',
          variant: 'secondary',
        }),
      ],
    })
  );

  return Box({
    key: 'ps-root',
    flexDirection: 'column',
    gap: 1,
    children,
  });
}
