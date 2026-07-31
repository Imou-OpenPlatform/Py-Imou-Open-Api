# Imou 警笛开启/关闭 Button Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 pyimouapi 与 Imou-Home-Assistant 中新增 `siren_start` / `siren_stop` 两个 Button 实体，支持 PaaS `sirenStart`/`sirenStop` 与 IoT ref `25500`/`22200`。

**Architecture:** PaaS 设备通过 `BUTTON_TYPE_ABILITY` + 专用 API；IoT 设备走通用 ref 按压分支（`siren_stop` 与 `mute` 同机制、不同 ref；`siren_start` 扩展可选 `input_ref` 自动填 ISO 8601）。HA 层仅补翻译/图标，实体仍由 `device.buttons` 驱动。

**Tech Stack:** Python 3.11+, pytest, asyncio, Home Assistant custom integration, pyimouapi

**Spec:** `Py-Imou-Open-Api/docs/superpowers/specs/2026-07-31-siren-button-design.md`

## Global Constraints

- 版本 bump 至 **1.3.4**（`pyproject.toml`、`setup.py`、`pyimouapi/__init__.py`、`uv.lock`、HA `manifest.json` / `pyproject.toml`）
- `clientLocalTime` 格式：`datetime.now().astimezone().isoformat(timespec="seconds")`
- IoT ref：`siren_start` → `25500` + input `25501`；`siren_stop` → `22200`（空 content，**不得**与 mute ref `21600`/`2200` 混用）
- PaaS 能力名：`Siren`；接口 `/openapi/sirenStart`、`/openapi/sirenStop`；params 含 `deviceId`、`channelId`
- ability 已注册时 IoT ref **不覆盖**（PaaS 优先，与 `restart_device` 一致）
- HA button 写后 **保留** `async_request_refresh()`（与 mute 一致）
- v1 **不**做倒计时 sensor、不 bump 无关平台逻辑
- 每个 Task 完成后在对应仓库单独 commit

## 文件影响总览

| 仓库 | 文件 | 动作 |
|------|------|------|
| Py-Imou-Open-Api | `pyimouapi/const.py` | Modify |
| Py-Imou-Open-Api | `pyimouapi/device.py` | Modify |
| Py-Imou-Open-Api | `pyimouapi/ha_device.py` | Modify |
| Py-Imou-Open-Api | `tests/test_siren.py` | Create |
| Py-Imou-Open-Api | `pyproject.toml`, `setup.py`, `pyimouapi/__init__.py`, `uv.lock`, `CHANGELOG.md` | Modify |
| Imou-Home-Assistant | `custom_components/imou_life/strings.json` | Modify |
| Imou-Home-Assistant | `custom_components/imou_life/translations/en.json` | Modify |
| Imou-Home-Assistant | `custom_components/imou_life/translations/zh-Hans.json` | Modify |
| Imou-Home-Assistant | `custom_components/imou_life/icons.json` | Modify |
| Imou-Home-Assistant | `custom_components/imou_life/manifest.json`, `pyproject.toml`, `uv.lock`, `CHANGELOG.md` | Modify |

**不改：** `Imou-Home-Assistant/custom_components/imou_life/button.py`（注册与 refresh 逻辑保持不变）

---

### Task 1: 常量与 Button 发现配置

**Files:**
- Modify: `pyimouapi/const.py`
- Create: `tests/test_siren.py`（仅 discovery 测试，本 Task 末）

**Interfaces:**
- Consumes: 无
- Produces:
  - `PARAM_SIREN_START = "siren_start"`
  - `PARAM_SIREN_STOP = "siren_stop"`
  - `PARAM_INPUT_REF = "input_ref"`
  - `API_ENDPOINT_SIREN_START`, `API_ENDPOINT_SIREN_STOP`
  - `IOT_SIREN_START_REF = "25500"`, `IOT_SIREN_START_INPUT_REF = "25501"`, `IOT_SIREN_STOP_REF = "22200"`
  - `BUTTON_TYPE_ABILITY` / `BUTTON_TYPE_REF` 条目

