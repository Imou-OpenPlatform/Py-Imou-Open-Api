# Select Friendly Option Keys Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 pyimouapi 1.3.4 将 `mode` / `device_volume` / `night_vision_mode` 的 select `current_option` 与 `options` 统一为友好稳定 key，读写边界完成 raw ↔ friendly 映射。

**Architecture:** 新增 `pyimouapi/select_option.py`（对齐 `sensor.py` 归一化模式）。配置默认值与 IoT/PaaS 读路径一律 `to_friendly`；写路径 `to_raw` 后再走现有 IoT/`15400` mute→`-1` 与 PaaS `NIGHT_VISION_MODE_MAP`。`collection_point` 跳过映射。

**Tech Stack:** Python 3.11+, pytest, asyncio, pyimouapi

**Spec:** `docs/superpowers/specs/2026-08-06-select-friendly-keys-design.md`

**Follow-up plans（本 plan 不含）：** Core 依赖 bump `1.3.0→1.3.4`、#177456 友好 key 适配、Imou-Home-Assistant 翻译同步。

## Global Constraints

- 版本保持 **1.3.4**（已在 tip；本 plan 不改版本号，只改语义并更新 CHANGELOG）
- 友好 key 词汇表（ verbatim from spec）：
  - volume: `mute`/`low`/`medium`/`high` ↔ `99`(含读 `-1`)/`0`/`1`/`2`；写 `15400` 时 mute→`-1`
  - mode: `home`/`away`/`disarm` ↔ `0`/`1`/`2`
  - night_vision: `intelligent`/`fullcolor`/`infrared`/`off`/`custom` ↔ IoT `0`–`4`；另保留 PaaS `lowlight`/`smartlowlight`
- 未知 raw：**原样返回** + debug 日志；未知友好 key（已映射的 select_type）：**`ValueError`**，禁止静默写错
- `collection_point`：**不**映射
- 每个 Task 结束后单独 commit；工作目录：`/home/open/projects/Py-Imou-Open-Api`，分支 `release/1.3.4`
- 测试命令：`uv run pytest <path> -v`（或 `.venv/bin/pytest`）

## 文件影响总览

| 文件 | 动作 | 职责 |
|------|------|------|
| `pyimouapi/select_option.py` | Create | raw ↔ friendly 映射 API |
| `tests/test_select_option.py` | Create | 映射表与边界单测 |
| `pyimouapi/const.py` | Modify | `SELECT_TYPE_REF` options/default 改为友好 key；可选 `PARAM_DEVICE_VOLUME` |
| `pyimouapi/ha_device.py` | Modify | 读/写/配置挂载 `to_friendly` / `to_raw` / `normalize_options` |
| `tests/test_write_optimistic_state.py` | Modify | select 断言改友好 key |
| `tests/test_update_from_detail.py` | Modify | volume `-1` → `mute`；key 用 `device_volume` |
| `CHANGELOG.md` | Modify | 记录 select 友好 key 破坏性变更 |

---

### Task 1: `select_option` 映射模块（TDD）

**Files:**
- Create: `pyimouapi/select_option.py`
- Create: `tests/test_select_option.py`

**Interfaces:**
- Consumes: `PARAM_MODE`, `PARAM_NIGHT_VISION_MODE`, `PARAM_COLLECTION_POINT` from `pyimouapi.const`；字面量 `"device_volume"`（若 Task 2 已加 `PARAM_DEVICE_VOLUME` 则改用常量）
- Produces:
  - `to_friendly(select_type: str, raw: str | int | None) -> str`
  - `to_raw(select_type: str, friendly: str) -> str`
  - `normalize_options(select_type: str, options: list[str]) -> list[str]`
  - `MAPPED_SELECT_TYPES: frozenset[str]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_select_option.py`:

