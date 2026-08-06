# HA Core imou Select Friendly Keys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 更新 Core `imou-select` 分支（PR #177456）：strings/icons/tests 使用友好 option key，并去掉多余 `usefixtures`；**本 plan 不 bump** `pyimouapi` 版本（依赖 PR 另开，待 PyPI 1.3.4）。

**Architecture:** Select 实体透传 `device.selects`；mock/fixture 改为友好 key 后与库 1.3.4 契约对齐。manifest 暂留 `pyimouapi==1.3.0`，PR 描述写 `Depends on` 库发版 + 后续依赖 PR。

**Tech Stack:** Home Assistant Core, pytest, syrupy

**Spec:** `Py-Imou-Open-Api/docs/superpowers/specs/2026-08-06-select-friendly-keys-design.md`

## Global Constraints

- 友好 key 词汇表同 spec §3（mode `home`/`away`/`disarm`；volume `mute`/`low`/`medium`/`high`；night_vision 字符串键含 `custom`）
- 删除数字 state keys；night_vision 不再双轨
- Reviewer：去掉测试里「已有 `init_integration` 参数却仍加 `@pytest.mark.usefixtures("init_integration")`」的装饰器（`test_select_option_via_domain_service`、`test_select_option_propagates_api_error`，以及同文件其它「参数含 init_integration」的用例）
- **不要**改 `manifest.json` / `requirements_all.txt`（依赖 bump 单独 PR）
- Work from: `/home/open/projects/core`，分支 `imou-select`
- Never Co-authored-by Cursor；never update git config
- 改 strings 后需 `python3 -m script.translations develop --integration imou` 再更新 snapshot

## 文件影响

| 文件 | 动作 |
|------|------|
| `homeassistant/components/imou/strings.json` | Friendly select states |
| `homeassistant/components/imou/icons.json` | Friendly state icons |
| `tests/components/imou/const.py` | DEFAULT_SELECTS friendly |
| `tests/components/imou/test_select.py` | Friendly options + usefixtures cleanup |
| `tests/components/imou/snapshots/test_select.ambr` | Regenerate |

---

### Task 1: strings + icons

目标 select 段与社区 `strings.json` 同构（common 引用：`home`/`not_home`/`low`/`medium`/`high`/`off`）。

icons volume/mode state keys → `mute`/`low`/`medium`/`high`，`home`/`away`/`disarm`。

- [ ] 改文件并 commit `fix: use friendly Imou select option translation keys`

---

### Task 2: fixtures + tests + snapshots

`DEFAULT_SELECTS`：

```python
PARAM_NIGHT_VISION_MODE: {
    PARAM_CURRENT_OPTION: "intelligent",
    PARAM_OPTIONS: ["intelligent", "fullcolor", "infrared", "off"],
},
PARAM_MODE: {
    PARAM_CURRENT_OPTION: "home",
    PARAM_OPTIONS: ["home", "away", "disarm"],
},
PARAM_DEVICE_VOLUME: {
    PARAM_CURRENT_OPTION: "medium",
    PARAM_OPTIONS: ["mute", "low", "medium", "high"],
},
```

`test_select.py`：
- 所有 mock options/current 改友好 key
- `test_select_option_via_domain_service`：选 `away` 而非 `"1"`；断言 `call.args[2] == "away"`；state `== "away"`
- error 测试 ATTR_OPTION 用 `"away"`
- 去掉与 `init_integration` 参数重复的 `@pytest.mark.usefixtures("init_integration")`（保留仅用 usefixtures、无参数注入的用例，如 snapshot）

然后：

```bash
python3 -m script.translations develop --integration imou
# 用项目 venv pytest，按需 --snapshot-update
.venv/bin/pytest tests/components/imou/test_select.py -q --snapshot-update
.venv/bin/pytest tests/components/imou/test_select.py -q
```

- [ ] Commit `test: align Imou select fixtures with friendly keys`

---

### Task 3: 更新 PR 描述（可选手动）

在 #177456 注明：Depends on pyimouapi 1.3.4 + Core dependency bump PR；已响应 friendly keys + usefixtures 反馈。不 bump manifest。
