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
  ContributorCandidateItem,
  ContributorLauncherSkill,
  ContributorSweepState,
  StagedContributorAction,
} from './types.js';

export type WriteTarget = 'regular' | 'missing' | 'unsafe';

export const contributorSweepState = atom(
  { plugin: 'magpie-contributor-growth', key: 'contributorSweepState' },
  null as ContributorSweepState | null
);

export const CONTRIBUTOR_QUEUE_STATE_KEY = 'magpie-contributor-growth.contributorSweepState';
export const CONTRIBUTOR_QUEUE_COMMAND = 'magpie-contributor-queue';
export const SWEEP_QUEUE_FILENAME = '.magpie-contributor-sweep-queue.json';
export const SWEEP_ACTION_FILENAME = '.magpie-contributor-sweep-action.json';
export const PERSONAL_LAYER_SUBDIR = 'apache-magpie';
export const MAX_CANDIDATES = 100;

const ALLOWED_SKILLS: ReadonlyArray<ContributorLauncherSkill> = [
  'activity-sweep',
  'nomination',
];

const SAFE_HANDLE_RE = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$/;

/**
 * Strips ANSI CSI/OSC/2-byte escapes, Unicode bidirectional overrides,
 * zero-width/format controls, and C0/C1 control codes from untrusted text.
 */