```python
"""Tests for select option friendly-key normalization."""

from __future__ import annotations

import pytest
from pyimouapi.const import PARAM_MODE, PARAM_NIGHT_VISION_MODE
from pyimouapi.select_option import normalize_options, to_friendly, to_raw

PARAM_DEVICE_VOLUME = "device_volume"


@pytest.mark.parametrize(
    ("select_type", "raw", "friendly"),
    [
        (PARAM_DEVICE_VOLUME, "99", "mute"),
        (PARAM_DEVICE_VOLUME, "-1", "mute"),
        (PARAM_DEVICE_VOLUME, -1, "mute"),
        (PARAM_DEVICE_VOLUME, "0", "low"),
        (PARAM_DEVICE_VOLUME, "1", "medium"),
        (PARAM_DEVICE_VOLUME, "2", "high"),
        (PARAM_MODE, "0", "home"),
        (PARAM_MODE, "1", "away"),
        (PARAM_MODE, "2", "disarm"),
        (PARAM_NIGHT_VISION_MODE, "0", "intelligent"),
        (PARAM_NIGHT_VISION_MODE, "1", "fullcolor"),
        (PARAM_NIGHT_VISION_MODE, "2", "infrared"),
        (PARAM_NIGHT_VISION_MODE, "3", "off"),
        (PARAM_NIGHT_VISION_MODE, "4", "custom"),
        (PARAM_NIGHT_VISION_MODE, "intelligent", "intelligent"),
        (PARAM_NIGHT_VISION_MODE, "FullColor", "fullcolor"),
        (PARAM_NIGHT_VISION_MODE, "lowlight", "lowlight"),
        (PARAM_NIGHT_VISION_MODE, "smartlowlight", "smartlowlight"),
    ],
)
def test_to_friendly(select_type: str, raw: str | int, friendly: str) -> None:
    assert to_friendly(select_type, raw) == friendly


@pytest.mark.parametrize(
    ("select_type", "friendly", "raw"),
    [
        (PARAM_DEVICE_VOLUME, "mute", "99"),
        (PARAM_DEVICE_VOLUME, "low", "0"),
        (PARAM_DEVICE_VOLUME, "medium", "1"),
        (PARAM_DEVICE_VOLUME, "high", "2"),
        (PARAM_MODE, "home", "0"),
        (PARAM_MODE, "away", "1"),
        (PARAM_MODE, "disarm", "2"),
        (PARAM_NIGHT_VISION_MODE, "intelligent", "0"),
        (PARAM_NIGHT_VISION_MODE, "fullcolor", "1"),
        (PARAM_NIGHT_VISION_MODE, "infrared", "2"),
        (PARAM_NIGHT_VISION_MODE, "off", "3"),
        (PARAM_NIGHT_VISION_MODE, "custom", "4"),
        (PARAM_NIGHT_VISION_MODE, "lowlight", "lowlight"),
        (PARAM_NIGHT_VISION_MODE, "smartlowlight", "smartlowlight"),
    ],
)
def test_to_raw(select_type: str, friendly: str, raw: str) -> None:
    assert to_raw(select_type, friendly) == raw


def test_to_friendly_unknown_raw_passthrough() -> None:
    assert to_friendly(PARAM_MODE, "9") == "9"


def test_to_raw_unknown_friendly_raises() -> None:
    with pytest.raises(ValueError, match="unknown"):
        to_raw(PARAM_MODE, "vacation")


def test_normalize_options_maps_list() -> None:
    assert normalize_options(PARAM_MODE, ["0", "1", "2"]) == [
        "home",
        "away",
        "disarm",
    ]


def test_collection_point_identity() -> None:
    from pyimouapi.const import PARAM_COLLECTION_POINT

    assert to_friendly(PARAM_COLLECTION_POINT, "door") == "door"
    assert to_raw(PARAM_COLLECTION_POINT, "door") == "door"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_select_option.py -v`

Expected: FAIL（`ModuleNotFoundError: pyimouapi.select_option` 或 import error）

- [ ] **Step 3: Write minimal implementation**

Create `pyimouapi/select_option.py`:

```python
"""Select option key normalization for Home Assistant integrations."""

from __future__ import annotations

import logging
from typing import Any

from pyimouapi.const import (
    PARAM_COLLECTION_POINT,
    PARAM_MODE,
    PARAM_NIGHT_VISION_MODE,
)

_LOGGER = logging.getLogger(__name__)

PARAM_DEVICE_VOLUME = "device_volume"

MAPPED_SELECT_TYPES = frozenset(
    {PARAM_MODE, PARAM_DEVICE_VOLUME, PARAM_NIGHT_VISION_MODE}
)

# raw string -> friendly
_VOLUME_RAW_TO_FRIENDLY = {
    "99": "mute",
    "-1": "mute",
    "0": "low",
    "1": "medium",
    "2": "high",
}
_VOLUME_FRIENDLY_TO_RAW = {
    "mute": "99",
    "low": "0",
    "medium": "1",
    "high": "2",
}

_MODE_RAW_TO_FRIENDLY = {"0": "home", "1": "away", "2": "disarm"}
_MODE_FRIENDLY_TO_RAW = {v: k for k, v in _MODE_RAW_TO_FRIENDLY.items()}

_NIGHT_VISION_RAW_TO_FRIENDLY = {
    "0": "intelligent",
    "1": "fullcolor",
    "2": "infrared",
    "3": "off",
    "4": "custom",
}
_NIGHT_VISION_FRIENDLY_TO_RAW = {
    "intelligent": "0",
    "fullcolor": "1",
    "infrared": "2",
    "off": "3",
    "custom": "4",
    "lowlight": "lowlight",
    "smartlowlight": "smartlowlight",
}
# PaaS already-friendly keys also accepted as raw (identity after lower)
for _k in ("intelligent", "fullcolor", "infrared", "off", "custom", "lowlight", "smartlowlight"):
    _NIGHT_VISION_RAW_TO_FRIENDLY.setdefault(_k, _k)


def _as_raw_str(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def to_friendly(select_type: str, raw: Any) -> str:
    """Map vendor/API raw option to a stable friendly key."""
    if select_type == PARAM_COLLECTION_POINT or select_type not in MAPPED_SELECT_TYPES:
        return _as_raw_str(raw)

    key = _as_raw_str(raw)
    if select_type == PARAM_DEVICE_VOLUME:
        table = _VOLUME_RAW_TO_FRIENDLY
    elif select_type == PARAM_MODE:
        table = _MODE_RAW_TO_FRIENDLY
    else:
        key_l = key.lower()
        mapped = _NIGHT_VISION_RAW_TO_FRIENDLY.get(key_l)
        if mapped is not None:
            return mapped
        _LOGGER.debug("unknown night_vision raw option %r", raw)
        return key_l

    if key in table:
        return table[key]
    _LOGGER.debug("unknown %s raw option %r", select_type, raw)
    return key


def to_raw(select_type: str, friendly: str) -> str:
    """Map friendly key to vendor/API raw string for IoT writes.

    For PaaS-only night vision keys (`lowlight`, `smartlowlight`), returns the
    same lowercase string (caller uses NIGHT_VISION_MODE_MAP).
    Raises ValueError for unknown keys on mapped select types.
    """
    if select_type == PARAM_COLLECTION_POINT or select_type not in MAPPED_SELECT_TYPES:
        return friendly

    key = friendly.strip().lower()
    if select_type == PARAM_DEVICE_VOLUME:
        table = _VOLUME_FRIENDLY_TO_RAW
    elif select_type == PARAM_MODE:
        table = _MODE_FRIENDLY_TO_RAW
    else:
        table = _NIGHT_VISION_FRIENDLY_TO_RAW

    if key not in table:
        raise ValueError(f"unknown {select_type} option: {friendly!r}")
    return table[key]


def normalize_options(select_type: str, options: list[str]) -> list[str]:
    """Return options list with each entry passed through to_friendly."""
    return [to_friendly(select_type, item) for item in options]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_select_option.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyimouapi/select_option.py tests/test_select_option.py
git commit -m "$(cat <<'EOF'
feat: add select option friendly-key normalization helpers

EOF
)"
```

---

### Task 2: `SELECT_TYPE_REF` 默认值改为友好 key