- [ ] **Step 1: 写 discovery 失败测试**

创建 `tests/test_siren.py`：

```python
"""Tests for siren start/stop button support."""

from __future__ import annotations

from pyimouapi.const import (
    PARAM_INPUT_REF,
    PARAM_REF,
    PARAM_SIREN_START,
    PARAM_SIREN_STOP,
)
from pyimouapi.ha_device import ImouHaDevice, ImouHaDeviceManager


def _ha_device(*, product_id: str = "prod1") -> ImouHaDevice:
    device = ImouHaDevice("DEV001", "Front Camera", "Imou", "IPC", "1.0")
    device.set_channel_id("0")
    device.set_product_id(product_id)
    return device


def test_configure_siren_buttons_by_ability() -> None:
    """Siren ability registers start/stop without ref."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ability(
        channel_abilities=["Siren"],
        is_ipc=True,
        device_abilities=[],
        imou_ha_device=device,
    )
    assert PARAM_SIREN_START in device.buttons
    assert PARAM_SIREN_STOP in device.buttons
    assert device.buttons[PARAM_SIREN_START] == {}
    assert device.buttons[PARAM_SIREN_STOP] == {}


def test_configure_siren_start_by_ref_includes_input_ref() -> None:
    """IoT SirenStart stores ref and input_ref."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ref(
        channel_ability_refs=["25500"],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_START] == {
        PARAM_REF: "25500",
        PARAM_INPUT_REF: "25501",
    }


def test_configure_siren_stop_by_ref() -> None:
    """IoT SirenStop stores ref only."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ref(
        channel_ability_refs=["22200"],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_STOP] == {PARAM_REF: "22200"}


def test_ability_blocks_siren_ref_when_already_registered() -> None:
    """PaaS ability takes priority; IoT ref is not added."""
    device = _ha_device()
    ImouHaDeviceManager.configure_button_by_ability(
        channel_abilities=["Siren"],
        is_ipc=True,
        device_abilities=[],
        imou_ha_device=device,
    )
    ImouHaDeviceManager.configure_button_by_ref(
        channel_ability_refs=["25500", "22200"],
        is_ipc=True,
        device_ability_refs=[],
        imou_ha_device=device,
    )
    assert device.buttons[PARAM_SIREN_START] == {}
    assert device.buttons[PARAM_SIREN_STOP] == {}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /home/open/projects/Py-Imou-Open-Api
uv run pytest tests/test_siren.py -v
```

Expected: FAIL（`PARAM_SIREN_START` 未定义或 discovery 未注册）

- [ ] **Step 3: 修改 `const.py`**

在 `PARAM_RESTART_DEVICE` 附近增加：

```python
PARAM_SIREN_START = "siren_start"
PARAM_SIREN_STOP = "siren_stop"
PARAM_INPUT_REF = "input_ref"
```

在 API endpoints 区增加：

```python
API_ENDPOINT_SIREN_START = "/openapi/sirenStart"
API_ENDPOINT_SIREN_STOP = "/openapi/sirenStop"
```

在 IoT ref 常量区（收藏点附近）增加：

```python
IOT_SIREN_START_REF = "25500"
IOT_SIREN_START_INPUT_REF = "25501"
IOT_SIREN_STOP_REF = "22200"
```

更新 `BUTTON_TYPE_ABILITY`：

```python
BUTTON_TYPE_ABILITY = {
    "restart_device": ["Reboot"],
    ...
    "siren_start": ["Siren"],
    "siren_stop": ["Siren"],
}
```

更新 `BUTTON_TYPE_REF`（在 `mute` 之后）：

```python
    "siren_start": [
        {"ref": IOT_SIREN_START_REF, "input_ref": IOT_SIREN_START_INPUT_REF},
    ],
    "siren_stop": [
        {"ref": IOT_SIREN_STOP_REF},
    ],
```