export function sanitizeContributorText(raw: unknown, maxLen: number = 100): string {
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
 * Validates that a contributor GitHub handle is safe for display and skill interpolation.
 */
export function isValidGitHubHandle(raw: unknown): raw is string {
  return typeof raw === 'string' && SAFE_HANDLE_RE.test(raw);
}

/**
 * Checks whether a skill name is in the allowed contributor-growth launcher set.
 */
export function isAllowedContributorSkill(raw: unknown): raw is ContributorLauncherSkill {
  return typeof raw === 'string' && (ALLOWED_SKILLS as readonly string[]).includes(raw);
}

/**
 * Confines local sweep queue/action file access strictly to the exact staging filenames
 * directly under the resolved `<git-common-dir>/apache-magpie` personal-layer directory.
 */
export function isConfinedContributorPath(filePath: string, personalDir: string): boolean {
  if (!filePath || !personalDir || typeof filePath !== 'string' || typeof personalDir !== 'string') {
    return false;
  }
  if (filePath.includes('\0') || personalDir.includes('\0')) {
    return false;
  }

  const normPath = filePath.replace(/\\/g, '/');
  const normDir = personalDir.replace(/\\/g, '/').replace(/\/+$/, '');
  if (!normDir || normPath.split('/').includes('..')) {
    return false;
  }

  return (
    normPath === `${normDir}/${SWEEP_QUEUE_FILENAME}` ||
    normPath === `${normDir}/${SWEEP_ACTION_FILENAME}`
  );
}

/**
 * Normalizes an absolute POSIX or Windows drive path, refusing relative paths,
 * `..` segments, trailing slashes, and non-drive backslashes.
 */
export function normalizeAbsolutePath(path: string): string | null {
  if (!path || typeof path !== 'string') return null;
  if (path.endsWith('/') || path.endsWith('\\')) return null;
  if (path.includes('\\') && !/^[A-Za-z]:\\/.test(path)) return null;
  const p = path.replace(/\\/g, '/');
  const drive = /^[A-Za-z]:\//.exec(p);
  const prefix = drive ? drive[0].slice(0, 2) : '';
  const rest = drive ? p.slice(2) : p;
  if (!rest.startsWith('/')) return null;
  const parts = rest.split('/').filter((s) => s !== '' && s !== '.');
  if (parts.includes('..')) return null;
  return `${prefix}/${parts.join('/')}`;
}

function resolveRelativePath(base: string, rel: string): string | null {
  const normRel = rel.replace(/\\/g, '/').trim();
  if (!normRel || normRel.includes('\0')) return null;
  const abs = normalizeAbsolutePath(normRel);
  if (abs) return abs;
  const normBase = normalizeAbsolutePath(base);
  if (!normBase) return null;
  const drive = /^[A-Za-z]:/.exec(normBase)?.[0] ?? '';
  const baseParts = normBase.slice(drive.length).split('/').filter(Boolean);
  for (const seg of normRel.split('/')) {
    if (!seg || seg === '.') continue;
    if (seg === '..') {
      if (baseParts.length === 0) return null;
      baseParts.pop();
    } else {
      baseParts.push(seg);
    }
  }
  return `${drive}/${baseParts.join('/')}`;
}

/**
 * Resolves `<git-common-dir>/apache-magpie` for a workspace root via pure `$.fs`,
 * supporting standard checkouts and linked worktrees while refusing symlinked `.git`.
 */
export async function resolvePersonalLayerDir(
  $: any,
  normRoot: string
): Promise<string | null> {
  const cleanRoot = normalizeAbsolutePath(normRoot);
  if (!cleanRoot) return null;
  const dotGitPath = `${cleanRoot}/.git`;
  let stat: any;
  try {
    stat = await $.fs.stat(dotGitPath);
  } catch {
    return null;
  }
  if (!stat || stat.isLink !== false) return null;

  if (stat.kind === 'directory') {
    return `${dotGitPath}/${PERSONAL_LAYER_SUBDIR}`;
  }

  if (stat.kind === 'file') {
    let content: string | null = null;
    try {
      content = await $.fs.read(dotGitPath);
    } catch {
      return null;
    }
    if (!content) return null;
    const match = /^gitdir:\s*(.+)$/m.exec(content);
    if (!match || !match[1]) return null;
    const gitDir = resolveRelativePath(cleanRoot, match[1].trim());
    if (!gitDir) return null;

    let gitCommonDir = gitDir;
    try {
      const commonContent = await $.fs.read(`${gitDir}/commondir`);
      if (typeof commonContent === 'string' && commonContent.trim()) {
        const resolved = resolveRelativePath(gitDir, commonContent.trim());
        if (resolved) gitCommonDir = resolved;
      }
    } catch {
      // Single worktree or no commondir file
    }
    return `${gitCommonDir}/${PERSONAL_LAYER_SUBDIR}`;
  }

  return null;
}

/**
 * Resolves the session working directory and root, each undefined when unavailable.
 */
async function sessionRootsOf($: any): Promise<(string | undefined)[]> {
  const roots: (string | undefined)[] = [];
  try {
    roots.push((await $.session.cwd()) || undefined);
  } catch {
    roots.push(undefined);
  }
  try {
    roots.push((await $.session.root()) || undefined);
  } catch {
    roots.push(undefined);
  }
  return roots;
}

/**
 * Derives the sibling action file path from a hydrated queue file path.
 */
export function getActionPathFromQueuePath(queuePath: string): string {
  const norm = queuePath.replace(/\\/g, '/');
  if (norm.endsWith(`/${SWEEP_QUEUE_FILENAME}`)) {
    return `${norm.slice(0, -SWEEP_QUEUE_FILENAME.length)}${SWEEP_ACTION_FILENAME}`;
  }
  return SWEEP_ACTION_FILENAME;
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
 * Reads contributorSweepState from the session store, failing open to null.
 */
export async function getContributorSweepState(
  $: any
): Promise<ContributorSweepState | null> {
  try {
    return (await read($, contributorSweepState)) ?? null;
  } catch {
    return null;
  }
}

/**
 * Writes contributorSweepState to the session store and invalidates ui.render.
 */
export async function setContributorSweepState(
  $: any,
  value: ContributorSweepState | null
): Promise<void> {
  try {
    await update($, contributorSweepState, () => value);
    try {
      $.ui.invalidate('ui.render');
    } catch {
      // Fail-open in headless/non-interactive harnesses
    }
  } catch {
    // Fail-open in headless/non-interactive harnesses
  }
}

function clampNonNegInt(raw: unknown): number {
  if (typeof raw !== 'number' || !Number.isFinite(raw) || raw < 0) return 0;
  return Math.floor(raw);
}

/**
 * Parses a local `.magpie-contributor-sweep-queue.json` payload, sorting
 * candidates alphabetically by handle (case-insensitively) and bounding to MAX_CANDIDATES.
 */
export function parseContributorSweepPayload(
  rawJson: string,
  nowIso: string = new Date().toISOString()
): { ok: true; state: ContributorSweepState } | { ok: false; error: string } {
  if (typeof rawJson !== 'string' || !rawJson.trim()) {
    return { ok: false, error: 'Empty contributor sweep payload' };
  }

  let parsed: any;
  try {
    parsed = JSON.parse(rawJson);
  } catch {
    return { ok: false, error: 'Malformed JSON in contributor sweep payload' };
  }

  if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.items)) {
    return {
      ok: false,
      error: 'Contributor sweep payload must be an object with an items array',
    };
  }

  const allItems: ContributorCandidateItem[] = [];
  const seen = new Set<string>();
  for (const rawItem of parsed.items) {
    if (!rawItem || typeof rawItem !== 'object') continue;

    const cleanHandle = sanitizeContributorText(rawItem.handle, 39).replace(/^@+/, '');
    if (!isValidGitHubHandle(cleanHandle)) continue;
    const key = cleanHandle.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);

    const displayName = sanitizeContributorText(rawItem.displayName, 60) || cleanHandle;
    const prCount = clampNonNegInt(rawItem.prCount);
    const reviewCount = clampNonNegInt(rawItem.reviewCount);
    const window = sanitizeContributorText(rawItem.window, 16) || '6m';
    const note = sanitizeContributorText(rawItem.note, 100);
    const updatedAt = sanitizeContributorText(rawItem.updatedAt, 40) || nowIso;

    allItems.push({
      handle: cleanHandle,
      displayName,
      prCount,
      reviewCount,
      window,
      note,
      updatedAt,
    });
  }

  allItems.sort((a, b) => {
    const ka = a.handle.toLowerCase();
    const kb = b.handle.toLowerCase();
    return ka < kb ? -1 : ka > kb ? 1 : 0;
  });

  const items = allItems.slice(0, MAX_CANDIDATES);
  const firstItem = items[0];
  return {
    ok: true,
    state: {
      items,
      selectedHandle: firstItem ? firstItem.handle : null,
      lastLaunchedAction: null,
      syncError: null,
      updatedAt: sanitizeContributorText(parsed.updatedAt, 40) || nowIso,
    },
  };
}

