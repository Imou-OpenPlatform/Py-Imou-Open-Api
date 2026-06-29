# Contributing to pyimouapi

Thank you for contributing to the Imou Open Platform Python SDK. This guide explains how to set up your environment, run checks locally, and open a pull request.

## Prerequisites

- Python 3.11 or newer
- [git](https://git-scm.com/)
- [uv](https://github.com/astral-sh/uv) (installed automatically by `script/setup` if missing)

## Getting started

1. Fork this repository on GitHub.
2. Clone your fork and create a feature branch from `main`:

   ```bash
   git checkout -b feat/my-change main
   ```

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

### Suggested branch names

- `fix/…` for bug fixes
- `feat/…` for new features
- `chore/…` for tooling or documentation

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
4. Open a `chore/…` PR.

### Runtime packages (`aiohttp`, `simpleeval`, etc.)

1. Bump in `pyproject.toml` `[project].dependencies`.
2. `uv lock`
3. Run `script/lint-check` and `script/test`; add tests if public API changes.
4. Open a `chore/…` PR. When releasing, bump `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml` together.

## Testing

- Automated tests live in `tests/` and use pytest with pytest-asyncio.
- Mock external API calls; do not require real Imou credentials in CI.
- For API behavior changes, describe manual verification steps in the PR **Testing** section.

## Opening a pull request

1. Push your branch to your fork.
2. Open a PR targeting **`main`**.
3. Fill out `.github/PULL_REQUEST_TEMPLATE.md` completely.
4. Ensure all CI checks pass:
   - **Lint**, **Spell**, **YAML**, **Version-sync**, **Test**
5. If you used AI tools, check the AI boxes in the PR template.

### Review process

1. CODEOWNERS are automatically requested for review.
2. A maintainer reviews functionality, compatibility, and test coverage.
3. Merge requires **one approval** and **green CI**.
4. Maintainers squash-merge to `main`.

### PR labels (maintainers)

| Label | Use |
|-------|-----|
| `bug` | Bug fix |
| `enhancement` | New feature |
| `breaking-change` | Breaking user-facing change |
| `needs-tests` | Missing or insufficient tests |
| `ci-failure` | CI needs contributor attention |

## Release process (maintainers)

1. Update `CHANGELOG.md` and bump version in `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml`.
2. Merge changes to `main`.
3. Tag on `main`: `git tag 1.2.8 && git push origin 1.2.8` (or `v1.2.8`)
4. The publish workflow uploads the package to PyPI.

## Imou-Home-Assistant integration

When a release affects Home Assistant behavior, open a follow-up PR in [Imou-Home-Assistant](https://github.com/Imou-OpenPlatform/Imou-Home-Assistant) to bump the `pyimouapi` pin in `manifest.json` and `pyproject.toml`.

## Branch protection (maintainers)

Configure in GitHub → **Settings** → **Branches** → rule for `main`:

- Require a pull request before merging (1 approval recommended)
- Require status checks: **Lint**, **Spell**, **YAML**, **Version-sync**, **Test**
- Dismiss stale approvals when new commits are pushed

See `.github/BRANCH_PROTECTION.md` for step-by-step instructions.

## Appendix: 中文快速指引

1. **环境**：`script/setup` 安装依赖与 pre-commit。
2. **提交前**：`script/lint` + `script/test` 必须通过。
3. **PR 目标分支**：`main`；使用仓库 PR 模板填写说明。
4. **发版**：维护者自行 bump 版本、更新 CHANGELOG、打 tag；PyPI 由 `publish.yml` 发布。
5. **HA 集成**：API 行为变更后，在 Imou-Home-Assistant 仓库另开 PR bump `pyimouapi` 版本。
6. **依赖升级**：仅 GitHub Actions 由 Dependabot 自动提 PR；Python 依赖手动升级。发版时须同步 bump `setup.py`、`pyimouapi/__init__.py`、`pyproject.toml`。