- [ ] **Step 4: 修改 `configure_button_by_ref` 写入 `input_ref`**

`pyimouapi/ha_device.py` 中 `configure_button_by_ref`：

```python
                    button_entry = {PARAM_REF: ref[PARAM_REF]}
                    if ref.get(PARAM_INPUT_REF):
                        button_entry[PARAM_INPUT_REF] = ref[PARAM_INPUT_REF]
                    imou_ha_device.buttons[button_type] = button_entry
                    break
```

并在文件顶部 imports 增加 `PARAM_INPUT_REF`, `PARAM_SIREN_START`, `PARAM_SIREN_STOP`（后续 Task 会用到，本 Task 仅 discovery）。

- [ ] **Step 5: 运行 discovery 测试**

```bash
uv run pytest tests/test_siren.py -v
```

Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add pyimouapi/const.py pyimouapi/ha_device.py tests/test_siren.py
git commit -m "$(cat <<'EOF'
feat: add siren button constants and discovery

Register siren_start/siren_stop via Siren ability or IoT refs 25500/22200.
EOF
)"
```

---

### Task 2: PaaS API 方法

**Files:**
- Modify: `pyimouapi/device.py`
- Modify: `tests/test_siren.py`

**Interfaces:**
- Consumes: `API_ENDPOINT_SIREN_START`, `API_ENDPOINT_SIREN_STOP`, `PARAM_DEVICE_ID`, `PARAM_CHANNEL_ID`
- Produces:
  - `ImouDeviceManager.async_siren_start(device_id: str, channel_id: str) -> None`
  - `ImouDeviceManager.async_siren_stop(device_id: str, channel_id: str) -> None`

- [ ] **Step 1: 写 PaaS API 失败测试**

在 `tests/test_siren.py` 追加：

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyimouapi.device import ImouDeviceManager


@pytest.mark.asyncio
async def test_async_siren_start_calls_api() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_siren_start("DEV001", "0")

    client.async_request_api.assert_awaited_once_with(
        "/openapi/sirenStart",
        {"deviceId": "DEV001", "channelId": "0"},
    )


@pytest.mark.asyncio
async def test_async_siren_stop_calls_api() -> None:
    client = MagicMock()
    client.async_request_api = AsyncMock()
    manager = ImouDeviceManager(client)

    await manager.async_siren_stop("DEV001", "0")

    client.async_request_api.assert_awaited_once_with(
        "/openapi/sirenStop",
        {"deviceId": "DEV001", "channelId": "0"},
    )
```

- [ ] **Step 2: 运行确认失败**

```bash
uv run pytest tests/test_siren.py::test_async_siren_start_calls_api tests/test_siren.py::test_async_siren_stop_calls_api -v
```

Expected: FAIL `AttributeError: async_siren_start`

- [ ] **Step 3: 实现 `device.py`**

imports 增加 `API_ENDPOINT_SIREN_START`, `API_ENDPOINT_SIREN_STOP`。

在 `async_turn_device_collection` 之后增加：

```python
    async def async_siren_start(self, device_id: str, channel_id: str) -> None:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_SIREN_START, params
        )

    async def async_siren_stop(self, device_id: str, channel_id: str) -> None:
        params = {
            PARAM_DEVICE_ID: device_id,
            PARAM_CHANNEL_ID: channel_id,
        }
        await self._imou_api_client.async_request_api(
            API_ENDPOINT_SIREN_STOP, params
        )
```

- [ ] **Step 4: 运行 PaaS API 测试**

```bash
uv run pytest tests/test_siren.py::test_async_siren_start_calls_api tests/test_siren.py::test_async_siren_stop_calls_api -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add pyimouapi/device.py tests/test_siren.py
git commit -m "$(cat <<'EOF'
feat: add PaaS sirenStart and sirenStop API methods
EOF
)"
```

---

### Task 3: IoT 通用 ref 按压（含 input_ref）