/**
 * Formats a safe, local-only skill launcher action object (omits private candidate notes).
 */
export function buildContributorLauncherAction(
  handle: string,
  skill: ContributorLauncherSkill,
  nowIso: string = new Date().toISOString()
): StagedContributorAction | null {
  if (!isValidGitHubHandle(handle) || !isAllowedContributorSkill(skill)) {
    return null;
  }
  return {
    handle,
    skill,
    command: `/magpie-contributor-growth:${skill} ${handle}`,
    stagedAt: nowIso,
  };
}

/**
 * Renders the interactive Contributor Activity Sweep Pane (plain counts, alphabetical order).
 */
export function renderContributorSweepPane(
  Box: any,
  Text: any,
  Button: any,
  state: ContributorSweepState | null
): any {
  if (!Box || !Text || !Button || !state) return null;

  const maxVisible = 12;
  const shown = state.items.slice(0, maxVisible);
  const itemCards =
    shown.length > 0
      ? shown.map((item) => {
          const isSelected = state.selectedHandle === item.handle;
          const stats = `${item.prCount} PRs · ${item.reviewCount} reviews (${item.window})`;
          const noteSuffix = item.note ? ` — ${item.note}` : '';
          return Box({
            flexDirection: 'column',
            padding: 1,
            borderStyle: 'single',
            borderColor: isSelected ? 'cyan' : 'gray',
            children: [
              Text({
                bold: isSelected,
                children: [`@${item.handle} (${item.displayName}) · ${stats}${noteSuffix}`],
              }),
              Box({
                flexDirection: 'row',
                gap: 1,
                children: [
                  Button({
                    key: `cs:select:${item.handle}`,
                    label: isSelected ? '[Selected]' : '[Select]',
                    variant: isSelected ? 'primary' : 'secondary',
                  }),
                  Button({
                    key: `cs:launch:activity-sweep:${item.handle}`,
                    label: '[Sweep]',
                    variant: 'secondary',
                  }),
                  Button({
                    key: `cs:launch:nomination:${item.handle}`,
                    label: '[Nominate]',
                    variant: 'secondary',
                  }),
                ],
              }),
            ],
          });
        })
      : [
          Text({
            color: 'muted',
            children: ['No candidates in queue.'],
          }),
        ];

  const footerChildren: any[] = [];
  if (state.items.length > maxVisible) {
    footerChildren.push(
      Text({
        color: 'muted',
        children: [`Showing ${maxVisible} of ${state.items.length} candidates.`],
      })
    );
  }
  if (state.lastLaunchedAction && !state.syncError) {
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
        children: [`Warning: ${sanitizeContributorText(state.syncError, 120)}`],
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
            children: [`Contributor Activity Sweep (${state.items.length})`],
          }),
          Button({
            key: 'cs:close',
            label: '[Close]',
            variant: 'secondary',
          }),
        ],
      }),
      ...itemCards,
      ...footerChildren,
    ],
  });
}