**Files:**
- Modify: `pyimouapi/const.py`（`SELECT_TYPE_REF` 中 `night_vision_mode` / `mode` / `device_volume` 的 `default` 与 `options`）
- Optional: 在 `const.py` 增加 `PARAM_DEVICE_VOLUME = "device_volume"`，并让 `select_option.py` 从 const 导入（删模块内重复字面量）

**Interfaces:**
- Consumes: Task 1 词汇表
- Produces: 配置阶段写出的 `options`/`default` 已是友好 key

- [ ] **Step 1: Write a failing configure test**

Append to `tests/test_select_option.py`:

```python
from pyimouapi.const import SELECT_TYPE_REF
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def test_configure_select_by_ref_uses_friendly_defaults() -> None:
    device = ImouHaDevice("d1", "cam", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_product_id("pid")
    # refs that match SELECT_TYPE_REF entries
    ImouHaDeviceManager.configure_select_by_ref(
        ["15200", "15400", "17400"],
        True,
        [],
        device,
    )
    assert device.selects[PARAM_MODE]["options"] == ["home", "away", "disarm"]
    assert device.selects[PARAM_MODE]["current_option"] == "home"
    assert device.selects["device_volume"]["options"] == [
        "mute",
        "low",
        "medium",
        "high",
    ]
    assert device.selects["device_volume"]["current_option"] == "low"
    assert device.selects[PARAM_NIGHT_VISION_MODE]["options"] == [
        "intelligent",
        "fullcolor",
        "infrared",
        "off",
    ]
    assert device.selects[PARAM_NIGHT_VISION_MODE]["current_option"] == "intelligent"
```

（若 `configure_select_by_ref` 对每个 type 只取第一个匹配 ref：`17400` 覆盖 night_vision；`15200` mode；`15400` volume。按 `SELECT_TYPE_REF` 遍历顺序验证实际落入 device 的 key。）

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_select_option.py::test_configure_select_by_ref_uses_friendly_defaults -v`

Expected: FAIL（仍为 `"0"`/`"99"`）

- [ ] **Step 3: Update `SELECT_TYPE_REF` in `const.py`**

Replace the three blocks’ `default`/`options` as follows（保留 ref / value_type / 其余字段不变）：

```python
    "night_vision_mode": [
        {
            "ref": "17400",
            "default": "intelligent",
            "options": ["intelligent", "fullcolor", "infrared", "off"],
            "value_type": "int",
        },
        {
            "ref": "139700",
            "default": "intelligent",
            "options": [
                "intelligent",
                "fullcolor",
                "infrared",
                "off",
                "custom",
            ],
            "value_type": "int",
        },
        {
            "ref": "112400",
            "default": "infrared",
            "options": ["infrared", "off"],
            "value_type": "int",
        },
    ],
    "mode": [
        {
            "ref": "15200",
            "default": "home",
            "options": ["home", "away", "disarm"],
            "value_type": "int",
        }
    ],
    "device_volume": [
        {
            "ref": "15400",
            "default": "low",
            "options": ["mute", "low", "medium", "high"],
            "value_type": "int",
        }
    ],
```

Optionally add near other PARAM_* lines:

```python
PARAM_DEVICE_VOLUME = "device_volume"
```

Then update `select_option.py` to `from pyimouapi.const import ..., PARAM_DEVICE_VOLUME` and remove local constant.

- [ ] **Step 4: Run configure test**

Run: `uv run pytest tests/test_select_option.py::test_configure_select_by_ref_uses_friendly_defaults -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyimouapi/const.py pyimouapi/select_option.py tests/test_select_option.py
git commit -m "$(cat <<'EOF'
feat: use friendly defaults in SELECT_TYPE_REF

EOF
)"
```

---

### Task 3: 读路径挂载 `to_friendly`

**Files:**
- Modify: `pyimouapi/ha_device.py` — `_apply_property_value`（select 分支）、`_async_update_device_night_vision_mode`
- Modify: `tests/test_update_from_detail.py`

**Interfaces:**
- Consumes: `to_friendly`, `normalize_options` from Task 1
- Produces: detail/property/PaaS 更新后 `current_option`/`options` 仅为友好 key

- [ ] **Step 1: Update failing expectation in `test_update_from_detail.py`**

Change the volume select key and assertion:

```python
    device.selects["device_volume"] = {PARAM_REF: "15400", PARAM_CURRENT_OPTION: "low"}
    # ...
    assert device.selects["device_volume"][PARAM_CURRENT_OPTION] == "mute"