**Files:**
- Modify: `pyimouapi/ha_device.py`
- Modify: `tests/test_siren.py`

**Interfaces:**
- Consumes: `PARAM_INPUT_REF`, `_resolve_device_id`, `delegate.async_iot_device_control`
- Produces:
  - `_async_press_button_by_ref(device, ref, content=None)` — `content` 默认 `{}`
  - 通用 ref 分支：有 `input_ref` 时构建 ISO 8601 content

- [ ] **Step 1: 写 IoT 按压失败测试**

```python
from datetime import datetime, timezone
from unittest.mock import patch

from pyimouapi.ha_device import ImouHaDeviceManager


@pytest.mark.asyncio
async def test_press_siren_start_iot_sends_client_local_time() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_START] = {
        PARAM_REF: "25500",
        PARAM_INPUT_REF: "25501",
    }
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)
    fixed = datetime(2026, 7, 31, 15, 8, tzinfo=timezone.utc)

    with patch("pyimouapi.ha_device.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
        await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001",
        "prod1",
        "25500",
        {"25501": "2026-07-31T15:08:00+00:00"},
    )


@pytest.mark.asyncio
async def test_press_siren_stop_iot_empty_content() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_STOP] = {PARAM_REF: "22200"}
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_STOP, 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001", "prod1", "22200", {}
    )


@pytest.mark.asyncio
async def test_press_mute_iot_still_empty_content() -> None:
    """mute path unchanged after input_ref extension."""
    from pyimouapi.const import PARAM_MUTE  # add at module top if preferred

    device = _ha_device()
    device.buttons["mute"] = {PARAM_REF: "21600"}
    delegate = MagicMock()
    delegate.async_iot_device_control = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, "mute", 500)

    delegate.async_iot_device_control.assert_awaited_once_with(
        "DEV001", "prod1", "21600", {}
    )
```

在文件顶部 `from pyimouapi.const import` 中补充 `PARAM_MUTE = "mute"` 或直接用字符串 `"mute"`（与 const 中 key 一致）。

- [ ] **Step 2: 运行确认失败**

```bash
uv run pytest tests/test_siren.py::test_press_siren_start_iot_sends_client_local_time tests/test_siren.py::test_press_siren_stop_iot_empty_content tests/test_siren.py::test_press_mute_iot_still_empty_content -v
```

Expected: FAIL（content 未传或 ISO 未生成）

- [ ] **Step 3: 修改 `ha_device.py`**

1. 文件顶部增加 `from datetime import datetime`

2. 扩展 `_async_press_button_by_ref`：

```python
    async def _async_press_button_by_ref(
        self, device: ImouHaDevice, ref: str, content: dict | None = None
    ):
        if content is None:
            content = {}
        device_id = self._resolve_device_id(device)
        await self.delegate.async_iot_device_control(
            device_id, device.product_id, ref, content
        )
```

（删除原方法内重复的 device_id 拼接逻辑，统一用 `_resolve_device_id`。）

3. 修改 `async_press_button` 通用 ref 分支：

```python
        elif device.buttons[button_type].get(PARAM_REF):
            ref_id = device.buttons[button_type].get(PARAM_REF)
            content: dict = {}
            if input_ref := device.buttons[button_type].get(PARAM_INPUT_REF):
                content = {
                    input_ref: datetime.now()
                    .astimezone()
                    .isoformat(timespec="seconds")
                }
            await self._async_press_button_by_ref(device, ref_id, content)
```

**注意：** 本 Task 先 **不** 加 PaaS siren 分支；IoT ref 设备走上述分支。PaaS 专用分支在 Task 4 添加（否则 ability-only `{}` 设备按压会 no-op）。

- [ ] **Step 4: 运行 IoT 测试**

