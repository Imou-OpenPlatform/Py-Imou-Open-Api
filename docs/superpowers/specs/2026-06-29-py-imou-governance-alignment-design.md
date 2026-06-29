# Py-Imou-Open-Api 治理规则全量对齐 Imou-Home-Assistant — 设计规格

**日期** 2026-06-29
**状态** 已批准
**范围** 以 Imou-Home-Assistant 为规范源，对 Py-Imou-Open-Api 的 Issue/PR 模板、CI、本地工具链与贡献文档做全量审计并对齐（保留合理仓库差异）。

---

## 1. 背景与目标

### 背景

- Py-Imou-Open-Api 在 1.2.8（PR #7）已做过一轮治理对齐，但用户要求**从零全量审查**，不假设既有工作已完备。
- Imou-Home-Assistant 在 2026-06 有后续更新（如 `actions/checkout@v7`、Issue workflow 注释、CONTRIBUTING 依赖升级专节等），Py 仓库尚未完全跟上。

### 目标

1. 建立治理**等价矩阵**：除文档化的合理差异外，Py 与 HA 治理文件一一对应。
2. 补齐 Py 仓库中仍落后的配置与文档项。
3. 确保 `script/lint-check` 与 CI required checks 完全一致。
4. 维护者可在 GitHub Settings 按文档启用分支保护。

### 非目标

- 修改 Imou-Home-Assistant 仓库（HA 自身 `script/lint` codespell 路径不完整等问题不在本次范围）。
- 引入共享治理模板基础设施（方案 B/C 延后）。
- 变更 `pyimouapi` 业务代码或发版逻辑（`publish.yml` 保持不变）。

---

## 2. 方案选择

采用 **等价矩阵审计（方案 A）**：

- 以 HA 为规范源，逐文件对照、补齐差距。
- 显式记录合理差异（Version-sync vs Manifest、publish.yml vs release_assets 等）。
- 单次 `chore/align-governance-with-imou-ha` PR 交付，无额外基础设施。

---

## 3. 治理范围

| 层级 | 文件 |
|------|------|
| GitHub 模板 | `.github/PULL_REQUEST_TEMPLATE.md`、`.github/ISSUE_TEMPLATE/*` |
| CI/CD | `ci-lint.yml`、`ci-test.yml`、`issue_opened_auto_reply.yaml`、`close_inactive_issues.yaml` |
| 自动化脚本 | `.github/scripts/close_inactive_author_issues.py` |
| 依赖机器人 | `dependabot.yml` |
| 所有权 | `CODEOWNERS` |
| 本地工具链 | `.pre-commit-config.yaml`、`.yamllint.yml`、`script/*` |
| 文档 | `CONTRIBUTING.md`、`AGENTS.md` |
| 工具配置 | `pyproject.toml` 中 ruff / codespell / pytest 段 |
| GitHub 设置 | 分支保护 required checks（文档化，无法入库） |

**仓库专属、不纳入对齐：**

- Py：`publish.yml`
- HA：`release_assets.yaml`、`hassfest`、`hacs`、`hacs.json`

---

## 4. 等价矩阵审计结果

### 4.1 必须修改

| 文件 | HA 现状 | Py 现状 | 对齐动作 |
|------|---------|---------|----------|
| `.github/workflows/ci-lint.yml` | checkout v7 | checkout v6 | 升到 v7（3 处） |
| `.github/workflows/ci-test.yml` | checkout v7 | checkout v6 | 升到 v7 |
| `.github/workflows/close_inactive_issues.yaml` | checkout v7 + 中文注释 | checkout v6，无注释 | v7 + 补注释 |
| `.github/workflows/issue_opened_auto_reply.yaml` | 顶部中文注释 | 无 | 补注释 |
| `.pre-commit-config.yaml` | ruff-pre-commit v0.8.3 | v0.15.0 | 改为 v0.8.3 |
| `script/lint` | codespell 不含 CONTRIBUTING/AGENTS | 含 | 与 HA `script/lint` 一致（以 CI/lint-check 为准） |
| `CONTRIBUTING.md` | 有 Dependency upgrades 专节 | 无 | 补充 Py 语境版本 |
| `AGENTS.md` | 提及 Dependabot 范围 | 未提及 | 补充一句 |
| `.github/ISSUE_TEMPLATE/bug_report.md` | Logs 含 debug 提示 | 简化版 | 补 tracebacks 提示 |
| `.github/PULL_REQUEST_TEMPLATE.md` | 含手动验证 checklist | 缺 | 补 SDK 语境项 |

