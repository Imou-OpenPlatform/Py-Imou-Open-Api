# Agent Instructions

This repository contains the **pyimouapi** Python library for the Imou Open Platform APIs.

## Before opening a PR

1. Run `script/setup` once in a fresh environment.
2. Run `script/lint` and `script/test` — both must pass.
3. Use `.github/PULL_REQUEST_TEMPLATE.md` — do not remove unchecked checklist items.
4. Do not amend or squash commits after a PR has received review.

## Code constraints

- Preserve public API compatibility unless the PR explicitly scopes a breaking change.
- New behavior should include unit tests under `tests/`.
- Keep `setup.py`, `pyimouapi/__init__.py`, and `pyproject.toml` versions in sync when releasing.

## AI limitations

AI-generated suggestions do not replace maintainer review. Contributors are responsible for understanding every line submitted.