```bash
uv run pytest tests/test_siren.py::test_press_siren_start_iot_sends_client_local_time tests/test_siren.py::test_press_siren_stop_iot_empty_content tests/test_siren.py::test_press_mute_iot_still_empty_content -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pyimouapi/ha_device.py tests/test_siren.py
git commit -m "$(cat <<'EOF'
feat: support IoT siren buttons via ref control with input_ref

Extend generic button ref press to send clientLocalTime for siren_start.
EOF
)"
```

---

### Task 4: PaaS 警笛按压分支

**Files:**
- Modify: `pyimouapi/ha_device.py`
- Modify: `tests/test_siren.py`

**Interfaces:**
- Consumes: `delegate.async_siren_start`, `delegate.async_siren_stop`, `RequestFailedException`
- Produces: `_async_siren_paas(device, button_type) -> None`

- [ ] **Step 1: 写 PaaS 按压失败测试**

```python
from pyimouapi.exceptions import RequestFailedException


@pytest.mark.asyncio
async def test_press_siren_start_paas() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_START] = {}
    delegate = MagicMock()
    delegate.async_siren_start = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_START, 500)

    delegate.async_siren_start.assert_awaited_once_with("DEV001", "0")
    delegate.async_iot_device_control.assert_not_called()


@pytest.mark.asyncio
async def test_press_siren_stop_paas() -> None:
    device = _ha_device()
    device.buttons[PARAM_SIREN_STOP] = {}
    delegate = MagicMock()
    delegate.async_siren_stop = AsyncMock()
    manager = ImouHaDeviceManager(delegate)

    await manager.async_press_button(device, PARAM_SIREN_STOP, 500)

    delegate.async_siren_stop.assert_awaited_once_with("DEV001", "0")


@pytest.mark.asyncio
async def test_press_siren_paas_requires_channel() -> None:
    device = _ha_device()
    device.set_channel_id(None)
    device.buttons[PARAM_SIREN_START] = {}
    manager = ImouHaDeviceManager(MagicMock())

    with pytest.raises(RequestFailedException):
        await manager.async_press_button(device, PARAM_SIREN_START, 500)
```

需在 mock delegate 上确保 `async_iot_device_control = AsyncMock()` 以便 `assert_not_called` 可用。

- [ ] **Step 2: 运行确认失败**

```bash
uv run pytest tests/test_siren.py::test_press_siren_start_paas tests/test_siren.py::test_press_siren_stop_paas tests/test_siren.py::test_press_siren_paas_requires_channel -v
```

Expected: FAIL（PaaS 未调用）

- [ ] **Step 3: 实现 PaaS 分支**

在 `async_press_button` 中，PTZ 分支之后、通用 ref 分支 **之前** 插入：

```python
        elif button_type in (PARAM_SIREN_START, PARAM_SIREN_STOP):
            if not device.buttons[button_type].get(PARAM_REF):
                await self._async_siren_paas(device, button_type)
                return
```

新增方法：

```python
    async def _async_siren_paas(self, device: ImouHaDevice, button_type: str) -> None:
        if device.channel_id is None:
            raise RequestFailedException(f"{button_type} requires channel")
        channel_id = str(device.channel_id)
        if button_type == PARAM_SIREN_START:
            await self.delegate.async_siren_start(device.device_id, channel_id)
        elif button_type == PARAM_SIREN_STOP:
            await self.delegate.async_siren_stop(device.device_id, channel_id)
```

- [ ] **Step 4: 运行全部 pyimouapi siren 测试**

```bash
uv run pytest tests/test_siren.py -v
```

Expected: 全部 passed

- [ ] **Step 5: 运行完整 pyimouapi 测试套件**

```bash
uv run pytest -q
```

Expected: 全部 passed（含既有 52+ tests）

- [ ] **Step 6: Bump 版本与 CHANGELOG**

`1.3.3` → `1.3.4`：`pyproject.toml`、`setup.py`、`pyimouapi/__init__.py`，运行 `uv lock`，`CHANGELOG.md` 增加：

```markdown
## [1.3.4]

- Siren start/stop button support: PaaS `sirenStart`/`sirenStop` and IoT refs `25500`/`22200`
```

