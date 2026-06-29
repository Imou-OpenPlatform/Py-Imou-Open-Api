# Py-Imou-Open-Api 治理对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align Py-Imou-Open-Api governance (Issue/PR templates, CI workflows, local lint tooling, contributor docs) with Imou-Home-Assistant, preserving documented repo-specific differences.

**Architecture:** Single `chore/align-governance-with-imou-ha` branch in `Py-Imou-Open-Api`. Copy structural patterns from `Imou-Home-Assistant` as the canonical source; substitute paths (`pyimouapi` vs `custom_components`), check names (`Version-sync` vs `Manifest`), and SDK-specific PR/issue wording. No business code changes.

**Tech Stack:** GitHub Actions, pre-commit, Ruff, codespell, yamllint, uv, bash scripts

**Spec:** `docs/superpowers/specs/2026-06-29-py-imou-governance-alignment-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `.github/workflows/ci-lint.yml` | Modify | Bump checkout to v7 (3 places) |
| `.github/workflows/ci-test.yml` | Modify | Bump checkout to v7 |
| `.github/workflows/close_inactive_issues.yaml` | Modify | v7 + HA Chinese header comments |
| `.github/workflows/issue_opened_auto_reply.yaml` | Modify | HA Chinese header comment |
| `.pre-commit-config.yaml` | Modify | ruff-pre-commit `v0.15.0` → `v0.8.3` |
| `script/lint` | Modify | Remove CONTRIBUTING.md/AGENTS.md from codespell (match HA) |
| `CONTRIBUTING.md` | Modify | Add Dependency upgrades section + 中文附录条目 |
| `AGENTS.md` | Modify | Add Dependabot scope bullet |
| `.github/PULL_REQUEST_TEMPLATE.md` | Modify | Add manual verification checklist item |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Modify | Logs hint with tracebacks |
| `CHANGELOG.md` | Modify | Unreleased entry for governance alignment |
| `docs/superpowers/specs/...-design.md` | Modify | Status `待审阅` → `已批准` |

**No changes:** `dependabot.yml`, `CODEOWNERS`, `close_inactive_author_issues.py`, `script/lint-check`, `script/setup`, `script/test`, `publish.yml`, `pyimouapi/*`, `tests/*`

---

### Task 1: Create feature branch

**Files:**
- Modify: (none — git only)

- [ ] **Step 1: Ensure clean working tree**

Run from repo root:

```bash
cd /home/open/projects/Py-Imou-Open-Api
git status
```

Expected: `nothing to commit, working tree clean` (or only intentional local changes stashed)

- [ ] **Step 2: Create branch from main**

```bash
git checkout main
git pull origin main
git checkout -b chore/align-governance-with-imou-ha
```

Expected: `Switched to a new branch 'chore/align-governance-with-imou-ha'`

---

### Task 2: Bump actions/checkout to v7 in CI workflows

**Files:**
- Modify: `.github/workflows/ci-lint.yml`
- Modify: `.github/workflows/ci-test.yml`

- [ ] **Step 1: Update ci-lint.yml**

Replace every `actions/checkout@v6` with `actions/checkout@v7` (3 occurrences at lines ~26, ~54, ~77):

```yaml
      - uses: actions/checkout@v7
```

- [ ] **Step 2: Update ci-test.yml**

Replace `actions/checkout@v6` with `actions/checkout@v7` (1 occurrence at line ~23):

```yaml
      - uses: actions/checkout@v7
```

- [ ] **Step 3: Verify no v6 remains in workflows**

```bash
grep -r 'checkout@v6' .github/workflows/ || echo "OK: no v6 left"
```

Expected: `OK: no v6 left`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci-lint.yml .github/workflows/ci-test.yml
git commit -m "chore(ci): bump actions/checkout to v7 in lint and test workflows"
```

---

### Task 3: Add HA workflow comments and bump checkout in issue automation

**Files:**
- Modify: `.github/workflows/issue_opened_auto_reply.yaml`
- Modify: `.github/workflows/close_inactive_issues.yaml`

- [ ] **Step 1: Add header comment to issue_opened_auto_reply.yaml**

Insert as line 1 (before `name:`):

```yaml
# 新建 Issue 时由 bot 自动回复；字段清单见各 ISSUE_TEMPLATE，此处仅补充支持工单链接。
```

- [ ] **Step 2: Rewrite close_inactive_issues.yaml header and checkout**

Replace the file top through `name:` with:

```yaml
# 按评论时间线：若**最后一条评论**来自维护者，且超过 STALE_AFTER_DAYS 天 → 打 stale 标签；
# 超过 INACTIVE_DAYS 天 → 评论并关闭。若最后一条来自非维护者，则移除 stale（表示已有新回复）。
# 带标签 no-auto-close 或 enhancement 的 Issue 整单跳过（不打 stale、不关）。
# 请在仓库 Labels 中预先创建与 STALE_LABEL 同名的标签（默认 stale）。
name: Close inactive issues after maintainer reply
```

And change checkout step to:

```yaml
        uses: actions/checkout@v7
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/issue_opened_auto_reply.yaml .github/workflows/close_inactive_issues.yaml
git commit -m "chore(ci): align issue automation workflows with Imou-Home-Assistant"
```

---

### Task 4: Align pre-commit and script/lint with HA

**Files:**
- Modify: `.pre-commit-config.yaml`
- Modify: `script/lint`

- [ ] **Step 1: Downgrade ruff-pre-commit rev in .pre-commit-config.yaml**

Change:

```yaml
    rev: v0.15.0
```

To:

```yaml
    rev: v0.8.3
```

- [ ] **Step 2: Align script/lint codespell paths with HA**

Replace line 6 in `script/lint`:

```bash
uv run codespell pyimouapi tests README.md CHANGELOG.md
```

(Remove `CONTRIBUTING.md AGENTS.md` — CI `lint-check` and Spell job still include them.)

- [ ] **Step 3: Run pre-commit to verify hooks still pass**

```bash
script/setup
uv run pre-commit run --all-files
```

Expected: all hooks Passed

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml script/lint
git commit -m "chore: align pre-commit ruff rev and script/lint with Imou-Home-Assistant"
```

---

### Task 5: Update contributor documentation

**Files:**
- Modify: `CONTRIBUTING.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Insert Dependency upgrades section in CONTRIBUTING.md**

Insert after the `## Code standards` section (after line 59, before `## Testing`):

```markdown
## Dependency upgrades

[Dependabot](https://docs.github.com/en/code-security/dependabot) opens weekly PRs for **GitHub Actions** only. Python dependencies are upgraded manually so `pyproject.toml` and `uv.lock` stay in sync.

### Dev-only packages (`ruff`, `pytest`, etc.)

1. Bump the version in `pyproject.toml` (`[dependency-groups].dev`).
2. Regenerate the lockfile: `uv lock`
3. Run `script/lint-check` and `script/test`.
4. Open a `chore/…` PR.

### Runtime packages (`aiohttp`, `simpleeval`, etc.)

1. Bump in `pyproject.toml` `[project].dependencies`.
2. `uv lock`
3. Run `script/lint-check` and `script/test`; add tests if public API changes.
4. Open a `chore/…` PR. When releasing, bump `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml` together.

```

- [ ] **Step 2: Extend 中文附录 in CONTRIBUTING.md**

Add item 6 to the numbered list in `## Appendix: 中文快速指引`:

```markdown
6. **依赖升级**：仅 GitHub Actions 由 Dependabot 自动提 PR；Python 依赖手动升级。发版时须同步 bump `setup.py`、`pyimouapi/__init__.py`、`pyproject.toml`。
```

- [ ] **Step 3: Add Dependabot bullet to AGENTS.md**

In `## Code constraints`, add after the version-sync bullet:

```markdown
- Dependabot covers GitHub Actions only. Python dependency bumps are manual (`pyproject.toml` + `uv lock`).
```

- [ ] **Step 4: Commit**

```bash
git add CONTRIBUTING.md AGENTS.md
git commit -m "docs: add dependency upgrade guidance aligned with Imou-Home-Assistant"
```

---

### Task 6: Update GitHub templates

**Files:**
- Modify: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `.github/ISSUE_TEMPLATE/bug_report.md`

- [ ] **Step 1: Add manual verification checklist to PR template**

In `.github/PULL_REQUEST_TEMPLATE.md`, after the `script/lint-check` line, add:

```markdown
- [ ] I have manually verified the changed behavior (see **Testing** below).
```

Replace the Testing HTML comment with:

```markdown
<!-- Required: unit tests, manual API calls, and/or Home Assistant integration verification. -->
```

- [ ] **Step 2: Update bug_report Logs hint**

In `.github/ISSUE_TEMPLATE/bug_report.md`, change the Logs code block content to:

```text
Paste relevant logs here (include tracebacks if applicable)
```

- [ ] **Step 3: Commit**

```bash
git add .github/PULL_REQUEST_TEMPLATE.md .github/ISSUE_TEMPLATE/bug_report.md
git commit -m "chore: align PR and bug report templates with Imou-Home-Assistant"
```

---

### Task 7: Update CHANGELOG and spec status

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/specs/2026-06-29-py-imou-governance-alignment-design.md`

- [ ] **Step 1: Add Unreleased entry to CHANGELOG.md**

Under `## [Unreleased]` (create if missing):

```markdown
### Changed

- Governance aligned with Imou-Home-Assistant: checkout@v7, workflow comments, pre-commit ruff rev, contributor docs, PR/issue templates.
```

- [ ] **Step 2: Update spec status**

Change line 4 in the design spec from:

```markdown
**状态** 待审阅
```

To:

```markdown
**状态** 已批准
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md docs/superpowers/specs/2026-06-29-py-imou-governance-alignment-design.md
git commit -m "docs: mark governance alignment spec approved and note in CHANGELOG"
```

---

### Task 8: Final verification

**Files:**
- Test: (verification only — no new test files)

- [ ] **Step 1: Run full local lint suite**

```bash
script/lint-check
```

Expected: exit code 0

- [ ] **Step 2: Run tests**

```bash
script/test
```

Expected: all tests pass, exit code 0

- [ ] **Step 3: Run pre-commit on all files**

```bash
uv run pre-commit run --all-files
```

Expected: all hooks Passed

- [ ] **Step 4: Diff audit against HA canonical source**

```bash
diff <(grep -n 'checkout@' /home/open/projects/Imou-Home-Assistant/.github/workflows/ci-lint.yml | sed 's/custom_components/pyimouapi/g') \
     <(grep -n 'checkout@' .github/workflows/ci-lint.yml)
```

Expected: only path-specific line content differs (job structure same checkout version)

- [ ] **Step 5: Push branch and open PR**

```bash
git push -u origin chore/align-governance-with-imou-ha
```

Open PR to `main` with title `chore: align governance with Imou-Home-Assistant` and verify CI shows green: **Lint**, **Spell**, **YAML**, **Version-sync**, **Test**.

---

## Spec Coverage Checklist

| Spec § | Task |
|--------|------|
| §4.1 checkout v7 | Task 2, 3 |
| §4.1 workflow comments | Task 3 |
| §4.1 pre-commit ruff v0.8.3 | Task 4 |
| §4.1 script/lint | Task 4 |
| §5.1 CONTRIBUTING Dependency upgrades | Task 5 |
| §5.2 AGENTS.md | Task 5 |
| §5.3 PR template | Task 6 |
| §5.4 bug_report | Task 6 |
| §7 verification | Task 8 |
| §6 branch protection | Manual post-merge (document in PR description) |
| §4.3 retained differences | No tasks (intentional) |

## Maintainer Post-Merge

After PR merge, confirm GitHub branch protection on `main` per `.github/BRANCH_PROTECTION.md` — required checks: Lint, Spell, YAML, Version-sync, Test.
