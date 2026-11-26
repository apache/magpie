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
  QueueItemSeverity,
  QueueItemStage,
  QueueStageFilter,
  SecurityLauncherSkill,
  SecurityQueueItem,
  SecurityTriageQueueState,
  StagedLauncherAction,
} from './types.js';

export type WriteTarget = 'regular' | 'missing' | 'unsafe';

export const triageQueueState = atom(
  { plugin: 'magpie-security', key: 'triageQueueState' },
  null as SecurityTriageQueueState | null
);

export const SECURITY_QUEUE_STATE_KEY = 'magpie-security.triageQueueState';
export const SECURITY_QUEUE_PANE_ID = 'magpie-security:triage-queue';
export const SECURITY_QUEUE_COMMAND = 'magpie-security-queue';
export const QUEUE_INPUT_FILENAME = '.magpie-security-triage-queue.json';
export const QUEUE_ACTION_FILENAME = '.magpie-security-triage-action.json';
export const MAX_QUEUE_ITEMS = 100;

const ALLOWED_SKILLS: ReadonlyArray<SecurityLauncherSkill> = [
  'issue-sync',
  'cve-allocate',
  'issue-triage',
];

const ALLOWED_STAGES: ReadonlyArray<QueueItemStage> = [
  'needs-sync',
  'needs-cve',
  'ready-for-fix',
];

const ALLOWED_FILTERS: ReadonlyArray<QueueStageFilter> = [
  'all',
  'needs-sync',
  'needs-cve',
  'ready-for-fix',
];

const ALLOWED_SEVERITIES: ReadonlyArray<QueueItemSeverity> = [
  'critical',
  'high',
  'medium',
  'low',
  'unknown',
];

const SAFE_ITEM_ID_RE = /^[A-Za-z0-9#._-]{1,40}$/;

/**
 * Strips ANSI CSI/OSC/2-byte escapes, Unicode bidirectional overrides,
 * zero-width/format controls, and C0/C1 control codes from untrusted advisory text.
 * Preserves quotes and syntax characters for inert Text rendering.
 */
export function sanitizeSecurityText(raw: unknown, maxLen: number = 100): string {
  if (typeof raw !== 'string') return '';
  return raw
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-Z\\-_]/g, '')
    .replace(/[\u202A-\u202E\u2066-\u2069\u200E\u200F\u061C\u2028\u2029]/g, '')
    .replace(/[\u200B-\u200D\uFEFF\u2060\u00AD\uFE00-\uFE0F]/g, '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/[\x00-\x1f\x7f-\x9f]/g, '')
    .replace(/ {2,}/g, ' ')
    .trim()
    .slice(0, maxLen);
}

/**
 * Validates that a queue item identifier is safe for display and skill command interpolation.
 */
export function isValidQueueItemId(raw: unknown): raw is string {
  return typeof raw === 'string' && SAFE_ITEM_ID_RE.test(raw);
}

/**
 * Checks whether a skill name is in the allowed launcher set.
 */
export function isAllowedLauncherSkill(raw: unknown): raw is SecurityLauncherSkill {
  return typeof raw === 'string' && (ALLOWED_SKILLS as readonly string[]).includes(raw);
}

/**
 * Confines local queue/action file access strictly to the exact staging filenames
 * directly under the active workspace root, rejecting traversal and null bytes.
 */
export function isConfinedQueuePath(filePath: string, cwd: string): boolean {
  if (!filePath || !cwd || typeof filePath !== 'string' || typeof cwd !== 'string') {
    return false;
  }
  if (filePath.includes('\0') || cwd.includes('\0')) {
    return false;
  }

  const normPath = filePath.replace(/\\/g, '/');
  const normCwd = cwd.replace(/\\/g, '/').replace(/\/+$/, '');
  if (!normCwd || normPath.split('/').includes('..')) {
    return false;
  }

  return (
    normPath === `${normCwd}/${QUEUE_INPUT_FILENAME}` ||
    normPath === `${normCwd}/${QUEUE_ACTION_FILENAME}`
  );
}

/**
 * Classifies a file target via $.fs.stat, refusing symlinks and non-regular files.
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
 * Reads the security triage queue state from the session store, failing open to null.
 */
