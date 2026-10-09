# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Tests for the HTML render helpers (the stats spec)."""

from __future__ import annotations

from pr_management.stats import dashboard

from .helpers import make_ctx


def test_partial_banner_appears_only_when_fetch_was_incomplete():
    ctx = make_ctx()
    with_banner = dashboard.render_title(ctx, partial_fetch=True)
    without_banner = dashboard.render_title(ctx, partial_fetch=False)

    assert "INCOMPLETE DATA" in with_banner
    assert 'class="warn"' in with_banner
    assert "INCOMPLETE DATA" not in without_banner


def test_title_renders_repo_and_viewer():
    ctx = make_ctx(repo="apache/airflow", viewer="potiuk")
    out = dashboard.render_title(ctx)
    assert "apache/airflow" in out
    assert "@potiuk" in out


def test_recommendations_empty_state():
    out = dashboard.render_recommendations([])
    assert "No urgent actions detected" in out


def test_recommendations_render_titles_and_actions():
    recs = [
        {
            "priority": "high",
            "icon": "🔥",
            "title": "Triage 3 PRs",
            "detail": "do it",
            "action": "/magpie-pr-management:pr-triage all PR issues",
            "count": 3,
        }
    ]
    out = dashboard.render_recommendations(recs)
    assert "Triage 3 PRs" in out
    assert "/magpie-pr-management:pr-triage all PR issues" in out
    assert 'class="action high"' in out


def test_hero_rows_show_counts():
    hero = {
        "open_total": 42,
        "non_drafts": 30,
        "drafts": 12,
        "contribs": 25,
        "collabs": 17,
        "ready": 5,
        "untriaged": 8,
        "untriaged_4w": 2,
        "qc_triaged": 10,
        "defacto": 4,
        "ai_triaged": 6,
        "bots": 3,
        "bots_dependabot": 2,
        "bots_other": 1,
        "contrib_nondraft_total": 20,
    }
    health = ("✅ Healthy", "#56d364")
    out = dashboard.render_hero_rows(hero, health)
    assert "42" in out
    assert "✅ Healthy" in out
    assert "Backlog state" in out


def test_html_escaping_in_title():
    ctx = make_ctx(repo="a/<script>", viewer="x")
    out = dashboard.render_title(ctx)
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