- [ ] **Step 7: Commit**

```bash
git add pyimouapi/ha_device.py tests/test_siren.py pyproject.toml setup.py pyimouapi/__init__.py uv.lock CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat: wire PaaS siren start/stop button press (1.3.4)
EOF
)"
```

---

### Task 5: Imou-Home-Assistant 翻译与版本

**Files:**
- Modify: `custom_components/imou_life/strings.json`
- Modify: `custom_components/imou_life/translations/en.json`
- Modify: `custom_components/imou_life/translations/zh-Hans.json`
- Modify: `custom_components/imou_life/icons.json`
- Modify: `custom_components/imou_life/manifest.json`
- Modify: `pyproject.toml`, `uv.lock`, `CHANGELOG.md`

**Interfaces:**
- Consumes: pyimouapi 1.3.4（本地 path 依赖若存在则同步 lock）
- Produces: HA 实体名/图标；`requirements: ["pyimouapi==1.3.4"]`

- [ ] **Step 1: 更新 `strings.json` button 段**

在 `"mute"` 之后增加：

```json
      "siren_start": {
        "name": "Start Siren"
      },
      "siren_stop": {
        "name": "Stop Siren"
      }
```

- [ ] **Step 2: 更新 `translations/en.json`**

同上（sentence case）。

- [ ] **Step 3: 更新 `translations/zh-Hans.json`**

```json
      "siren_start": {
        "name": "开启警笛"
      },
      "siren_stop": {
        "name": "关闭警笛"
      }
```

- [ ] **Step 4: 更新 `icons.json` button 段**

```json
			"siren_start": {
				"default": "mdi:bullhorn"
			},
			"siren_stop": {
				"default": "mdi:bullhorn-outline"
			}
```

- [ ] **Step 5: Bump HA 版本**

`manifest.json` 的 `version` 与 `requirements` 中 `pyimouapi==1.3.4`；`pyproject.toml` 依赖版本同步；`uv lock`。

`CHANGELOG.md` 增加 1.3.4 条目：新增警笛开启/关闭 button。

- [ ] **Step 6: 运行 HA 测试**

```bash
cd /home/open/projects/Imou-Home-Assistant
uv run pytest -q
```

Expected: 全部 passed

- [ ] **Step 7: Commit**

```bash
git add custom_components/imou_life/strings.json custom_components/imou_life/translations/en.json custom_components/imou_life/translations/zh-Hans.json custom_components/imou_life/icons.json custom_components/imou_life/manifest.json pyproject.toml uv.lock CHANGELOG.md
git commit -m "$(cat <<'EOF'
feat: add siren start/stop button translations (1.3.4)
EOF
)"
```

---

### Task 6: 规格状态更新

**Files:**
- Modify: `docs/superpowers/specs/2026-07-31-siren-button-design.md`

- [ ] **Step 1: 将 spec 状态改为已批准**

`**状态** 待审阅` → `**状态** 已批准`

- [ ] **Step 2: Commit**

```bash
cd /home/open/projects/Py-Imou-Open-Api
git add docs/superpowers/specs/2026-07-31-siren-button-design.md
git commit -m "$(cat <<'EOF'
docs: mark siren button design approved
EOF
)"
```

---

## Plan Self-Review

| Spec 要求 | 对应 Task |
|-----------|-----------|
| PaaS sirenStart/Stop | Task 2, 4 |
| IoT 25500 + 25501 ISO8601 | Task 1, 3 |
| IoT 22200 空 content | Task 1, 3 |
| mute 与 siren_stop ref 分离 | Task 3 mute 回归测试 |
| ability 优先于 ref | Task 1 测试 |
| HA 翻译/图标 | Task 5 |
| 不写后改 refresh | 不改 button.py（spec 约束） |
| 版本 1.3.4 | Task 4, 5 |
| 全量测试通过 | Task 4 Step 5, Task 5 Step 6 |

无 TBD / 占位步骤。