export async function getSecurityTriageQueueState(
  $: any
): Promise<SecurityTriageQueueState | null> {
  try {
    return (await read($, triageQueueState)) ?? null;
  } catch {
    return null;
  }
}

/**
 * Writes the security triage queue state to the session store and invalidates ui.render.
 */
export async function setSecurityTriageQueueState(
  $: any,
  value: SecurityTriageQueueState | null
): Promise<void> {
  try {
    await update($, triageQueueState, () => value);
    try {
      $.ui.invalidate('ui.render');
    } catch {
      // Fail-open in headless/non-interactive harnesses
    }
  } catch {
    // Fail-open in headless/non-interactive harnesses
  }
}

/**
 * Parses and bounds a local `.magpie-security-triage-queue.json` payload.
 */
export function parseSecurityQueuePayload(
  rawJson: string,
  nowIso: string = new Date().toISOString()
): { ok: true; state: SecurityTriageQueueState } | { ok: false; error: string } {
  if (typeof rawJson !== 'string' || !rawJson.trim()) {
    return { ok: false, error: 'Empty security queue payload' };
  }

  let parsed: any;
  try {
    parsed = JSON.parse(rawJson);
  } catch {
    return { ok: false, error: 'Malformed JSON in security queue payload' };
  }

  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.items)) {
    return { ok: false, error: 'Security queue payload must be an object with an items array' };
  }

  const items: SecurityQueueItem[] = [];
  for (const rawItem of parsed.items) {
    if (items.length >= MAX_QUEUE_ITEMS) break;
    if (!rawItem || typeof rawItem !== 'object') continue;

    const cleanId = sanitizeSecurityText(rawItem.id, 40);
    if (!isValidQueueItemId(cleanId)) continue;

    const cleanTitle = sanitizeSecurityText(rawItem.title, 100) || '(untitled advisory)';
    const stage: QueueItemStage = (ALLOWED_STAGES as readonly string[]).includes(rawItem.stage)
      ? (rawItem.stage as QueueItemStage)
      : 'needs-sync';
    const severity: QueueItemSeverity = (ALLOWED_SEVERITIES as readonly string[]).includes(
      rawItem.severity
    )
      ? (rawItem.severity as QueueItemSeverity)
      : 'unknown';

    const rawCve = sanitizeSecurityText(rawItem.cveId, 32);
    const cveId = /^CVE-\d{4}-\d{4,}$/.test(rawCve) ? rawCve : null;
    const needsCve = typeof rawItem.needsCve === 'boolean' ? rawItem.needsCve : cveId === null;
    const updatedAt = sanitizeSecurityText(rawItem.updatedAt, 40) || nowIso;

    items.push({
      id: cleanId,
      title: cleanTitle,
      stage,
      severity,
      cveId,
      needsCve,
      updatedAt,
    });
  }

  const firstItem = items[0];
  return {
    ok: true,
    state: {
      items,
      activeFilter: 'all',
      selectedItemId: firstItem ? firstItem.id : null,
      lastLaunchedAction: null,
      syncError: null,
      updatedAt: sanitizeSecurityText(parsed.updatedAt, 40) || nowIso,
    },
  };
}

/**
 * Formats a safe, local-only skill launcher action object (omits advisory titles/embargo text).
 */
export function buildLauncherAction(
  itemId: string,
  skill: SecurityLauncherSkill,
  nowIso: string = new Date().toISOString()
): StagedLauncherAction | null {
  if (!isValidQueueItemId(itemId) || !isAllowedLauncherSkill(skill)) {
    return null;
  }
  return {
    itemId,
    skill,
    command: `/magpie-security:${skill} ${itemId}`,
    stagedAt: nowIso,
  };
}

/**
 * Counts queue items per stage for header/tab badges.
 */
export function summarizeQueueStages(items: ReadonlyArray<SecurityQueueItem>): {
  all: number;
  needsSync: number;
  needsCve: number;
  readyForFix: number;
} {
  let needsSync = 0;
  let needsCve = 0;
  let readyForFix = 0;
  for (const item of items) {
    if (item.stage === 'needs-sync') needsSync += 1;
    else if (item.stage === 'needs-cve') needsCve += 1;
    else if (item.stage === 'ready-for-fix') readyForFix += 1;
  }
  return {
    all: items.length,
    needsSync,
    needsCve,
    readyForFix,
  };
}