```

（detail 仍提供 `"15400": -1`。）

- [ ] **Step 2: Run test — expect FAIL if wire-up missing, or FAIL on old `"99"`**

Run: `uv run pytest tests/test_update_from_detail.py::test_update_from_detail_applies_switch_and_select -v`

Expected: FAIL（仍为 `"99"` 或 key `"volume"` 找不到）

- [ ] **Step 3: Wire `to_friendly` in `_apply_property_value`**

In `ha_device.py` imports add:

```python
from .select_option import normalize_options, to_friendly, to_raw
```

Replace select branch in `_apply_property_value`（约 366–370 行）为：

```python
        elif kind == "select":
            value = str(raw_value) if isinstance(raw_value, int) else raw_value
            if ref == "15400" and str(value) == "-1":
                value = "99"
            device.selects[key][PARAM_CURRENT_OPTION] = to_friendly(key, value)
```

- [ ] **Step 4: Wire night vision update**

In `_async_update_device_night_vision_mode`，在写入 current/options 处改为：

```python
        if data[PARAM_MODE] is not None:
            device.selects[PARAM_NIGHT_VISION_MODE][PARAM_CURRENT_OPTION] = to_friendly(
                PARAM_NIGHT_VISION_MODE, data[PARAM_MODE]
            )
        if data[PARAM_MODES] is not None:
            device.selects[PARAM_NIGHT_VISION_MODE][PARAM_OPTIONS] = normalize_options(
                PARAM_NIGHT_VISION_MODE,
                [item.lower() for item in data[PARAM_MODES]],
            )
```

- [ ] **Step 5: Run related tests**

Run:

```bash
uv run pytest tests/test_update_from_detail.py tests/test_select_option.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyimouapi/ha_device.py tests/test_update_from_detail.py
git commit -m "$(cat <<'EOF'
feat: normalize select options on read paths

EOF
)"
```

---

### Task 4: 写路径挂载 `to_raw`

**Files:**
- Modify: `pyimouapi/ha_device.py` — `async_select_option`
- Modify: `tests/test_write_optimistic_state.py`

**Interfaces:**
- Consumes: `to_raw` from Task 1
- Produces: 云端仍收数字/`NIGHT_VISION_MODE_MAP`；本地 `current_option` 存友好 key

- [ ] **Step 1: Update optimistic select test to friendly keys**

In `tests/test_write_optimistic_state.py` replace `test_select_option_by_ref_updates_local_state_without_read` body:

```python
async def test_select_option_by_ref_updates_local_state_without_read() -> None:
    """IoT select writes update current_option without a coordinator refresh read."""
    device = _ha_device()
    device.selects[PARAM_MODE] = {
        PARAM_REF: "15200",
        PARAM_CURRENT_OPTION: "home",
        PARAM_OPTIONS: ["home", "away", "disarm"],
        PARAM_VALUE_TYPE: "int",
    }
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_select_option(device, PARAM_MODE, "away")

    assert device.selects[PARAM_MODE][PARAM_CURRENT_OPTION] == "away"
    delegate.async_set_iot_device_properties.assert_awaited_once()
    # content should send raw "1" for away
    call_kwargs = delegate.async_set_iot_device_properties.await_args
    assert call_kwargs is not None
    delegate.async_get_iot_device_properties = AsyncMock()
    delegate.async_get_iot_device_properties.assert_not_called()
