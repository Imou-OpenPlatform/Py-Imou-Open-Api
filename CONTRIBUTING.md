# Contributing to pyimouapi

Thank you for contributing to the Imou Open Platform Python SDK. This guide explains how to set up your environment, run checks locally, and open a pull request.

## Prerequisites

- Python 3.11 or newer
- [git](https://git-scm.com/)
- [uv](https://github.com/astral-sh/uv) (installed automatically by `script/setup` if missing)

## Git workflow

This repo is maintained by one person. Keep the branch graph simple.

| Branch | Role |
|--------|------|
| `dev` | **Only development branch.** All features, fixes, and docs land here. |
| `main` | Released / PyPI. Update only when shipping a version (`dev` → `main`). |

**Do not** create `feat/…`, `fix/…`, `chore/…`, or other topic branches on `Imou-OpenPlatform/Py-Imou-Open-Api`. Maintainers and agents commit on `dev`.

## Getting started

1. Fork this repository on GitHub (external contributors) or clone it (maintainers).
2. Base your work on `dev`:

   ```bash
   git checkout dev
   git pull origin dev
   ```

   External contributors: create a short-lived branch **on the fork** from `dev`, then open a PR **into `dev`**. Do not open PRs against `main` unless you are merging a release.

3. Install development dependencies:

   ```bash
   script/setup
   ```

## Development workflow

1. Make your changes under `pyimouapi/` and/or `tests/`.
2. Format and lint:

   ```bash
   script/lint
   ```

3. Run tests:

   ```bash
   script/test
   ```

4. Optional: run the same checks CI uses without modifying files:

   ```bash
   script/lint-check
   ```

Pre-commit hooks run automatically on `git commit` after `script/setup`.

### Branches (forks only)

External contributors may use a short-lived branch **on their fork** (`fix/…`, `feat/…`, `chore/…`). That branch is deleted after the PR merges into `dev`. Do not push topic branches to the canonical repository.

## Code standards

- Python code is formatted and linted with [Ruff](https://docs.astral.sh/ruff/).
- Preserve backward compatibility for public APIs consumed by [Imou-Home-Assistant](https://github.com/Imou-OpenPlatform/Imou-Home-Assistant) unless explicitly scoped.
- Keep version strings aligned across `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml` when releasing.

## Dependency upgrades

[Dependabot](https://docs.github.com/en/code-security/dependabot) opens weekly PRs for **GitHub Actions** only. Python dependencies are upgraded manually so `pyproject.toml` and `uv.lock` stay in sync.

### Dev-only packages (`ruff`, `pytest`, etc.)

1. Bump the version in `pyproject.toml` (`[dependency-groups].dev`).
2. Regenerate the lockfile: `uv lock`
3. Run `script/lint-check` and `script/test`.
4. Commit on `dev` (maintainers) or open a PR into `dev` (forks).

### Runtime packages (`aiohttp`, `simpleeval`, etc.)

1. Bump in `pyproject.toml` `[project].dependencies`.
2. `uv lock`
3. Run `script/lint-check` and `script/test`; add tests if public API changes.
4. Commit on `dev` or open a PR into `dev`. When releasing, bump `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml` together.

## Testing

- Automated tests live in `tests/` and use pytest with pytest-asyncio.
- Mock external API calls; do not require real Imou credentials in CI.
- For API behavior changes, describe manual verification steps in the PR **Testing** section.

## Opening a pull request

1. Push your fork branch (or push `dev` if you are a maintainer merging a release).
2. Open a PR targeting **`dev`**. Target **`main` only** for a release merge from `dev`.
3. Fill out `.github/PULL_REQUEST_TEMPLATE.md` completely.
4. Ensure all CI checks pass:
   - **Lint**, **Spell**, **YAML**, **Version-sync**, **Test**
5. If you used AI tools, check the AI boxes in the PR template.

### Review process

1. CODEOWNERS are automatically requested for review.
2. A maintainer reviews functionality, compatibility, and test coverage.
3. Merge requires **one approval** and **green CI**.
4. Maintainers squash-merge into `dev`. Releases squash-merge `dev` into `main`.

### PR labels (maintainers)

| Label | Use |
|-------|-----|
| `bug` | Bug fix |
| `enhancement` | New feature |
| `breaking-change` | Breaking user-facing change |
| `needs-tests` | Missing or insufficient tests |
| `ci-failure` | CI needs contributor attention |

## Release process (maintainers)

1. On `dev`, update `CHANGELOG.md` and bump version in `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml`.
2. Open a PR **`dev` → `main`** (this is the only time work should land on `main`).
3. After merge, tag on `main`: `git tag 1.2.8 && git push origin 1.2.8` (or `v1.2.8`)
4. The publish workflow uploads the package to PyPI.

## Imou-Home-Assistant integration

When a release affects Home Assistant behavior, bump the `pyimouapi` pin in [Imou-Home-Assistant](https://github.com/Imou-OpenPlatform/Imou-Home-Assistant) on **that repo's `dev` branch** (`manifest.json` and `pyproject.toml`). Do not open a topic branch there either.

## Branch protection (maintainers)

Configure in GitHub → **Settings** → **Branches** → rule for `main` (release only):

- Require a pull request before merging (1 approval recommended)
- Require status checks: **Lint**, **Spell**, **YAML**, **Version-sync**, **Test**
- Dismiss stale approvals when new commits are pushed

Do **not** require a pull request on `dev`. Maintainers push `dev` directly; CI already runs on push to `dev`.

See `.github/BRANCH_PROTECTION.md` for step-by-step instructions.

## Appendix: 中文快速指引

1. **环境**：`script/setup` 安装依赖与 pre-commit。
2. **提交前**：`script/lint` + `script/test` 必须通过。
3. **开发分支**：`dev`（不要在本仓库开 feat/fix 分支）。**PR**：日常合入 `dev`；发版才从 `dev` 合到 `main`。使用仓库 PR 模板填写说明。
4. **发版**：维护者自行 bump 版本、更新 CHANGELOG、打 tag；PyPI 由 `publish.yml` 发布。
5. **HA 集成**：API 行为变更后，在 Imou-Home-Assistant 的 `dev` 上 bump `pyimouapi`，不要另开特性分支。
6. **依赖升级**：仅 GitHub Actions 由 Dependabot 自动提 PR；Python 依赖手动升级。发版时须同步 bump `setup.py`、`pyimouapi/__init__.py`、`pyproject.toml`。
