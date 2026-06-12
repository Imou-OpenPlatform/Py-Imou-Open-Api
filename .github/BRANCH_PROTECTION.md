# main 分支保护配置指南

本文档面向仓库维护者，说明如何在 GitHub 上为 `main` 分支启用 PR 治理规则。

## 前置条件

- 仓库管理员权限
- CI workflow 已合并（`ci-lint.yml`、`ci-test.yml`）

## 配置步骤

1. 打开 GitHub 仓库 → **Settings** → **Branches**。
2. 点击 **Add branch protection rule**（或编辑已有 `main` 规则）。
3. **Branch name pattern** 填写：`main`
4. 勾选 **Require a pull request before merging**
   - 建议勾选 **Require approvals**：至少 **1** 人
   - 建议勾选 **Dismiss stale pull request approvals when new commits are pushed**
5. 勾选 **Require status checks to pass before merging**
   - 勾选 **Require branches to be up to date before merging**（推荐）
   - 在搜索框中添加以下必需检查（名称须与 workflow job `name` 一致）：
     - `Lint`
     - `Spell`
     - `YAML`
     - `Version-sync`
     - `Test`
6. 可选：勾选 **Require conversation resolution before merging**
7. 可选：勾选 **Do not allow bypassing the above settings**（仅超级管理员可绕过）
8. 点击 **Create** / **Save changes**

> **注意：** 首次合并 CI workflow 后，状态检查名称才会出现在 GitHub 选项列表中。可先合并治理 PR，再在 follow-up 中补全 required checks。

## 紧急 hotfix

若启用 bypass，仓库 Admin 可在紧急情况下直接推送到 `main`。请在 hotfix 后尽快补 PR 与 CHANGELOG。

## Fork PR

当前 CI 使用 `pull_request` 触发，不向 fork PR 暴露 secrets，外部贡献者 PR 与内部 PR 使用同一套检查。

## CODEOWNERS

合并 `.github/CODEOWNERS` 后，PR 会自动请求 `@Imou-OpenPlatform` 团队 review。请确认团队成员已加入 GitHub 组织并具有 review 权限。