function shouldKeepLaunchedAction(
  action: StagedContributorAction | null,
  items: ReadonlyArray<ContributorCandidateItem>
): StagedContributorAction | null {
  if (!action) return null;
  return items.some((it) => it.handle === action.handle) ? action : null;
}

/**
 * Validates, reads, parses, and hydrates `.magpie-contributor-sweep-queue.json`
 * under `<git-common-dir>/apache-magpie/`, then opens the Pane.
 */
export async function loadAndHydrateContributorQueue(
  $: any,
  queuePath: string,
  personalDir: string,
  preserveUiState: boolean = false
): Promise<{ ok: true; message: string } | { ok: false; message: string }> {
  if (!isConfinedContributorPath(queuePath, personalDir)) {
    return {
      ok: false,
      message: 'Contributor Sweep Queue: refused unconfined queue path.',
    };
  }

  const queueTarget = await classifyWriteTarget($, queuePath);
  if (queueTarget === 'missing') {
    return { ok: false, message: `No local queue file found at ${SWEEP_QUEUE_FILENAME}.` };
  }
  if (queueTarget === 'unsafe') {
    return {
      ok: false,
      message: `Contributor Sweep Queue: refusing to read symlink or non-regular file at ${SWEEP_QUEUE_FILENAME}.`,
    };
  }

  let rawContent: string | null = null;
  try {
    rawContent = await $.fs.read(queuePath);
  } catch {
    rawContent = null;
  }

  if (!rawContent) {
    return { ok: false, message: `No local queue file found at ${SWEEP_QUEUE_FILENAME}.` };
  }

  const parsed = parseContributorSweepPayload(rawContent);
  if (!parsed.ok) {
    return { ok: false, message: `Contributor Sweep Queue error: ${parsed.error}` };
  }

  let nextState: ContributorSweepState = {
    ...parsed.state,
    queuePath,
  };

  if (preserveUiState) {
    const prev = await getContributorSweepState($);
    if (prev) {
      const selectedStillExists =
        prev.selectedHandle !== null &&
        nextState.items.some((it) => it.handle === prev.selectedHandle);
      nextState = {
        ...nextState,
        selectedHandle: selectedStillExists
          ? prev.selectedHandle
          : nextState.selectedHandle,
        lastLaunchedAction: shouldKeepLaunchedAction(
          prev.lastLaunchedAction,
          nextState.items
        ),
      };
    }
  }

  await setContributorSweepState($, nextState);

  try {
    await $.ui.open({ component: 'Pane' });
  } catch {
    // Fail-open when $.ui.open is unavailable
  }

  return {
    ok: true,
    message: `Contributor Sweep Queue loaded: ${nextState.items.length} candidate(s).`,
  };
}

/**
 * Resolves the `<git-common-dir>/apache-magpie` directory for the active session.
 */
async function resolveSessionPersonalDir(
  $: any,
  preferCwd: boolean = false
): Promise<string | null> {
  const roots = await sessionRootsOf($);
  const ordered = preferCwd ? [roots[0], roots[1]] : [roots[1], roots[0]];
  let firstResolved: string | null = null;
  for (const r of ordered) {
    if (!r) continue;
    const personalDir = await resolvePersonalLayerDir($, r);
    if (!personalDir) continue;
    if (!firstResolved) firstResolved = personalDir;
    if ((await classifyWriteTarget($, `${personalDir}/${SWEEP_QUEUE_FILENAME}`)) !== 'missing') {
      return personalDir;
    }
  }
  return firstResolved;
}