/**
 * Renders the interactive Local Security Triage Queue Pane.
 */
export function renderSecurityQueuePane(
  Box: any,
  Text: any,
  Button: any,
  state: SecurityTriageQueueState | null
): any {
  if (!Box || !Text || !Button || !state) return null;

  const counts = summarizeQueueStages(state.items);
  const visibleItems =
    state.activeFilter === 'all'
      ? state.items
      : state.items.filter((it) => it.stage === state.activeFilter);

  const tabDefs: Array<{ key: QueueStageFilter; label: string }> = [
    { key: 'all', label: `All (${counts.all})` },
    { key: 'needs-sync', label: `Needs Sync (${counts.needsSync})` },
    { key: 'needs-cve', label: `Needs CVE (${counts.needsCve})` },
    { key: 'ready-for-fix', label: `Ready (${counts.readyForFix})` },
  ];

  const tabButtons = tabDefs.map((tab) =>
    Button({
      key: `sq:filter:${tab.key}`,
      label: state.activeFilter === tab.key ? `[${tab.label}]` : tab.label,
      variant: state.activeFilter === tab.key ? 'primary' : 'secondary',
    })
  );

  const itemCards =
    visibleItems.length === 0
      ? [
          Box({
            padding: 1,
            children: [
              Text({
                color: 'muted',
                children: ['No open advisories or trackers in this filter.'],
              }),
            ],
          }),
        ]
      : visibleItems.slice(0, 12).map((item) => {
          const isSelected = state.selectedItemId === item.id;
          const badgeColor =
            item.severity === 'critical' || item.severity === 'high'
              ? 'error'
              : item.severity === 'medium'
                ? 'warning'
                : 'info';
          const cveText = item.cveId ? item.cveId : item.needsCve ? 'CVE needed' : 'No CVE';

          const actionButtons = [
            Button({
              key: `sq:launch:issue-sync:${item.id}`,
              label: '[Sync]',
              variant: 'secondary',
            }),
          ];
          if (item.needsCve || !item.cveId) {
            actionButtons.push(
              Button({
                key: `sq:launch:cve-allocate:${item.id}`,
                label: '[Allocate CVE]',
                variant: 'primary',
              })
            );
          }
          actionButtons.push(
            Button({
              key: `sq:launch:issue-triage:${item.id}`,
              label: '[Triage]',
              variant: 'secondary',
            })
          );

          return Box({
            padding: 1,
            borderStyle: isSelected ? 'round' : 'single',
            children: [
              Text({
                color: badgeColor,
                bold: true,
                children: [`[${item.severity.toUpperCase()}] ${item.id} (${cveText})`],
              }),
              Text({
                children: [item.title],
              }),
              Box({
                flexDirection: 'row',
                gap: 1,
                children: actionButtons,
              }),
            ],
          });
        });

  const footerChildren: any[] = [];
  if (visibleItems.length > 12) {
    footerChildren.push(
      Text({
        color: 'muted',
        children: [`Showing 12 of ${visibleItems.length} items in this filter.`],
      })
    );
  }
  if (state.lastLaunchedAction) {
    footerChildren.push(
      Text({
        color: 'success',
        bold: true,
        children: [`Staged: ${state.lastLaunchedAction.command}`],
      })
    );
  }
  if (state.syncError) {
    footerChildren.push(
      Text({
        color: 'warning',
        children: [`Warning: ${sanitizeSecurityText(state.syncError, 120)}`],
      })
    );
  }

  return Box({
    flexDirection: 'column',
    padding: 1,
    children: [
      Box({
        flexDirection: 'row',
        justifyContent: 'space-between',
        children: [
          Text({
            bold: true,
            children: ['Security Triage Queue (Local-Only)'],
          }),
          Button({
            key: 'sq:close',
            label: '[Close]',
            variant: 'secondary',
          }),
        ],
      }),
      Box({
        flexDirection: 'row',
        gap: 1,
        children: tabButtons,
      }),
      ...itemCards,
      ...footerChildren,
    ],
  });
}

