# Agent Instructions

This repository contains the **pyimouapi** Python library for the Imou Open Platform APIs.

## Git workflow (maintainers / agents)

- Develop **only** on `dev`. Do not create `feat/`, `fix/`, `chore/`, or other topic branches.
- `main` is the PyPI release branch. Merge `dev` into `main` only when shipping a release.
- Commit and push on `dev` unless the user explicitly asks for a `dev` → `main` PR.

## Before opening a PR

1. Run `script/setup` once in a fresh environment.
2. Run `script/lint` and `script/test` — both must pass.
3. Use `.github/PULL_REQUEST_TEMPLATE.md` — do not remove unchecked checklist items.
4. Do not amend or squash commits after a PR has received review.
5. Target `dev` for ongoing work. Target `main` only for a release merge from `dev`.

## Code constraints

- Preserve public API compatibility unless the PR explicitly scopes a breaking change.
- New behavior should include unit tests under `tests/`.
- Keep `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml` versions in sync when releasing.
- Dependabot covers GitHub Actions only. Python dependency bumps are manual (`pyproject.toml` + `uv lock`).

## AI limitations

AI-generated suggestions do not replace maintainer review. Contributors are responsible for understanding every line submitted.