```

Add a volume mute write test in the same file:

```python
@pytest.mark.asyncio
async def test_select_volume_mute_writes_minus_one() -> None:
    device = _ha_device()
    device.selects["device_volume"] = {
        PARAM_REF: "15400",
        PARAM_CURRENT_OPTION: "low",
        PARAM_OPTIONS: ["mute", "low", "medium", "high"],
        PARAM_VALUE_TYPE: "int",
    }
    delegate = MagicMock()
    delegate.async_set_iot_device_properties = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_select_option(device, "device_volume", "mute")

    assert device.selects["device_volume"][PARAM_CURRENT_OPTION] == "mute"
    # async_set_iot_device_properties(device_id, channel_id, product_id, {ref: value})
    props = delegate.async_set_iot_device_properties.await_args.args[3]
    assert props == {"15400": -1}
```

- [ ] **Step 2: Run tests — expect FAIL（仍把 `"away"` 当 raw 写出或本地存错）**

Run: `uv run pytest tests/test_write_optimistic_state.py -v`

Expected: FAIL or wrong cloud payload

- [ ] **Step 3: Update `async_select_option` IoT branch**

Replace the IoT ref branch（约 866–876）为：

```python
        if device.selects[select_type].get(PARAM_REF):
            ref_id = device.selects[select_type].get(PARAM_REF)
            value_type = device.selects[select_type].get(PARAM_VALUE_TYPE)
            write_option = to_raw(select_type, option)
            # 兼容下音量15400值为-1的情况
            if ref_id == "15400" and write_option == "99":
                write_option = "-1"
            await self._async_select_option_by_ref(
                device, write_option, ref_id, value_type
            )
            device.selects[select_type][PARAM_CURRENT_OPTION] = to_friendly(
                select_type, option
            )
```

PaaS night vision 分支保持调用 `async_set_device_night_vision_mode(..., option)`（友好 key / 已有 map）；本地：

```python
            device.selects[PARAM_NIGHT_VISION_MODE][PARAM_CURRENT_OPTION] = to_friendly(
                PARAM_NIGHT_VISION_MODE, option
            )
```

- [ ] **Step 4: Run write + full select-related suite**

Run:

```bash
uv run pytest tests/test_write_optimistic_state.py tests/test_select_option.py tests/test_update_from_detail.py tests/test_collection_point.py -v
```

Expected: PASS（collection_point 不受影响）

- [ ] **Step 5: Commit**

```bash
git add pyimouapi/ha_device.py tests/test_write_optimistic_state.py
git commit -m "$(cat <<'EOF'
feat: map friendly select keys to raw on write

EOF
)"
```

---

### Task 5: CHANGELOG + 全量回归

**Files:**
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Tasks 1–4 行为
- Produces: 发布说明中的破坏性说明

- [ ] **Step 1: Update `CHANGELOG.md` under `## [1.3.4]`**

Add under `### Changed`（保留既有条目）：

```markdown
- Select `current_option` / `options` for `mode`, `device_volume`, and `night_vision_mode` use stable friendly keys (`home`/`away`/`disarm`, `mute`/`low`/`medium`/`high`, `intelligent`/`fullcolor`/…); IoT numeric codes are mapped at the library boundary (breaking for consumers that compared numeric option strings)
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -q`

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "$(cat <<'EOF'
docs: note select friendly-key breaking change in 1.3.4 changelog

EOF
)"
```

---

## Self-Review (plan vs spec)

| Spec 要求 | Task |
|-----------|------|
| `select_option.py` 边界映射 | Task 1 |
| `SELECT_TYPE_REF` 友好 default/options | Task 2 |
| 读路径 `_apply_property_value` / night vision | Task 3 |
| 写路径 `to_raw` + mute→`-1` | Task 4 |
| `collection_point` 跳过 | Task 1 identity + Task 4 不改该分支 |
| 未知 raw passthrough / 未知 friendly raise | Task 1 |
| CHANGELOG 破坏性说明 | Task 5 |
| 版本 1.3.4 一次发版 | 本 plan 不改号；发 PyPI 在 follow-up |
| Core / 社区适配 | **另开 plan**（见上 Follow-up） |

---

## 执行交接

Plan complete and saved to `docs/superpowers/plans/2026-08-06-select-friendly-keys.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每个 Task 派一个新 subagent，Task 间复查
2. **Inline Execution** — 本会话用 executing-plans 按 Task 推进并设检查点

**Which approach?**