### 4.2 已对齐、无需改动

- `dependabot.yml`、`ISSUE_TEMPLATE/config.yml`、`feature_request.md`、`question.md`
- `close_inactive_author_issues.py`（逻辑一致，仅默认 repo 名不同）
- `script/setup`、`script/test`、`.yamllint.yml`
- CI 触发器、concurrency、reviewdog 集成
- Issue 自动欢迎回复正文
- inactive issue 阈值：STALE 21 天 / CLOSE 30 天

### 4.3 合理保留差异

| 项目 | Py | HA | 说明 |
|------|----|----|------|
| 版本同步 CI job | `Version-sync` | `Manifest` | 各仓库版本来源不同 |
| yamllint 目标 | 含 `publish.yml` | 含 `hacs.json` | 各仓库专属 workflow |
| Issue/PR 环境字段 | Python / pyimouapi | HA / integration version | 语境适配 |
| `pyproject.toml` ruff | per-file-ignores | 无 | 库代码需要 |
| `BRANCH_PROTECTION.md` | 独立文件 | 写在 CONTRIBUTING | Py 增强，保留 |

---

## 5. 文档增补内容

### 5.1 CONTRIBUTING — Dependency upgrades（Py 版）

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

中文附录同步增加对应条目。

### 5.2 AGENTS.md 增补

在 Code constraints 或独立 bullet 增加：

> Dependabot covers GitHub Actions only. Python dependency bumps are manual (`pyproject.toml` + `uv lock`).

### 5.3 PR 模板增补

Checklist 增加：

```markdown
- [ ] I have manually verified the changed behavior (see **Testing** below).
```

Testing 注释：

```markdown
<!-- Required: unit tests, manual API calls, and/or Home Assistant integration verification. -->
```

### 5.4 bug_report Logs 提示

```text
Paste relevant logs here (include tracebacks if applicable)
```

---

## 6. GitHub 分支保护（维护者手动）

合并治理 PR 后，在 GitHub → Settings → Branches → `main` 确认：

| 设置项 | 值 |
|--------|-----|
| Require PR before merging | 是，1 approval |
| Dismiss stale approvals | 是 |
| Required status checks | `Lint`, `Spell`, `YAML`, `Version-sync`, `Test` |

详见 `.github/BRANCH_PROTECTION.md`。

---

## 7. 验证计划

| 步骤 | 命令/动作 | 通过标准 |
|------|-----------|----------|
| 本地 lint | `script/setup && script/lint-check` | 退出码 0 |
| 本地测试 | `script/test` | 退出码 0 |
| pre-commit | `uv run pre-commit run --all-files` | 全部通过 |
| CI | 开 PR 到 `main` | 5 个 required checks 全绿 |
| 文档 | 人工对照 CONTRIBUTING 与 HA 章节 | 结构一一对应 |

---

## 8. 实施计划

- **分支**：`chore/align-governance-with-imou-ha`
- **目标仓库**：`Imou-OpenPlatform/Py-Imou-Open-Api`
- **预估改动**：约 10 个文件，无业务代码变更
- **风险**：ruff-pre-commit 降级后若与 dev 环境 ruff 版本冲突，将 rev 与 `pyproject.toml` 锁定一致

---

## 9. 验收标准

1. 除第 4.3 节「合理保留差异」外，治理文件与 HA 结构等价。
2. `script/lint-check` 检查项与 CI jobs 一致。
3. CONTRIBUTING 含 Dependency upgrades、PR 流程、分支保护、中文附录。
4. 所有 workflow 使用 `actions/checkout@v7`。