/**
 * Handles `/magpie-contributor-queue`: reads `.magpie-contributor-sweep-queue.json`
 * under `<git-common-dir>/apache-magpie/`, hydrates state, and opens the Pane.
 */
export async function handleContributorQueueCommand($: any): Promise<string> {
  try {
    const personalDir = await resolveSessionPersonalDir($, false);
    if (!personalDir) {
      return 'Contributor Sweep Queue: unable to resolve git personal-layer directory.';
    }

    const queuePath = `${personalDir}/${SWEEP_QUEUE_FILENAME}`;
    const res = await loadAndHydrateContributorQueue($, queuePath, personalDir, false);
    return res.message;
  } catch {
    return 'Contributor Sweep Queue: failed to load local queue.';
  }
}

/**
 * Handles `ui.render` for the Contributor Activity Sweep Pane, failing open when empty.
 */
export async function handleRenderContributorSweepPane(
  $: any,
  e: any,
  next: any
): Promise<any> {
  try {
    if (!e || (e.component && e.component !== 'Pane')) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const state = await getContributorSweepState($);
    if (!state) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const ui = $.ui.resolve(e);
    if (!ui?.Box || !ui?.Text || !ui?.Button) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const rendered = renderContributorSweepPane(ui.Box, ui.Text, ui.Button, state);
    if (rendered) return rendered;
  } catch {
    // Fail-open
  }
  return typeof next === 'function' ? next(e) : undefined;
}

/**
 * Handles interactive `ui.press` events for selection, launcher buttons, and close.
 */