/**
 * Handles `/magpie-security-queue`: reads `.magpie-security-triage-queue.json`
 * under strict workspace confinement, hydrates state, and opens the Pane.
 */
export async function handleQueueCommand($: any): Promise<string> {
  try {
    let cwd = '';
    try {
      cwd = (await $.session.root()) || '';
    } catch {
      // Fallback to cwd below
    }
    if (!cwd) {
      try {
        cwd = (await $.session.cwd()) || '';
      } catch {
        cwd = '';
      }
    }
    if (!cwd) {
      return 'Security Triage Queue: unable to resolve workspace root.';
    }

    const normCwd = String(cwd).replace(/\\/g, '/').replace(/\/+$/, '');
    const queuePath = `${normCwd}/${QUEUE_INPUT_FILENAME}`;
    if (!isConfinedQueuePath(queuePath, normCwd)) {
      return 'Security Triage Queue: refused unconfined queue path.';
    }

    const queueTarget = await classifyWriteTarget($, queuePath);
    if (queueTarget === 'missing') {
      return `No local queue file found at ${QUEUE_INPUT_FILENAME}.`;
    }
    if (queueTarget === 'unsafe') {
      return `Security Triage Queue: refusing to read symlink or non-regular file at ${QUEUE_INPUT_FILENAME}.`;
    }

    let rawContent: string | null = null;
    try {
      rawContent = await $.fs.read(queuePath);
    } catch {
      rawContent = null;
    }

    if (!rawContent) {
      return `No local queue file found at ${QUEUE_INPUT_FILENAME}.`;
    }

    const parsed = parseSecurityQueuePayload(rawContent);
    if (!parsed.ok) {
      return `Security Triage Queue error: ${parsed.error}`;
    }

    await setSecurityTriageQueueState($, parsed.state);

    try {
      await $.ui.open({ component: 'Pane' });
    } catch {
      // Fail-open when $.ui.open is unavailable
    }

    const summary = summarizeQueueStages(parsed.state.items);
    return `Security Triage Queue loaded: ${summary.all} item(s) (${summary.needsSync} sync, ${summary.needsCve} CVE, ${summary.readyForFix} ready).`;
  } catch {
    return 'Security Triage Queue: failed to load local queue.';
  }
}

/**
 * Handles `ui.render` for the Security Triage Queue Pane, failing open when empty.
 */
export async function handleRenderSecurityQueuePane(
  $: any,
  e: any,
  next: any
): Promise<any> {
  try {
    if (!e || (e.component && e.component !== 'Pane')) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const state = await getSecurityTriageQueueState($);
    if (!state) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const ui = $.ui.resolve(e);
    if (!ui?.Box || !ui?.Text || !ui?.Button) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const rendered = renderSecurityQueuePane(ui.Box, ui.Text, ui.Button, state);
    if (rendered) return rendered;
  } catch {
    // Fail-open
  }
  return typeof next === 'function' ? next(e) : undefined;
}

/**
 * Handles interactive `ui.press` events for filter tabs, launcher buttons, and close.
 */