export async function handleContributorSweepPress($: any, e: any, next: any): Promise<any> {
  try {
    const element = typeof e?.element === 'string' ? e.element : '';
    if (!element) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    const state = await getContributorSweepState($);
    if (!state) {
      return typeof next === 'function' ? next(e) : undefined;
    }

    if (element === 'cs:close') {
      await setContributorSweepState($, null);
      return;
    }

    if (element.startsWith('cs:select:')) {
      const targetHandle = element.slice('cs:select:'.length);
      const exists = state.items.some((item) => item.handle === targetHandle);
      if (exists) {
        await setContributorSweepState($, {
          ...state,
          selectedHandle: targetHandle,
        });
        return;
      }
    }

    if (element.startsWith('cs:launch:')) {
      const rest = element.slice('cs:launch:'.length);
      const colonIdx = rest.indexOf(':');
      if (colonIdx > 0) {
        const rawSkill = rest.slice(0, colonIdx);
        const rawHandle = rest.slice(colonIdx + 1);
        const itemExists = state.items.some((item) => item.handle === rawHandle);

        if (
          itemExists &&
          isAllowedContributorSkill(rawSkill) &&
          isValidGitHubHandle(rawHandle)
        ) {
          const action = buildContributorLauncherAction(rawHandle, rawSkill);
          if (action) {
            let syncError: string | null = null;
            try {
              const personalDir = state.queuePath
                ? state.queuePath.replace(/\\/g, '/').replace(/\/[^/]+$/, '')
                : await resolveSessionPersonalDir($, false);
              const actionPath = state.queuePath
                ? getActionPathFromQueuePath(state.queuePath)
                : personalDir
                  ? `${personalDir}/${SWEEP_ACTION_FILENAME}`
                  : '';
              if (
                personalDir &&
                actionPath &&
                isConfinedContributorPath(actionPath, personalDir)
              ) {
                if ((await classifyWriteTarget($, actionPath)) === 'unsafe') {
                  syncError = `Refusing to write to symlink or non-regular file: ${SWEEP_ACTION_FILENAME}`;
                } else {
                  await $.fs.write(actionPath, JSON.stringify(action, null, 2) + '\n');
                }
              } else {
                syncError = `Could not resolve git personal-layer directory for ${SWEEP_ACTION_FILENAME}; run command manually.`;
              }
            } catch {
              syncError = `Could not write ${SWEEP_ACTION_FILENAME}; run command manually.`;
            }

            await setContributorSweepState($, {
              ...state,
              selectedHandle: rawHandle,
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
 * Invalidates stale local sweep state on mutating git operations.
 */
export async function clearContributorSweepOnMutatingGit(
  $: any,
  command: string
): Promise<void> {
  try {
    if (/\bgit\s+(?:checkout|switch|reset|commit|merge|rebase|restore)\b/i.test(command)) {
      if (await getContributorSweepState($)) {
        await setContributorSweepState($, null);
      }
    }
  } catch {
    // Fail-open
  }
}

/**
 * Write tool.call hook: auto-hydrates `.magpie-contributor-sweep-queue.json`
 * when written under `<git-common-dir>/apache-magpie/`.
 */
export async function handleContributorSweepWriteToolCall(
  $: any,
  e: any,
  next: any
): Promise<any> {
  const result = typeof next === 'function' ? await next(e) : undefined;
  try {
    const filePath =
      typeof e?.file_path === 'string'
        ? e.file_path
        : typeof e?.path === 'string'
          ? e.path
          : typeof e?.filePath === 'string'
            ? e.filePath
            : typeof e?.input?.file_path === 'string'
              ? e.input.file_path
              : '';
    if (
      filePath &&
      /(?:^|\/)\.magpie-contributor-sweep-queue\.json$/.test(filePath.replace(/\\/g, '/'))
    ) {
      const normalized = normalizeAbsolutePath(filePath);
      const roots = await sessionRootsOf($);
      for (const r of roots) {
        if (!r) continue;
        const personalDir = await resolvePersonalLayerDir($, r);
        if (!personalDir) continue;
        if (normalized && isConfinedContributorPath(normalized, personalDir)) {
          await loadAndHydrateContributorQueue($, normalized, personalDir, true);
          break;
        }
      }
    }
  } catch {
    // Fail-open
  }
  return result;
}

/**
 * Bash tool.call hook: clears stale state on mutating git before execution,
 * and auto-hydrates `.magpie-contributor-sweep-queue.json` after execution.
 */
export async function handleContributorSweepBashToolCall(
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
    await clearContributorSweepOnMutatingGit($, cmd);
  }
  const result = typeof next === 'function' ? await next(e) : undefined;
  try {
    const isMutatingGit = /\bgit\s+(?:checkout|switch|reset|commit|merge|rebase|restore)\b/i.test(
      cmd
    );
    const isReadOnlyGit =
      /\bgit\s+(?:check-ignore|status|diff|log|ls-files)\b/i.test(cmd) &&
      !/(?:>|>>|\btee\b)/i.test(cmd);
    if (
      cmd &&
      cmd.includes(SWEEP_QUEUE_FILENAME) &&
      !isMutatingGit &&
      !isReadOnlyGit &&
      !/^\s*rm\b/i.test(cmd)
    ) {
      const personalDir = await resolveSessionPersonalDir($, true);
      if (personalDir) {
        await loadAndHydrateContributorQueue(
          $,
          `${personalDir}/${SWEEP_QUEUE_FILENAME}`,
          personalDir,
          true
        );
      }
    }
  } catch {
    // Fail-open
  }
  return result;
}

/**
 * Registers the magpie-contributor-growth Contributor Activity Sweep Pane hooks.
 */
export function register(on: any): void {
  on('session.start', async ($: any, _e: any, next: any) => {
    await setContributorSweepState($, null);
    try {
      await $.command.register({
        name: CONTRIBUTOR_QUEUE_COMMAND,
        description: 'Open the Contributor Activity Sweep side pane',
      });
    } catch {
      // Fail-open if command registration is unsupported
    }
    if (typeof next === 'function') return next(_e);
  });

  on(
    'command.run',
    { command: CONTRIBUTOR_QUEUE_COMMAND },
    async ($: any, _e: any, _next: any) => {
      const text = await handleContributorQueueCommand($);
      return { text };
    }
  );

  on('ui.render', { component: 'Pane' }, ($: any, e: any, next: any) =>
    handleRenderContributorSweepPane($, e, next)
  );

  on('ui.press', ($: any, e: any, next: any) =>
    handleContributorSweepPress($, e, next)
  );

  on('tool.call', { tool: 'Write' }, ($: any, e: any, next: any) =>
    handleContributorSweepWriteToolCall($, e, next)
  );

  on('tool.call', { tool: 'Bash' }, ($: any, e: any, next: any) =>
    handleContributorSweepBashToolCall($, e, next)
  );
}

export default register;