export async function handleSecurityQueuePress($: any, e: any, next: any): Promise<any> {
  try {
    const element = typeof e?.element === 'string' ? e.element : '';
    if (!element) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const state = await getSecurityTriageQueueState($);
    if (!state) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    if (element === 'sq:close') {
      await setSecurityTriageQueueState($, null);
      return;
    }

    if (element.startsWith('sq:filter:')) {
      const nextFilter = element.slice('sq:filter:'.length);
      if ((ALLOWED_FILTERS as readonly string[]).includes(nextFilter)) {
        await setSecurityTriageQueueState($, {
          ...state,
          activeFilter: nextFilter as QueueStageFilter,
        });
        return;
      }
    }

    if (element.startsWith('sq:select:')) {
      const targetId = element.slice('sq:select:'.length);
      const exists = state.items.some((item) => item.id === targetId);
      if (exists) {
        await setSecurityTriageQueueState($, {
          ...state,
          selectedItemId: targetId,
        });
        return;
      }
    }

    if (element.startsWith('sq:launch:')) {
      const rest = element.slice('sq:launch:'.length);
      const colonIdx = rest.indexOf(':');
      if (colonIdx > 0) {
        const rawSkill = rest.slice(0, colonIdx);
        const rawItemId = rest.slice(colonIdx + 1);
        const itemExists = state.items.some((item) => item.id === rawItemId);

        if (itemExists && isAllowedLauncherSkill(rawSkill) && isValidQueueItemId(rawItemId)) {
          const action = buildLauncherAction(rawItemId, rawSkill);
          if (action) {
            let syncError: string | null = null;
            try {
              let cwd = '';
              try {
                cwd = (await $.session.root()) || '';
              } catch {
                // Fallback to cwd
              }
              if (!cwd) {
                try {
                  cwd = (await $.session.cwd()) || '';
                } catch {
                  cwd = '';
                }
              }
              const normCwd = String(cwd).replace(/\\/g, '/').replace(/\/+$/, '');
              const actionPath = `${normCwd}/${QUEUE_ACTION_FILENAME}`;
              if (normCwd && isConfinedQueuePath(actionPath, normCwd)) {
                if ((await classifyWriteTarget($, actionPath)) === 'unsafe') {
                  syncError = `Refusing to write to symlink or non-regular file: ${QUEUE_ACTION_FILENAME}`;
                } else {
                  await $.fs.write(actionPath, JSON.stringify(action, null, 2) + '\n');
                }
              }
            } catch {
              syncError = `Could not write ${QUEUE_ACTION_FILENAME}; run command manually.`;
            }

            await setSecurityTriageQueueState($, {
              ...state,
              selectedItemId: rawItemId,
              lastLaunchedAction: action,
              syncError,
            });
            return;
          }
        }
      }
    }
  } catch {
    // Fail-open
  }

  return typeof next === 'function' ? next(e) : undefined;
}

/**
 * Invalidates stale local queue state on mutating git operations (checkout, switch, reset, commit).
 */
export async function clearSecurityQueueOnMutatingGit($: any, command: string): Promise<void> {
  try {
    if (/\bgit\s+(?:checkout|switch|reset|commit|merge|rebase|restore)\b/i.test(command)) {
      if (await getSecurityTriageQueueState($)) {
        await setSecurityTriageQueueState($, null);
      }
    }
  } catch {
    // Fail-open
  }
}

/**
 * Bash tool.call helper for unit-testing mutating git command invalidation.
 */
export async function handleSecurityQueueBashToolCall(
  $: any,
  e: any,
  next: any
): Promise<any> {
  const cmd =
    typeof e?.command === 'string'
      ? e.command
      : typeof e?.input?.command === 'string'
        ? e.input.command
        : '';
  if (cmd) {
    await clearSecurityQueueOnMutatingGit($, cmd);
  }
  return typeof next === 'function' ? next(e) : undefined;
}

/**
 * Registers the magpie-security Local Security Triage Queue Pane hooks.
 */
export function register(on: any): void {
  on('session.start', async ($: any, _e: any, next: any) => {
    await setSecurityTriageQueueState($, null);
    try {
      await $.command.register({
        name: SECURITY_QUEUE_COMMAND,
        description: 'Open the Local Security Triage Queue side pane',
      });
    } catch {
      // Fail-open if command registration is unsupported
    }
    if (typeof next === 'function') return next(_e);
  });

  on(
    'command.run',
    { command: SECURITY_QUEUE_COMMAND },
    async ($: any, _e: any, _next: any) => {
      const text = await handleQueueCommand($);
      return { text };
    }
  );

  on('ui.render', { component: 'Pane' }, ($: any, e: any, next: any) =>
    handleRenderSecurityQueuePane($, e, next)
  );

  on('ui.press', ($: any, e: any, next: any) =>
    handleSecurityQueuePress($, e, next)
  );

  on('tool.call', { tool: 'Bash' }, ($: any, e: any, next: any) =>
    handleSecurityQueueBashToolCall($, e, next)
  );
}

export default register;
